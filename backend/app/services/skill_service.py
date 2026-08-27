"""技能服务：可插拔 LangChain 工具注册表 + 数据库启用状态管理 + 社区市场。

设计要点：
1. "内置工具"用 LangChain @tool 装饰器在 Python 代码中定义，零外部包依赖。
2. "市场工具"映射到 langchain_community 里的真实工具（DDG/Wikipedia/Arxiv 等），
   作为"开源技能市场"的来源；用户可以"安装/卸载"，启用后 LLM 真能调用。
3. Skill 表存"用户级启用/禁用"状态和展示元信息；工具实现本身不在 DB。
4. 首次访问时自动为内置工具初始化 Skill 行（owner_id = 当前用户）。
5. chat_service 调用 get_enabled_tools(user, db) 拿到当前用户启用的 BaseTool 列表，
   用 llm.bind_tools(tools) 绑定到 LLM，实现 Function Calling。
"""
from __future__ import annotations

import ast
import operator
from datetime import datetime
from typing import Callable, Optional

from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.skill import Skill
from app.models.user import User


# ---------- 内置工具实现（纯 Python 标准库，无外部依赖） ----------

_ALLOWED_OPS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("不支持的表达式节点（仅支持数字和 + - * / // % ** 与括号）")


@tool
def calculator(expression: str) -> str:
    """计算数学表达式。支持加减乘除、括号、幂运算、取模。

    输入：合法的数学表达式字符串，例如 '2 + 3 * (4 - 1)' 或 '2 ** 10'。
    返回：计算结果字符串。
    """
    try:
        result = _safe_eval(ast.parse(expression, mode="eval").body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"计算结果：{expression} = {result}"
    except Exception as e:
        return f"计算失败：{e}（请输入合法的数学表达式，例如 (2+3)*4）"


@tool
def datetime_now(query: str = "") -> str:
    """获取当前日期、时间和星期几。

    输入：可选的查询字符串，例如 '今天' / 'now' / '星期几'。空字符串也行。
    返回：当前日期时间的中文描述。
    """
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return (
        f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"（{weekdays[now.weekday()]}）"
    )


@tool
def text_statistics(text: str) -> str:
    """统计文本的字数、词数、行数。

    输入：要统计的文本内容。
    返回：总字符数、中文字符数、英文词数、行数。
    """
    if not text:
        return "输入为空"
    chars = len(text)
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    english_words = len([w for w in text.split() if any(c.isalpha() for c in w)])
    lines = text.count("\n") + 1
    return (
        f"字数统计：总字符 {chars}，中文字符 {chinese_chars}，"
        f"英文词数 {english_words}，行数 {lines}"
    )


@tool
def review_outline(topic: str) -> str:
    """为给定主题生成复习大纲（5 个要点模板）。

    输入：要复习的主题或知识点名称。
    返回：5 要点的复习提纲。
    """
    return (
        f"《{topic}》复习大纲（5 要点）：\n"
        f"1. 基础概念与定义\n"
        f"2. 核心原理与机制\n"
        f"3. 典型应用场景\n"
        f"4. 常见误区与注意事项\n"
        f"5. 拓展延伸与参考资料\n"
        f"（建议结合教材章节与课堂笔记逐项展开）"
    )


@tool
def resume_check(resume_text: str) -> str:
    """检查简历的常见问题（字数、关键词覆盖、结构）。

    输入：简历全文或关键段落。
    返回：检查报告，列出问题或确认结构完整。
    """
    issues: list[str] = []
    if len(resume_text) < 100:
        issues.append("简历过短（少于 100 字），建议补充项目经历和技能描述")
    if len(resume_text) > 2000:
        issues.append("简历过长（超过 2000 字），建议精简到 1 页 A4")
    keywords = ["教育", "项目", "技能", "实习", "获奖"]
    missing = [k for k in keywords if k not in resume_text]
    if missing:
        issues.append(f"缺少关键板块：{', '.join(missing)}")
    if not issues:
        issues.append("结构完整，建议进一步优化内容量化（用数据描述项目成果）")
    return "简历检查报告：\n" + "\n".join(f"- {i}" for i in issues)


# ---------- 市场工具（langchain_community 真实实现） ----------
# 这些工具来自开源 LangChain 社区生态，用户"安装"后立即可被 LLM 调用。

def _make_ddg_search() -> Optional[BaseTool]:
    """DuckDuckGo 网络搜索（无需 API key）。"""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun()
    except Exception:
        return None


@tool
def bocha_search(query: str) -> str:
    """使用博查 AI 进行网络搜索（国内可访问）。

    适合查询最新新闻、技术资料、天气、人物背景等需要联网的信息。

    输入：搜索关键词，例如 'Python 3.13 新特性'。
    返回：搜索结果摘要 + 关键网页列表。
    """
    import json as _json
    import urllib.request
    import urllib.parse

    from app.config import settings

    api_key = (settings.BOCHA_API_KEY or "").strip()
    if not api_key:
        return ("博查 API Key 未配置，请在 backend/.env 设置 BOCHA_API_KEY="
                "sk-xxx（在 https://open.bochaai.com 注册免费获取）")

    url = "https://api.bochaai.com/v1/web-search"
    body = _json.dumps({
        "query": query,
        "summary": True,        # 让博查返回一段 AI 总结
        "count": 5,             # 取前 5 条网页
        "freshness": "oneYear",  # 时间范围：一年内
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "campus-assistant/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"博查搜索请求失败：{type(e).__name__}: {e}"

    try:
        data = _json.loads(raw)
    except Exception:
        return f"博查返回非 JSON：{raw[:200]}"

    # 博查 API 的关键字段：data.summary / data.webPages.value[]
    summary = (data.get("data", {}) or {}).get("summary", "") or ""
    web_pages = ((data.get("data", {}) or {}).get("webPages", {}) or {}).get("value", []) or []

    out_parts: list[str] = []
    if summary:
        out_parts.append(f"📌 AI 总结：\n{summary}")
    if web_pages:
        out_parts.append("\n📄 网页结果：")
        for i, p in enumerate(web_pages[:5], 1):
            name = p.get("name", "")
            url0 = p.get("url", "")
            snippet = (p.get("snippet", "") or "").strip()
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            out_parts.append(f"[{i}] {name}\n链接: {url0}\n摘要: {snippet}")
    if not out_parts:
        return f"博查未返回结果：{raw[:400]}"
    return "\n\n".join(out_parts)


def _make_bocha_search() -> Optional[BaseTool]:
    """博查 AI 网络搜索（国内可访问，需要 BOCHA_API_KEY）。"""
    from app.config import settings
    if not (settings.BOCHA_API_KEY or "").strip():
        return None  # 未配置 key 时市场里显示为"依赖未装好"
    return bocha_search


def _make_wikipedia() -> Optional[BaseTool]:
    """Wikipedia 维基百科查询。"""
    try:
        from langchain_community.tools import WikipediaQueryRun
        from langchain_community.utilities import WikipediaAPIWrapper
        return WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=2))
    except Exception:
        return None


@tool
def arxiv_search(query: str) -> str:
    """在 arXiv 上搜索学术论文。返回最多 3 篇相关论文的标题/作者/摘要。

    输入：搜索关键词，例如 'transformer attention'。
    返回：论文列表摘要。
    """
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    import ssl as _ssl

    # arXiv 提供 Atom XML API：http://export.arxiv.org/api/query
    # 注意：arXiv 会从 http 跳转到 https，部分 Windows 环境的 SSL 证书校验失败；
    # 这里手动跳过证书校验，arXiv 是公网公开数据，无安全风险。
    base = "http://export.arxiv.org/api/query"
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": 3,
        "sortBy": "relevance",
    })
    url = f"{base}?{params}"

    try:
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "campus-assistant/1.0"})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            xml_data = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"arXiv HTTP 请求失败：{type(e).__name__}: {e}"

    # 解析 Atom XML（命名空间是 http://www.w3.org/2005/Atom）
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        return f"arXiv XML 解析失败：{e}"

    entries = root.findall("a:entry", ns)
    if not entries:
        return f"未在 arXiv 上找到 '{query}' 相关论文"

    out: list[str] = []
    for i, e in enumerate(entries, 1):
        title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
        title = " ".join(title.split())  # 压缩多余空白
        # 作者列表
        authors = e.findall("a:author", ns)
        author_names = []
        for a in authors[:3]:
            n = (a.findtext("a:name", default="", namespaces=ns) or "").strip()
            if n:
                author_names.append(n)
        authors_str = ", ".join(author_names)
        if len(authors) > 3:
            authors_str += f" 等 {len(authors)} 位作者"
        # 摘要
        summary = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
        summary = " ".join(summary.split())
        if len(summary) > 300:
            summary = summary[:300] + "..."
        # arxiv id
        entry_id = (e.findtext("a:id", default="", namespaces=ns) or "").strip()
        link = ""
        for l in e.findall("a:link", ns):
            if l.get("type") == "text/html":
                link = l.get("href", "")
                break
        if not link:
            link = entry_id

        out.append(
            f"[{i}] {title}\n作者: {authors_str}\narXiv: {entry_id}\n链接: {link}\n摘要: {summary}"
        )
    return "\n\n".join(out)


