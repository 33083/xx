"""对话服务：会话管理 + 多轮记忆 + RAG 链 + SSE 流式输出。"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import AsyncIterator, Iterator, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.llm import EchoChatModel, get_llm
from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.schemas.conversation import (
    AgentType,
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationOut,
    ConversationTitleUpdate,
    MessageOut,
)
from app.services import rag_service, skill_service


# ---------------- 会话 CRUD ----------------

def _ensure_title(body: str) -> str:
    if not body:
        return "新对话"
    t = body.replace("\n", " ").strip()
    return (t[:20] + "…") if len(t) > 20 else t


def _coerce_agent_type(v) -> str:
    """把 ChatRequest.agent_type / ConversationCreate.agent_type 规范成 DB 存储字符串。

    Pydantic 的 AgentType 枚举值在 FastAPI 反序列化后，有时是 Enum 实例，有时是
    原始字符串（取决于请求 JSON 字段类型）。Conversation.agent_type 是
    Mapped[str]，如果塞入 Enum 实例，SQLAlchemy 会把它作为 Python 对象暂存在属性
    上（在 commit/refresh 之前不会转成数据库字符串），后面用 c.message_count 这
    种属性时，可能触发 SQLA 的实例状态错乱，得到 'str' object has no attribute 'id'
    这种诡异错误。所以统一转成小写字符串再赋值。
    """
    if isinstance(v, AgentType):
        return v.value
    s = str(v or "rag").strip().lower()
    if s not in {"chat", "rag", "react", "grill"}:
        s = "rag"
    return s


def create_conversation(user: User, payload: ConversationCreate, db: Session) -> ConversationOut:
    title = payload.title or "新对话"
    c = Conversation(
        owner_id=user.id,
        title=title,
        skill=payload.skill,
        agent_type=_coerce_agent_type(payload.agent_type),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return ConversationOut.model_validate(c)


def list_conversations(user: User, db: Session) -> List[ConversationOut]:
    rows = db.scalars(
        select(Conversation)
        .where(Conversation.owner_id == user.id)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return [ConversationOut.model_validate(r) for r in rows]


def get_conversation(user: User, cid: int, db: Session) -> Conversation | None:
    return db.scalar(select(Conversation).where(Conversation.id == cid, Conversation.owner_id == user.id))


def update_conversation_title(user: User, cid: int, up: ConversationTitleUpdate, db: Session) -> ConversationOut | None:
    c = get_conversation(user, cid, db)
    if c is None:
        return None
    c.title = up.title
    db.commit()
    db.refresh(c)
    return ConversationOut.model_validate(c)


def delete_conversation(user: User, cid: int, db: Session) -> bool:
    c = get_conversation(user, cid, db)
    if c is None:
        return False
    db.delete(c)
    db.commit()
    return True


def list_messages(user: User, cid: int, db: Session) -> List[MessageOut]:
    c = get_conversation(user, cid, db)
    if c is None:
        return []
    rows = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == cid)
        .order_by(ConversationMessage.id.asc())
    ).all()
    out = []
    for m in rows:
        refs = None
        if m.refs:
            try:
                refs = json.loads(m.refs)
            except Exception:
                refs = m.refs
        # Pydantic v2 model_validate 不支持 update= 关键字参数；
        # 改成先转 dict 再覆盖 refs 字段，最后再校验。
        data = {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "image_url": getattr(m, "image_url", None),
            "refs": refs,
            "created_at": m.created_at,
        }
        out.append(MessageOut.model_validate(data))
    return out


def search_conversations(user_id: int, q: str, db: Session, limit: int = 50) -> List[dict]:
    """按关键词全文搜索会话标题 + 消息内容，返回带会话上下文的命中列表。"""
    q = (q or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    hits: List[dict] = []
    # 1. 会话标题命中
    convs = db.scalars(
        select(Conversation)
        .where(Conversation.owner_id == user_id, Conversation.title.ilike(like))
        .order_by(Conversation.updated_at.desc())
        .limit(20)
    ).all()
    for c in convs:
        hits.append({
            "type": "conversation",
            "conversation_id": c.id,
            "title": c.title,
            "snippet": c.title,
            "role": "title",
            "created_at": c.updated_at.isoformat() if c.updated_at else "",
        })
    # 2. 消息内容命中（带上下文片段）
    rows = db.execute(
        select(ConversationMessage, Conversation)
        .join(Conversation, ConversationMessage.conversation_id == Conversation.id)
        .where(Conversation.owner_id == user_id, ConversationMessage.content.ilike(like))
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
    ).all()
    for m, c in rows:
        content = m.content or ""
        idx = content.lower().find(q.lower())
        if idx < 0:
            idx = 0
        start = max(0, idx - 30)
        end = min(len(content), idx + len(q) + 70)
        snippet = ("…" if start > 0 else "") + content[start:end] + ("…" if end < len(content) else "")
        hits.append({
            "type": "message",
            "conversation_id": c.id,
            "title": c.title,
            "snippet": snippet,
            "role": m.role,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        })
    return hits


# ---------------- 对话核心 ----------------

# 历史上下文预算（字符）：超出后丢弃更早的消息，避免超 LLM token 上限
HISTORY_CHAR_BUDGET = 6000


def _load_recent_history(
    cid: int, db: Session, limit: int = 20, budget: int = HISTORY_CHAR_BUDGET
) -> Tuple[List[ConversationMessage], bool]:
    """按字符预算从新到旧截取历史消息。

    返回 (keep, truncated)：keep 为按时间正序保留的消息列表（旧→新）；
    truncated 表示是否因预算不足被截断（调用方可提示用户）。
    """
    rows = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == cid)
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
    ).all()
    keep: List[ConversationMessage] = []
    left = budget
    truncated = False
    for m in rows:  # rows 新的在前，优先保留最近内容
        cost = len(m.content or "") + len(getattr(m, "image_url", None) or "")
        if cost > left:
            truncated = True
            break
        keep.append(m)
        left -= cost
    keep.reverse()  # 转回 旧→新，供 LLM 顺序读取
    return keep, truncated


def _truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def _llm_supports_vision(llm) -> bool:
    """粗略判断当前 LLM 是否支持视觉输入。

    支持的视觉模型：
    - DeepSeek: deepseek-v4-flash-vision-exp（用户消息携带 image_url 时自动切到这个模型）
    - OpenAI: gpt-4o / gpt-4-vision / gpt-4-turbo
    - Claude 3 / Gemini / Qwen-VL / GLM-4V 等
    """
    model_name = ""
    try:
        # langchain_openai.ChatOpenAI 有 model_name / model 属性
        model_name = str(
            getattr(llm, "model_name", None) or getattr(llm, "model", "") or ""
        ).lower()
    except Exception:
        model_name = ""
    if not model_name:
        return False
    # 命中这些前缀/关键字视为视觉模型
    vision_hints = (
        "gpt-4o", "gpt-4-vision", "gpt-4-turbo",
        "claude-3", "gemini", "qwen-vl", "qwen2-vl", "glm-4v",
        "vision",  # DeepSeek deepseek-v4-flash-vision-exp 命中
    )
    return any(h in model_name for h in vision_hints)


def _resolve_image_url(url: str) -> str:
    """把后端本地的 /uploads/... 相对路径转成 base64 data URL。

    DeepSeek 视觉模型仅接受：
    1. base64 data URL: data:image/jpeg;base64,...
    2. 公网可访问 http(s) URL
    3. Files API file_id

    后端上传的图片是 /uploads/... 相对路径（公网不可访问），必须转 base64。
    """
    if not url:
        return url
    # 已经是 data: 或 http(s):// 直接返回
    if url.startswith("data:") or url.startswith("http://") or url.startswith("https://"):
        return url
    # /uploads/... 走本地文件读取转 base64
    if url.startswith("/uploads/"):
        from app.config import settings
        # services/ -> app/ -> backend/，backend/uploads/...
        here = os.path.dirname(os.path.abspath(__file__))
        backend_root = os.path.abspath(os.path.join(here, "..", ".."))
        local_path = os.path.join(backend_root, "uploads", url[len("/uploads/"):].replace("/", os.sep))
        if not os.path.exists(local_path):
            return url  # 找不到文件就原样返回，让模型报错也好定位
        # 推断 MIME
        ext = os.path.splitext(local_path)[1].lower()
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }
        mime = mime_map.get(ext, "image/png")
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    return url


def _build_user_message(req: ChatRequest, ctx_block: str, use_vision: bool):
    """构造当前轮的 HumanMessage。如果有 image_url 走多模态 content。

    use_vision=True 时构造 OpenAI 兼容的多模态 content：
        [{"type":"text",...}, {"type":"image_url","image_url":{"url":...}}]
    其中 image_url 会被 _resolve_image_url 转成 DeepSeek 视觉模型可接受的格式
    （base64 data URL 或公网 URL）。
    否则纯文本。
    """
    from langchain_core.messages import HumanMessage

    text_content = (
        (ctx_block + "\n\n用户问题：" + req.message) if ctx_block
        else "用户问题：" + req.message
    )

    if not req.image_url:
        return HumanMessage(content=text_content)

    if use_vision:
        # 多模态 content：text + image_url
        # 注意：DeepSeek 视觉模型只接受 base64 data URL 或公网 http(s) URL，
        # 后端本地的 /uploads/... 必须先转 base64。
        resolved_url = _resolve_image_url(req.image_url)
        content = [
            {"type": "text", "text": text_content},
            {"type": "image_url", "image_url": {"url": resolved_url}},
        ]
        return HumanMessage(content=content)
    else:
        # 降级：在文本里告诉模型用户上传了图片（模型本身看不了）
        tip = "\n\n[用户附带了一张图片，但当前模型不支持视觉理解；如需图片分析请配置支持视觉的 LLM]"
        return HumanMessage(content=text_content + tip)


def _prepare_messages(user_id: int, req: ChatRequest, db: Session, cid: int):
    """拼 LangChain messages：系统 + 历史 + RAG 上下文 + 当前问题。

    返回 (messages, refs, use_vision)：
    - use_vision: 当前请求是否应使用视觉 LLM（req.image_url 存在且视觉模型可用）
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from app.core.llm import get_vision_llm

    refs = []
    rag_ok = True
    if req.use_rag:
        out = rag_service.rag_search(user_id, req.message, category=req.rag_category)
        refs = out.hits
        rag_ok = out.rag_ok
    ctx_block = rag_service.build_context_block(refs)

    rag_roles = {
        "material": "当前分类【学习资料】：请扮演耐心的学习辅导老师，基于资料讲解概念、总结要点、解答疑问，多举例、分点作答。",
        "resume": "当前分类【简历】：请扮演资深简历优化顾问，基于用户简历指出问题、给出具体修改建议（措辞/量化/结构）、提炼个人亮点；不要编造简历中没有的信息。",
        "interview": "当前分类【面经】：请扮演面试准备教练，基于面经梳理高频考点、给出模拟面试题与答题思路、提醒注意事项。",
    }
    # 面试拷问模式（grill-me）：苏格拉底式面试官，一次一个问题、层层深入
    grill_role = (
        "当前处于【面试拷问模式 Grill Me】。请扮演一位严格但专业的面试官，对用户进行"
        "苏格拉底式拷问式面试，目标是通过层层追问帮用户查漏补缺、把知识讲清楚。\n"
        "行为规则：\n"
        "1. **一次只问一个问题**，绝不同时抛出多个问题。\n"
        "2. 从基础问题开始，根据用户上一轮的回答逐层深入：表面 → 细节 → 原理 → 边界/异常 → 综合应用。\n"
        "3. 每一问都应给出你建议的【推荐答案要点】（简短），让用户确认、纠正或补充，而不是从零写答案。\n"
        "4. 持续追踪用户暴露的知识盲点，优先深挖这些薄弱处；用户答错或含糊时，温和点破并追问到底。\n"
        "5. 当用户说\"总结\"/\"结束\"/\"复盘\"时，输出拷问总结：覆盖的知识点、暴露的薄弱点、建议复习清单。\n"
        "6. 结合知识库面经出题，优先高频考点；若检索到相关面经片段，问题应基于片段。\n"
    )
    if getattr(req, "agent_type", None) == "grill" or (req.agent_type and req.agent_type.value == "grill"):
        role_line = grill_role
    else:
        role_line = rag_roles.get(req.rag_category, "")

    # 历史：按字符预算取最近若干轮 user/assistant 对，超出预算自动截断
    hist, history_truncated = _load_recent_history(cid, db, limit=20)

    # 长期记忆：会话摘要 + 用户画像（尽力而为，失败不影响主流程）
    from app.services import memory_service
    conv = db.get(Conversation, cid)
    summary_block = memory_service.format_summary_block(conv.summary if conv else None)
    usr = db.get(User, user_id)
    profile_block = memory_service.format_profile_block(usr.profile if usr else None)

    sys_txt = (
        "你是「大学生学习与求职智能助手」。角色：耐心、专业、不编造事实。\n"
        + (role_line + "\n" if role_line else "")
        + (profile_block + "\n" if profile_block else "")
        + (summary_block + "\n" if summary_block else "")
        + "规则：\n"
        "1. 如果下面提供了知识库片段，回答尽量以片段内容为依据，并尽量引用（如\"据《xxx》文档…\"）。\n"
        "2. 如果知识库没覆盖，直说\"我没有找到相关资料\"，然后给出通用建议，不要编造。\n"
        "3. 回答用中文，要点清晰，适当分段落，必要时用小标题。\n"
        "4. 如果用户附带图片，先简要描述图片内容，再围绕用户问题作答。\n"
        "5. **工具调用规则**：\n"
        "   - 需要联网搜索时，优先使用 bocha_search（博查 AI，国内可用）；\n"
        "   - duckduckgo_search 在国内网络下通常不可用，只有在 bocha_search 不可用时才考虑；\n"
        "   - 如果某个工具执行失败，换用另一个搜索工具重试一次，不要直接放弃；\n"
        "   - 调用搜索工具时 query 参数必须用中文原文（用户问的就是中文），不要翻译成英文。\n"
    )
    if history_truncated:
        sys_txt += "\n（提示：由于历史消息过长，较早的对话已被截断，仅保留最近内容；但上面的历史摘要已保留关键信息。）\n"
    messages: list = [SystemMessage(content=sys_txt)]

    # 决定是否使用视觉模型：req.image_url 存在 且 当前配了可用视觉 LLM
    use_vision = False
    if req.image_url:
        vision_llm = get_vision_llm()
        use_vision = bool(vision_llm and _llm_supports_vision(vision_llm))

    for h in hist:
        if h.role == "user":
            # 历史消息如果带过 image_url，也以多模态格式还原（仅视觉模型时有效）
            if use_vision and getattr(h, "image_url", None):
                resolved_hist_url = _resolve_image_url(h.image_url)
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": h.content},
                    {"type": "image_url", "image_url": {"url": resolved_hist_url}},
                ]))
                continue
            messages.append(HumanMessage(content=h.content))
        elif h.role == "assistant":
            messages.append(AIMessage(content=h.content))
        # system / tool 先忽略

    # 追加 RAG 上下文 + 当前问题（可能含图片）
    messages.append(_build_user_message(req, ctx_block, use_vision))
    return messages, refs, use_vision, rag_ok


