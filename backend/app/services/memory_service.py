"""长期记忆服务：会话摘要记忆 + 用户画像记忆。

- 会话摘要：每轮对话后用 LLM 把「旧摘要 + 本轮对话」滚动压缩成新摘要，存入
  conversations.summary。注入系统提示后，即使历史消息被截断，模型仍能记住很早之前的内容。
- 用户画像：从用户发言中提取个人背景（专业/目标/偏好等），合并进 users.profile，
  跨会话复用，让助手记住"你是谁"。

Echo 演示模式（未配置 LLM Key）下不调用 LLM，退化为安全降级逻辑，不阻塞主流程。
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.llm import EchoChatModel, get_llm
from app.models.conversation import Conversation
from app.models.user import User

# 摘要/画像的字符上限（防止无限膨胀）
SUMMARY_MAX = 4000
PROFILE_MAX = 3000


def _is_echo(llm) -> bool:
    return isinstance(llm, EchoChatModel)


def _invoke_text(llm, system: str, user: str) -> str:
    """调用 LLM 拿纯文本回复；任何异常都返回空串（调用方自行降级）。"""
    from langchain_core.messages import HumanMessage, SystemMessage

    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return str(getattr(resp, "content", "") or "").strip()


# ---------------------------------------------------------------------------
# 会话摘要记忆
# ---------------------------------------------------------------------------

def update_conversation_summary(db: Session, cid: int, exchange: str) -> None:
    """根据「旧摘要 + 本轮对话」滚动更新会话摘要（尽力而为，失败不影响主流程）。

    exchange 为本轮 user 提问 + assistant 回答的文本。
    """
    c = db.get(Conversation, cid)
    if c is None:
        return
    old = (c.summary or "").strip()
    llm = get_llm()
    try:
        if _is_echo(llm):
            # 演示模式：不调 LLM，直接拼接截断，保证有摘要可用
            text = (old + "\n" + exchange).strip()
            new_summary = text[-SUMMARY_MAX:]
        else:
            prompt = (
                "你是对话摘要器。请把「历史摘要」和「新对话」合并成一段精简的中文摘要：\n"
                "1. 保留所有关键信息：用户身份、目标、偏好、重要事实、关键结论、待办事项。\n"
                "2. 删除寒暄、重复、无关细节。\n"
                "3. 只输出摘要正文，不要任何前缀、标题或解释。\n\n"
                f"【历史摘要】\n{old or '（无）'}\n\n"
                f"【新对话】\n{exchange}\n"
            )
            new_summary = _invoke_text(
                llm, "你是专业的中文对话摘要器。", prompt
            ) or exchange[-SUMMARY_MAX:]
            new_summary = new_summary[-SUMMARY_MAX:]
    except Exception:
        new_summary = (old + "\n" + exchange).strip()[-SUMMARY_MAX:]

    if new_summary != old:
        c.summary = new_summary
        db.commit()


def format_summary_block(summary: str | None) -> str:
    """把摘要格式化为系统提示片段；无摘要返回空串。"""
    s = (summary or "").strip()
    if not s:
        return ""
    return f"【历史对话摘要】\n{s}\n（以上是对较早对话的压缩摘要，可基于它回答涉及之前内容的问题）"


# ---------------------------------------------------------------------------
# 用户画像记忆
# ---------------------------------------------------------------------------

_PROFILE_KEYS_HINT = (
    "专业, 年级, 学校, 城市, 求职方向, 目标岗位, 技术栈, 项目方向, "
    "学习目标, 考研/考公/出国, 个人情况, 偏好, 其他"
)


def _parse_profile_json(text: str, old: dict) -> dict:
    """从 LLM 输出里安全解析 JSON 画像；失败则返回旧画像。"""
    t = (text or "").strip()
    if not t:
        return old
    # 去掉可能的 ```json 包裹
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:].strip()
    try:
        obj = json.loads(t)
    except Exception:
        # 尝试截取第一个 { 到最后一个 }
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            try:
                obj = json.loads(t[a : b + 1])
            except Exception:
                return old
        else:
            return old
    if not isinstance(obj, dict):
        return old
    merged = dict(old)
    for k, v in obj.items():
        if v is None or v == "" or v == []:
            continue
        key = str(k).strip()
        if not key:
            continue
        merged[key] = v
    return merged


def update_user_profile(db: Session, user_id: int, user_message: str) -> None:
    """从用户发言中提取个人画像并与旧画像合并（尽力而为）。

    只在消息看起来包含个人信息时才调用 LLM；明显是普通提问时直接跳过，
    避免每次对话都消耗一次 LLM 调用。
    """
    u = db.get(User, user_id)
    if u is None:
        return
    msg = (user_message or "").strip()
    if not msg or len(msg) > 500:
        return
    # 粗略判断：包含个人指代或背景词才值得提取
    hints = ("我是", "我学", "我读", "我大", "我今年", "我考", "我找", "我想",
             "专业", "年级", "毕业", "求职", "实习", "考研", "考公", "目标",
             "我的", "本科", "硕士", "博士", "学校", "老师")
    if not any(h in msg for h in hints):
        return

    old = {}
    if u.profile:
        try:
            old = json.loads(u.profile)
        except Exception:
            old = {}
    if not isinstance(old, dict):
        old = {}

    llm = get_llm()
    if _is_echo(llm):
        return  # 演示模式不做画像提取，避免幻觉
    try:
        prompt = (
            "从用户的发言中提取关于用户本人的背景信息，与已有画像合并去重。\n"
            "提取维度参考：" + _PROFILE_KEYS_HINT + "\n"
            "规则：只提取发言中明确体现的信息，不要编造；同一信息以新发言为准；"
            "不相关的维度不要出现。\n"
            "只输出一个 JSON 对象，键为维度名，值为字符串或字符串数组，不要任何其它文字。\n\n"
            f"【已有画像】\n{json.dumps(old, ensure_ascii=False)}\n\n"
            f"【用户发言】\n{msg}\n"
        )
        text = _invoke_text(llm, "你是用户画像信息提取器，只输出 JSON。", prompt)
        merged = _parse_profile_json(text, old)
    except Exception:
        return

    if merged:
        u.profile = json.dumps(merged, ensure_ascii=False)
        db.commit()


def format_profile_block(profile: str | None) -> str:
    """把画像格式化为系统提示片段；无画像返回空串。"""
    p = (profile or "").strip()
    if not p:
        return ""
    try:
        obj = json.loads(p)
    except Exception:
        return ""
    if not isinstance(obj, dict) or not obj:
        return ""
    lines = []
    for k, v in obj.items():
        if isinstance(v, (list, tuple)):
            lines.append(f"- {k}：" + "、".join(str(i) for i in v))
        else:
            lines.append(f"- {k}：{v}")
    return "【用户画像】\n" + "\n".join(lines)