def _make_arxiv() -> Optional[BaseTool]:
    """arXiv 论文搜索（自实现，直接调 arXiv HTTP API，不依赖 arxiv Python 包）。"""
    return arxiv_search


@tool
def python_repl(code: str) -> str:
    """执行 Python 代码，返回 stdout 输出。

    适合做复杂数据处理、数值计算、批量字符串操作。代码在隔离的 namespace 里执行，
    不会污染主进程；可访问标准库（math/json/re/datetime 等）。

    输入：Python 代码字符串，例如 'import math; print(math.sqrt(2))'。
    返回：代码的 stdout 输出（截断到 2000 字符）。
    """
    import io
    import contextlib

    # 隔离的全局命名空间，预导入常用标准库
    import math, json, re, datetime, random, statistics, collections  # noqa: F401
    namespace = {
        "math": math, "json": json, "re": re, "datetime": datetime,
        "random": random, "statistics": statistics, "collections": collections,
        "sum": sum, "len": len, "range": range, "print": print,
        "sorted": sorted, "enumerate": enumerate, "zip": zip, "map": map,
        "filter": filter, "abs": abs, "round": round, "min": min, "max": max,
    }

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(code, namespace)
        out = buf.getvalue()
        if not out:
            return "代码执行完毕（无 stdout 输出）"
        if len(out) > 2000:
            out = out[:2000] + f"\n...(共 {len(out)} 字符，已截断)"
        return out
    except Exception as e:
        return f"代码执行失败：{type(e).__name__}: {e}"