def _run_with_tools(
    llm,
    messages: List[BaseMessage],
    tools: list,
    *,
    max_iter: int = 4,
) -> Tuple[AIMessage, List[dict]]:
    """带工具调用循环的同步执行：llm.invoke → 若 AIMessage.tool_calls 则执行工具
    → 把 ToolMessage 喂回 → 再 invoke，最多 max_iter 轮。

    返回 (最终 AIMessage, 工具调用轨迹)。
    轨迹元素：{name, args, output}。
    """
    if not tools or isinstance(llm, EchoChatModel):
        # Echo 演示模式或没有启用工具：直接 invoke，不做 bind_tools（Echo 不支持）
        if isinstance(llm, EchoChatModel) and tools:
            # 给演示模式答案里挂一行提示，便于用户感知工具存在
            tip = (
                "\n\n（演示模式不支持真实 Function Calling；"
                "配置 DEEPSEEK_API_KEY 后启用工具将自动触发调用）"
            )
        else:
            tip = ""
        resp = llm.invoke(messages)
        if hasattr(resp, "content") and tip:
            resp = AIMessage(content=str(resp.content) + tip)
        return resp, []

    bound = llm.bind_tools(tools) if hasattr(llm, "bind_tools") else llm
    trace: List[dict] = []
    cur_messages = list(messages)
    # 构建一个 tool_name -> BaseTool 的索引（按 BaseTool.name 而非 registry_key）
    # 注意：LLM 返回的 tool_calls 用的是 BaseTool.name，不是我们的 skill_key。
    # 比如 ArxivQueryRun 的 .name 是 'arxiv'，不是 'arxiv_query'。
    tool_by_name = {t.name: t for t in tools}
    for _ in range(max_iter):
        ai_msg = bound.invoke(cur_messages)
        if not getattr(ai_msg, "tool_calls", None):
            return ai_msg, trace
        cur_messages.append(ai_msg)
        # 执行每个 tool_call
        for tc in ai_msg.tool_calls:
            tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
            # 优先在当前用户启用的工具列表里按 BaseTool.name 找
            tool = tool_by_name.get(tool_name)
            # 兜底：在全局 TOOL_INDEX 里按 registry_key 找
            if tool is None:
                tool = skill_service.TOOL_INDEX.get(tool_name)
            if tool is None:
                output = f"工具 {tool_name} 不存在"
            else:
                try:
                    output = tool.invoke(args if isinstance(args, dict) else {"input": args})
                    output = str(output)
                except Exception as e:
                    output = f"工具执行失败：{e}"
            trace.append({"name": tool_name, "args": args, "output": output})
            cur_messages.append(ToolMessage(content=output, tool_call_id=tc_id or tool_name))
        # 继续循环让 LLM 看到工具结果后再决定是否再调
    return ai_msg, trace


