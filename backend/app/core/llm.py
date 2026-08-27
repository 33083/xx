"""LLM 工厂：优先 DeepSeek/OpenAI/DashScope；缺 key 则 EchoChatModel 兜底。"""
from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.config import settings


class EchoChatModel(BaseChatModel):
    model: str = "echo-demo"

    @property
    def _llm_type(self) -> str:
        return "echo-demo"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model}

    def _generate(
        self, messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_human = ""
        has_ctx = False
        has_image = False
        for m in reversed(messages):
            if isinstance(m, HumanMessage) and not last_human:
                # content 可能是 str（纯文本）或 list[dict]（多模态）
                c = m.content
                if isinstance(c, list):
                    text_parts = []
                    for b in c:
                        if isinstance(b, dict):
                            if b.get("type") == "text":
                                text_parts.append(b.get("text", ""))
                            elif b.get("type") == "image_url":
                                has_image = True
                    last_human = "".join(text_parts)
                else:
                    last_human = str(c)
            text = str(m.content)
            if "参考以下上下文" in text or "知识库检索片段" in text:
                has_ctx = True
                break
        ctx_note = "[已检索到 RAG 上下文]\n" if has_ctx else ""
        image_note = "[用户附带了一张图片]\n" if has_image else ""
        answer = (
            "[演示模式：LLM API Key 未配置，当前使用 echo 演示模式]\n\n"
            f"你的问题：{last_human or '(空)'}\n\n"
            f"{ctx_note}{image_note}"
            "在 backend/.env 里填好 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 后会切到真实大模型。"
            "当前演示已能验证：上传 → 切片 → 向量化 → 检索 → SSE 流式，整条链路可用。"
        )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=answer))])

    def _stream(
        self, messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        import time
        # _generate 返回 ChatGeneration，其 message 是 AIMessage（非 Chunk）。
        # 而 ChatGenerationChunk.message 必须是 BaseMessageChunk 子类，不能直接
        # 把 AIMessage 塞进去，否则 pydantic v2 会抛 model_type 校验错误。
        # 所以这里直接拿字符串 content，然后逐段构造 AIMessageChunk。
        full = (
            self._generate(messages, stop=stop, run_manager=run_manager)
            .generations[0]
            .message.content
            or ""
        )
        if not isinstance(full, str):
            # content 有时是 list[dict]（结构化输出），转成字符串安全兜底
            full = str(full)
        step = 2
        for i in range(0, len(full), step):
            time.sleep(0.03)
            yield ChatGenerationChunk(message=AIMessageChunk(content=full[i : i + step]))

    async def _astream(
        self, messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        full = (
            self._generate(messages, stop=stop, run_manager=run_manager)
            .generations[0]
            .message.content
            or ""
        )
        if not isinstance(full, str):
            full = str(full)
        step = 2
        for i in range(0, len(full), step):
            await asyncio.sleep(0.02)
            yield ChatGenerationChunk(message=AIMessageChunk(content=full[i : i + step]))


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """文本对话 LLM（默认 DeepSeek deepseek-chat）。"""
    provider = (settings.LLM_PROVIDER or "").lower().strip()

    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                model=settings.LLM_MODEL or settings.DEEPSEEK_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        except Exception:
            pass

    if provider == "openai" and settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.LLM_MODEL or "gpt-4o-mini",
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        except Exception:
            pass

    if provider == "dashscope" and settings.DASHSCOPE_API_KEY:
        try:
            from langchain_community.chat_models.tongyi import ChatTongyi
            return ChatTongyi(
                dashscope_api_key=settings.DASHSCOPE_API_KEY,
                model=settings.LLM_MODEL or "qwen-plus",
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        except Exception:
            pass

    return EchoChatModel()


@lru_cache(maxsize=1)
def get_vision_llm() -> Optional[BaseChatModel]:
    """视觉 LLM：仅在用户消息带 image_url 时使用。

    返回 None 表示没有可用的视觉模型（调用方应回退到 get_llm() 走文本降级）。
    DeepSeek 视觉模型：deepseek-v4-flash-vision-exp（OpenAI 兼容格式）。
    """
    provider = (settings.LLM_PROVIDER or "").lower().strip()

    # DeepSeek 视觉模型：base_url 与文本一致，仅 model 名不同
    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                model=settings.DEEPSEEK_VISION_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        except Exception:
            return None

    # OpenAI gpt-4o 系列
    if provider == "openai" and settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model="gpt-4o-mini",
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        except Exception:
            return None

    return None