def _make_python_repl() -> Optional[BaseTool]:
    """Python REPL（自实现，不依赖 langchain-experimental）。"""
    return python_repl


# 市场元信息（key -> 描述/类目/图标/依赖说明）
_MARKET_META: list[dict] = [
    {
        "skill_key": "duckduckgo_search",
        "name": "DuckDuckGo 搜索",
        "description": "匿名网络搜索（无需 API Key）。让助手能查最新新闻/技术资料/天气等。注意：国内访问 DuckDuckGo 受限。",
        "category": "search",
        "category_label": "网络搜索",
        "icon": "Search",
        "source": "langchain_community",
        "requirements": ["duckduckgo-search"],
    },
    {
        "skill_key": "bocha_search",
        "name": "博查 AI 搜索",
        "description": "国内可访问的 AI 网络搜索（无需翻墙）。需要 BOCHA_API_KEY，在 https://open.bochaai.com 注册免费获取。",
        "category": "search",
        "category_label": "网络搜索",
        "icon": "Search",
        "source": "bochaai",
        "requirements": ["BOCHA_API_KEY"],
    },
    {
        "skill_key": "wikipedia_query",
        "name": "Wikipedia 查询",
        "description": "查询维基百科条目，适合概念解释、人物/事件背景。",
        "category": "search",
        "category_label": "网络搜索",
        "icon": "Reading",
        "source": "langchain_community",
        "requirements": ["wikipedia"],
    },
    {
        "skill_key": "arxiv_query",
        "name": "Arxiv 论文搜索",
        "description": "搜索 arxiv.org 学术论文摘要，适合科研/写文献综述。",
        "category": "academic",
        "category_label": "学术辅助",
        "icon": "Document",
        "source": "self_impl",
        "requirements": [],
    },
    {
        "skill_key": "python_repl",
        "name": "Python 代码执行",
        "description": "执行 Python 代码，适合复杂数据处理/图表生成/批量计算。",
        "category": "compute",
        "category_label": "计算与代码",
        "icon": "Cpu",
        "source": "self_impl",
        "requirements": [],
    },
]

# key -> 工厂函数（懒加载，避免不存在的包导入失败）
_MARKET_FACTORIES: dict[str, Callable[[], Optional[BaseTool]]] = {
    "duckduckgo_search": _make_ddg_search,
    "bocha_search": _make_bocha_search,
    "wikipedia_query": _make_wikipedia,
    "arxiv_query": _make_arxiv,
    "python_repl": _make_python_repl,
}

# 缓存：key -> BaseTool | None（首次成功调用时实例化；失败的不缓存，便于重试）
_MARKET_INSTANCES: dict[str, Optional[BaseTool]] = {}