def _chunk_text(chunk) -> str:
    """从流式 chunk 提取纯文本片段（兼容 str / list[block] / .text）。"""
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for b in content:
            if isinstance(b, str):
                parts.append(b)
            elif isinstance(b, dict) and isinstance(b.get("text"), str):
                parts.append(b["text"])
        return "".join(parts)
    if hasattr(chunk, "text") and isinstance(chunk.text, str):
        return chunk.text
    return ""


async def _stream_with_tools(
    llm,
    messages: List[BaseMessage],
    tools: list,
    out_trace: list,
    max_iter: int = 4,
):
    """真实流式 + Function Calling。

    与 _run_with_tools（同步 invoke 拿完整答案）不同，这里用 llm.astream 边生成
    边把文本片 yield 出去，达到真流式效果；若模型发起工具调用，则执行工具并把
    ToolMessage 喂回后继续下一轮流式（工具执行期间会有短暂无输出停顿）。
    工具调用轨迹写入 out_trace。
    """
    bound = llm.bind_tools(tools) if hasattr(llm, "bind_tools") else llm
    tool_by_name = {t.name: t for t in tools}
    cur: list = list(messages)
    trace: list[dict] = []
    for _ in range(max_iter):
        agg = None
        async for chunk in bound.astream(cur):
            txt = _chunk_text(chunk)
            if txt:
                # 结构化事件：文本增量
                yield {"type": "text", "content": txt}
            # AIMessageChunk.__add__ 会把 tool_call_chunks 合并成 tool_calls
            agg = chunk if agg is None else agg + chunk
        if agg is None:
            break
        tool_calls = getattr(agg, "tool_calls", None) or []
        if not tool_calls:
            break
        cur.append(agg)
        for tc in tool_calls:
            tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
            # 工具开始事件（前端实时展示“正在调用…”）
            yield {
                "type": "tool",
                "tool": {"name": tool_name, "args": args, "status": "start"},
            }
            tool = tool_by_name.get(tool_name) or skill_service.TOOL_INDEX.get(tool_name)
            if tool is None:
                output = f"工具 {tool_name} 不存在"
            else:
                try:
                    output = str(tool.invoke(args if isinstance(args, dict) else {"input": args}))
                except Exception as e:
                    output = f"工具执行失败：{e}"
            trace.append({"name": tool_name, "args": args, "output": output})
            # 工具结束事件
            yield {
                "type": "tool",
                "tool": {"name": tool_name, "status": "done", "output": _truncate(output, 300)},
            }
            cur.append(ToolMessage(content=output, tool_call_id=tc_id or tool_name))
    out_trace[:] = trace


