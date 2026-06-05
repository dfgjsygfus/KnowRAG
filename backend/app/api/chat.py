from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.schemas.chat import ChatStreamRequest
from backend.app.services.rag_service import stream_rag_answer


router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)
GENERIC_CHAT_ERROR = "问答服务暂时不可用，请稍后重试。"


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest) -> StreamingResponse:
    """Stream a grounded single-turn answer for the desktop pet."""

    return StreamingResponse(
        _safe_sse_stream(request.question, request.top_k),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _safe_sse_stream(question: str, top_k: int) -> AsyncIterator[str]:
    try:
        async for item in stream_rag_answer(question=question, top_k=top_k):
            yield _format_sse(item)
    except Exception:
        logger.exception("Chat stream failed")
        yield _format_sse({"event": "error", "data": {"message": GENERIC_CHAT_ERROR}})


def _format_sse(item: dict[str, Any]) -> str:
    event = str(item.get("event") or "message")
    data = json.dumps(item.get("data") or {}, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"