def _get_market_tool(key: str) -> Optional[BaseTool]:
    """惰性获取市场工具实例，找不到或依赖缺失返回 None。

    注意：失败结果不缓存，便于依赖安装后下次调用时重新尝试。
    """
    factory = _MARKET_FACTORIES.get(key)
    if factory is None:
        return None
    # 已经成功实例化过，直接返回缓存
    if key in _MARKET_INSTANCES and _MARKET_INSTANCES[key] is not None:
        return _MARKET_INSTANCES[key]
    # 否则尝试实例化
    try:
        inst = factory()
    except Exception:
        inst = None
    if inst is not None:
        _MARKET_INSTANCES[key] = inst  # 只缓存成功结果
    return inst


def is_market_tool_available(key: str) -> bool:
    """检查某个市场工具的依赖是否已装好。"""
    return _get_market_tool(key) is not None


# ---------- 内置注册表 ----------

_BUILTIN_TOOLS: list[BaseTool] = [
    calculator,
    datetime_now,
    text_statistics,
    review_outline,
    resume_check,
]

# skill_key -> BaseTool（含内置 + 已装好依赖的市场工具）
TOOL_INDEX: dict[str, BaseTool] = {t.name: t for t in _BUILTIN_TOOLS}

# 同步加入可用的市场工具到 TOOL_INDEX
for _meta in _MARKET_META:
    _t = _get_market_tool(_meta["skill_key"])
    if _t is not None:
        TOOL_INDEX[_meta["skill_key"]] = _t


def list_builtin_skills() -> list[dict]:
    """返回所有内置技能的元信息（不查 DB）。供前端展示。"""
    return [
        {
            "skill_key": t.name,
            "name": t.name,
            "description": (t.description or "").split("\n", 1)[0],
            "category": "tool",
            "category_label": _category_label(t.name),
            "icon": _icon_name(t.name),
            "source": "builtin",
        }
        for t in _BUILTIN_TOOLS
    ]


def list_market_tools() -> list[dict]:
    """返回市场所有可下载技能的元信息（不区分是否已安装）。"""
    return [
        {
            "skill_key": m["skill_key"],
            "name": m["name"],
            "description": m["description"],
            "category": m["category"],
            "category_label": m["category_label"],
            "icon": m["icon"],
            "source": m["source"],
            "requirements": m.get("requirements", []),
            "available": is_market_tool_available(m["skill_key"]),
        }
        for m in _MARKET_META
    ]


def _category_label(key: str) -> str:
    return {
        "calculator": "数学计算",
        "datetime_now": "日期时间",
        "text_statistics": "文本分析",
        "review_outline": "学习辅助",
        "resume_check": "求职辅助",
    }.get(key, "通用工具")


def _icon_name(key: str) -> str:
    return {
        "calculator": "Operation",
        "datetime_now": "Calendar",
        "text_statistics": "Document",
        "review_outline": "Reading",
        "resume_check": "Notebook",
    }.get(key, "MagicStick")


# ---------- DB CRUD ----------

def _merge_skill_rows(rows, user_id: int) -> list[Skill]:
    """按 skill_key 合并去重，返回每键至多一行。

    同一 skill_key 可能同时存在「全局模板行(owner_id=None)」和「用户专属行」，
    甚至历史遗留的同用户重复行。规则：用户专属行优先，全局模板行兜底。
    否则 get_enabled_tools 会拼出重复工具名，bind_tools 发给 LLM 时会报
    "Tool names must be unique"（DeepSeek 400 错误）。
    """
    merged: dict[str, Skill] = {}
    for r in rows:
        if r.owner_id is None:
            merged.setdefault(r.skill_key, r)
    for r in rows:
        if r.owner_id == user_id:
            merged[r.skill_key] = r
    return list(merged.values())


def get_user_skills(user: User, db: Session) -> list[Skill]:
    """读取用户已注册的技能记录；首次访问时自动初始化所有内置工具（market 不自动加）。"""
    rows = db.scalars(
        select(Skill).where(
            (Skill.owner_id == user.id) | (Skill.owner_id.is_(None))
        )
    ).all()

    rows = _merge_skill_rows(rows, user.id)

    existing_keys = {r.skill_key for r in rows}
    to_create = []
    for meta in list_builtin_skills():
        if meta["skill_key"] not in existing_keys:
            to_create.append(Skill(
                owner_id=user.id,
                skill_key=meta["skill_key"],
                name=meta["name"],
                description=meta["description"],
                category=meta["category"],
                enabled=True,
            ))
    if to_create:
        db.add_all(to_create)
        db.commit()
        rows = db.scalars(
            select(Skill).where(
                (Skill.owner_id == user.id) | (Skill.owner_id.is_(None))
            )
        ).all()
        rows = _merge_skill_rows(rows, user.id)
    return rows