# ---------- 同步 ----------

def chat_sync(user: User, req: ChatRequest, db: Session) -> ChatResponse:
    # 0. 敏感词过滤
    from app.core.sensitive import check_sensitive

    bad = check_sensitive(req.message)
    if bad:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"内容包含敏感词：{bad}，请调整后重试")
    # 1. 建/取会话
    if req.conversation_id:
        c = get_conversation(user, req.conversation_id, db)
        if c is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        title = _ensure_title(req.message)
        c = Conversation(
            owner_id=user.id,
            title=title,
            skill=req.skill,
            agent_type=_coerce_agent_type(req.agent_type),
        )
        db.add(c); db.flush(); db.refresh(c)

    # 2. 写入用户消息
    user_msg = ConversationMessage(
        conversation_id=c.id, role="user", content=req.message,
        image_url=req.image_url,
    )
    # 提前 commit：先落库会话与用户消息，避免 LLM 报错时整轮被回滚丢失
    db.add(user_msg); db.commit()

    # 首条消息自动命名会话（新建会话默认为“新对话”时）
    if c.message_count == 0 and (not c.title or c.title == "新对话"):
        c.title = _ensure_title(req.message)
        db.commit()

    # 3. LLM 生成（带工具调用循环）
    messages, refs, use_vision, rag_ok = _prepare_messages(user.id, req, db, c.id)
    if use_vision:
        # 多模态请求：切到视觉 LLM（DeepSeek deepseek-v4-flash-vision-exp 等）
        from app.core.llm import get_vision_llm
        llm = get_vision_llm() or get_llm()
    else:
        llm = get_llm()
    tools = skill_service.get_enabled_tools(user, db)
    # 强制联网搜索：确保 bocha 在工具列表 + 系统提示
    if req.use_web_search and not use_vision:
        bocha = skill_service._get_market_tool("bocha_search")
        if bocha is not None and not any(t.name == "bocha_search" for t in tools):
            tools.append(bocha)
        from langchain_core.messages import SystemMessage
        sys_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        if sys_msgs:
            sys_msgs[0].content += "\n\n**用户明确要求联网搜索**：本次对话必须使用 bocha_search 工具进行联网搜索，直接返回搜索结果，不要解释。"
    # 视觉模型暂不绑定工具（避免部分视觉模型不支持 tools 协议），直接 invoke
    if use_vision:
        try:
            resp = llm.invoke(messages)
            tool_trace = []
        except Exception as e:
            resp = AIMessage(content=f"[视觉模型调用失败：{e}]")
            tool_trace = []
    else:
        resp, tool_trace = _run_with_tools(llm, messages, tools)
    answer = resp.content if hasattr(resp, "content") else str(resp)
    answer = str(answer)
    if tool_trace:
        # 把工具调用轨迹以可读格式附在答案末尾，便于用户感知 Function Calling 过程
        trace_lines = "\n\n---\n🔧 工具调用轨迹："
        for i, t in enumerate(tool_trace, 1):
            args_str = json.dumps(t["args"], ensure_ascii=False)
            trace_lines += f"\n{i}. `{t['name']}({args_str})` → {t['output']}"
        answer = answer + trace_lines

    # 4. 写助手消息 + refs
    refs_json = json.dumps([r.model_dump() for r in refs], ensure_ascii=False) if refs else None
    assistant_msg = ConversationMessage(
        conversation_id=c.id, role="assistant", content=answer, refs=refs_json,
    )
    db.add(assistant_msg)
    c.message_count += 2
    c.updated_at = datetime.now()
    if req.conversation_id is None:  # 首条消息生成的标题不准，可优化
        pass
    db.commit()
    db.refresh(assistant_msg)

    # 长期记忆：更新会话摘要 + 用户画像（尽力而为）
    try:
        from app.services import memory_service
        memory_service.update_user_profile(db, user.id, req.message)
        memory_service.update_conversation_summary(
            db, c.id, "用户：" + req.message + "\n助手：" + answer
        )
    except Exception:
        pass

    return ChatResponse(
        conversation_id=c.id,
        message_id=assistant_msg.id,
        answer=answer,
        refs=[r.model_dump() for r in refs],
        rag_ok=rag_ok,
    )


# ---------- 流式（SSE 事件）----------

def _sse(event: str, data: str) -> str:
    """一个标准 SSE 帧。"""
    lines = []
    if event:
        lines.append(f"event: {event}")
    for line in (data or "").splitlines():
        lines.append(f"data: {line}")
    lines.append("")  # 空行分隔
    return "\n".join(lines) + "\n"


async def chat_stream(user: User, req: ChatRequest, db: Session) -> AsyncIterator[str]:
    # 0. 敏感词过滤
    from app.core.sensitive import check_sensitive

    bad = check_sensitive(req.message)
    if bad:
        yield _sse("error", json.dumps(
            {"detail": f"内容包含敏感词：{bad}，请调整后重试"}, ensure_ascii=False,
        ))
        return
    # 1. 建/取会话
    if req.conversation_id:
        c = get_conversation(user, req.conversation_id, db)
        if c is None:
            yield _sse("error", json.dumps({"detail": "会话不存在"}, ensure_ascii=False))
            return
    else:
        title = _ensure_title(req.message)
        c = Conversation(
            owner_id=user.id,
            title=title,
            skill=req.skill,
            agent_type=_coerce_agent_type(req.agent_type),
        )
        db.add(c); db.flush(); db.refresh(c)

    # 2. 用户消息入库
    user_msg = ConversationMessage(
        conversation_id=c.id, role="user", content=req.message,
        image_url=req.image_url,
    )
    # 提前 commit：先落库会话与用户消息，避免 LLM 中途报错时整轮被回滚丢失
    db.add(user_msg); db.commit(); db.refresh(c)

    # 首条消息自动命名会话（新建会话默认为“新对话”时）
    if c.message_count == 0 and (not c.title or c.title == "新对话"):
        c.title = _ensure_title(req.message)
        db.commit()
        db.refresh(c)

    # 3. 发 start 事件（带 conversation_id / refs）
    messages, refs, use_vision, rag_ok = _prepare_messages(user.id, req, db, c.id)
    refs_payload = [r.model_dump() for r in refs]
    yield _sse("start", json.dumps(
        {"conversation_id": c.id, "refs": refs_payload, "rag_ok": rag_ok}, ensure_ascii=False,
    ))

    # 4. 生成（带工具调用循环）。如果有启用的工具，走 _run_with_tools 同步执行
    #    拿到完整答案后切片伪流式吐出；否则走 llm.astream 真实流式。
    #    多模态（use_vision=True）请求切到视觉 LLM，且暂不绑定 tools（视觉模型多不支持 tools）。
    if use_vision:
        from app.core.llm import get_vision_llm
        llm = get_vision_llm() or get_llm()
        tools = []
    else:
        llm = get_llm()
        tools = skill_service.get_enabled_tools(user, db)
        # 如果用户勾选了「强制联网搜索」，确保 bocha_search 在工具列表里
        if req.use_web_search:
            bocha = skill_service._get_market_tool("bocha_search")
            if bocha is not None and not any(t.name == "bocha_search" for t in tools):
                tools.append(bocha)
            # 追加系统提示，告诉 LLM 必须用 bocha
            from langchain_core.messages import SystemMessage
            sys_msgs = [m for m in messages if isinstance(m, SystemMessage)]
            if sys_msgs:
                sys_msgs[0].content += "\n\n**用户明确要求联网搜索**：本次对话必须使用 bocha_search 工具进行联网搜索，直接返回搜索结果，不要解释。"
    full_parts: list[str] = []
    tool_trace_stream: list[dict] = []
    try:
        if use_vision:
            # 视觉模型：直接 invoke 拿完整答案，再切片伪流式
            import asyncio as _asyncio
            try:
                ai_msg = llm.invoke(messages)
                full_answer = (
                    ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
                )
                full_answer = str(full_answer)
            except Exception as e:
                full_answer = f"[视觉模型调用失败：{e}]"
            step = 4
            for i in range(0, len(full_answer), step):
                await _asyncio.sleep(0.02)
                piece = full_answer[i : i + step]
                full_parts.append(piece)
                yield _sse("delta", json.dumps({"content": piece}, ensure_ascii=False))
        elif tools:
            # 工具调用：真实流式 + Function Calling。
            # 文本随 LLM 生成即吐（真流式）；工具开始/结束发独立 tool 事件，前端实时展示。
            async for ev in _stream_with_tools(llm, messages, tools, tool_trace_stream):
                if ev["type"] == "text":
                    piece = ev["content"]
                    if piece:
                        full_parts.append(piece)
                        yield _sse("delta", json.dumps({"content": piece}, ensure_ascii=False))
                elif ev["type"] == "tool":
                    yield _sse("tool", json.dumps({"tool": ev["tool"]}, ensure_ascii=False))
        else:
            # 无工具：走真实 astream
            async for chunk in llm.astream(messages):
                # 优先：AIMessageChunk.content (str | list[block])
                if hasattr(chunk, "content"):
                    content = chunk.content
                    if isinstance(content, str):
                        txt = content
                    elif isinstance(content, list):
                        parts_i: list[str] = []
                        for b in content:
                            if isinstance(b, str):
                                parts_i.append(b)
                            elif isinstance(b, dict) and isinstance(b.get("text"), str):
                                parts_i.append(b["text"])
                        txt = "".join(parts_i)
                    else:
                        txt = str(content)
                elif hasattr(chunk, "text") and isinstance(chunk.text, str):
                    txt = chunk.text
                else:
                    txt = str(chunk)
                if txt:
                    full_parts.append(str(txt))
                    yield _sse("delta", json.dumps({"content": str(txt)}, ensure_ascii=False))
    except Exception as e:
        yield _sse("error", json.dumps({"detail": f"LLM 错误：{e}"}, ensure_ascii=False))
        return

    answer = "".join(full_parts)

    # 5. 入库 + end 事件
    refs_json = json.dumps(refs_payload, ensure_ascii=False) if refs else None
    assistant_msg = ConversationMessage(
        conversation_id=c.id, role="assistant", content=answer, refs=refs_json,
    )
    db.add(assistant_msg)
    c.message_count += 2
    c.updated_at = datetime.now()
    db.commit()
    db.refresh(assistant_msg)

    # 长期记忆：更新会话摘要 + 用户画像（尽力而为，失败不影响 SSE 收尾）
    try:
        from app.services import memory_service
        memory_service.update_user_profile(db, user.id, req.message)
        memory_service.update_conversation_summary(
            db, c.id, "用户：" + req.message + "\n助手：" + answer
        )
    except Exception:
        pass

    yield _sse("end", json.dumps({
        "conversation_id": c.id,
        "message_id": assistant_msg.id,
        "chars": len(answer),
        "tool_calls": tool_trace_stream,
    }, ensure_ascii=False))
    # 避免 uvicorn / starlette 在 SSE 结束后过早关闭 chunked 传输，
    # 导致客户端抛出 "Response ended prematurely"。这里再吐一个 0 字节
    # SSE 帧作为 flush 提示。
    yield _sse("", "")