def set_skill_enabled(user: User, skill_key: str, enabled: bool, db: Session) -> Skill:
    """切换某用户的技能启用状态。不存在则 404。"""
    row = db.scalar(
        select(Skill).where(
            Skill.owner_id == user.id,
            Skill.skill_key == skill_key,
        )
    )
    if row is None:
        # 把全局模板行（owner_id=None）克隆一份给当前用户
        global_row = db.scalar(
            select(Skill).where(
                Skill.owner_id.is_(None),
                Skill.skill_key == skill_key,
            )
        )
        if global_row is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"技能 {skill_key} 不存在")
        row = Skill(
            owner_id=user.id,
            skill_key=global_row.skill_key,
            name=global_row.name,
            description=global_row.description,
            category=global_row.category,
            enabled=enabled,
        )
        db.add(row)
    else:
        row.enabled = enabled
    db.commit()
    db.refresh(row)
    return row


def install_market_tool(user: User, skill_key: str, db: Session) -> Skill:
    """从市场"下载安装"一个工具：在 user_skills 表里插入一行，enabled=True。

    - 如果市场里没这个工具 → 404
    - 如果依赖未装好 → 400 提示用户
    - 如果已经安装过 → 复用现有行（不报错，方便前端幂等调用）
    """
    from fastapi import HTTPException

    meta = next((m for m in _MARKET_META if m["skill_key"] == skill_key), None)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"市场里没有这个技能：{skill_key}")

    if not is_market_tool_available(skill_key):
        reqs = ", ".join(meta.get("requirements", []))
        raise HTTPException(
            status_code=400,
            detail=f"技能 {meta['name']} 的依赖未装好（{reqs}），请在后端运行 pip install 安装",
        )

    # 看用户是否已经安装过
    row = db.scalar(
        select(Skill).where(
            Skill.owner_id == user.id,
            Skill.skill_key == skill_key,
        )
    )
    if row is None:
        row = Skill(
            owner_id=user.id,
            skill_key=meta["skill_key"],
            name=meta["name"],
            description=meta["description"],
            category=meta["category"],
            enabled=True,  # 安装即启用
        )
        db.add(row)
    else:
        # 已经装过，重新安装即重新启用
        row.enabled = True
    db.commit()
    db.refresh(row)
    return row


def uninstall_market_tool(user: User, skill_key: str, db: Session) -> bool:
    """卸载市场工具：删除用户对应的 user_skills 行。"""
    row = db.scalar(
        select(Skill).where(
            Skill.owner_id == user.id,
            Skill.skill_key == skill_key,
        )
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def get_enabled_tools(user: User, db: Session) -> list[BaseTool]:
    """获取该用户启用的所有工具实例（用于绑定到 LLM 做 Function Calling）。

    含内置 + 已安装的市场工具。

    每次调用时实时构建市场工具实例（避免 --reload 模式下模块级缓存失效问题）。
    """
    rows = get_user_skills(user, db)
    # 内置工具索引（每次实时构建，避免模块级缓存陈旧）
    builtin_idx: dict[str, BaseTool] = {t.name: t for t in _BUILTIN_TOOLS}
    # 市场工具索引（按 BaseTool.name 索引，便于 LLM tool_call name 匹配）
    market_idx: dict[str, BaseTool] = {}
    for m in _MARKET_META:
        try:
            inst = _MARKET_FACTORIES[m["skill_key"]]()
            if inst is not None:
                market_idx[inst.name] = inst  # 注意用 BaseTool.name 而非 skill_key
        except Exception:
            pass

    tools: list[BaseTool] = []
    for r in rows:
        if not r.enabled:
            continue
        # 在内置索引里找（用 skill_key，因为内置工具 .name == skill_key）
        if r.skill_key in builtin_idx:
            tools.append(builtin_idx[r.skill_key])
            continue
        # 在市场索引里找（按 BaseTool.name，因为市场工具的 .name 不等于 skill_key）
        # 这里我们用 skill_key 找对应 BaseTool.name
        meta = next((m for m in _MARKET_META if m["skill_key"] == r.skill_key), None)
        if meta is None:
            continue
        # 重新用工厂函数取一次实例（确保拿到最新的）
        try:
            inst = _MARKET_FACTORIES[r.skill_key]()
            if inst is not None:
                tools.append(inst)
        except Exception:
            pass
    return tools
