from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from backend.app.schemas.query_routing import QueryIntent, QueryRoute
from backend.app.schemas.retrieval import RetrievalResult, RetrievalSearchResult
from backend.app.services.app_config import get_config_value
from backend.app.services.openai_chat import OpenAIChatClient
from backend.app.services.query_router import route_query
from backend.app.services.retrieval_service import retrieve_query


INSUFFICIENT_ANSWER = "我在资料里没有找到足够信息，暂时无法回答这个问题。"


async def stream_rag_answer(
    question: str,
    top_k: int = 5,
    retrieve: Callable[[str, int], RetrievalResult] | None = None,
    chat_client: OpenAIChatClient | None = None,
    min_score: float | None = None,
    route: Callable[[str], Awaitable[QueryRoute]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Retrieve context and yield desktop-pet friendly answer events."""

    normalized_question = question.strip()
    yield {"event": "status", "data": {"state": "thinking"}}

    query_route = await (route or route_query)(normalized_question)
    yield {"event": "routing", "data": _route_payload(query_route)}

    if query_route.intent == QueryIntent.CASUAL_CHAT:
        yield {"event": "sources", "data": {"sources": []}}
        yield {"event": "status", "data": {"state": "answering"}}
        async for delta in (chat_client or OpenAIChatClient()).stream_chat(build_casual_chat_messages(normalized_question)):
            yield {"event": "delta", "data": {"content": delta}}
        yield {"event": "done", "data": {"state": "success"}}
        return

    retrieval = (retrieve or retrieve_query)(normalized_question, top_k)
    relevant_results = [
        item for item in retrieval.results
        if item.score >= (min_score if min_score is not None else _configured_min_score())
    ]
    sources = [_source_payload(item, index) for index, item in enumerate(relevant_results, start=1)]
    yield {"event": "sources", "data": {"sources": sources}}

    if not relevant_results:
        yield {"event": "delta", "data": {"content": INSUFFICIENT_ANSWER}}
        yield {"event": "done", "data": {"state": "empty"}}
        return

    yield {"event": "status", "data": {"state": "answering"}}
    messages = build_rag_messages(normalized_question, relevant_results)
    async for delta in (chat_client or OpenAIChatClient()).stream_chat(messages):
        yield {"event": "delta", "data": {"content": delta}}
    yield {"event": "done", "data": {"state": "success"}}


def build_rag_messages(question: str, results: list[RetrievalSearchResult]) -> list[dict[str, str]]:
    """Build a grounded single-turn prompt with numbered sources."""

    contexts = []
    for index, result in enumerate(results, start=1):
        heading = " > ".join(result.heading_path) or "无"
        contexts.append(
            "\n".join(
                [
                    f"[{index}] 文档：{result.document_title or result.source_path}",
                    f"路径：{result.source_path}",
                    f"标题：{heading}",
                    f"行号：{result.start_line}-{result.end_line}",
                    f"内容：{result.content}",
                ]
            )
        )

    return [
        {
            "role": "system",
            "content": (
                "你是一个桌面知识助手。只能根据提供的资料回答，不得编造。"
                "回答时使用 [1]、[2] 这样的编号引用资料。"
                "如果资料不足，明确说明资料不足。"
            ),
        },
        {
            "role": "user",
            "content": f"问题：{question}\n\n资料：\n\n" + "\n\n".join(contexts),
        },
    ]


def build_casual_chat_messages(question: str) -> list[dict[str, str]]:
    """构造不访问知识库的简短闲聊 Prompt。"""

    return [
        {
            "role": "system",
            "content": "你是一个友好、简洁的桌面知识助手。当前是普通闲聊，不要声称查询了知识库。",
        },
        {"role": "user", "content": question},
    ]


def _source_payload(result: RetrievalSearchResult, citation: int) -> dict[str, Any]:
    return {
        "citation": citation,
        "chunk_id": result.chunk_id,
        "score": result.score,
        "document_title": result.document_title,
        "source_path": result.source_path,
        "heading_path": list(result.heading_path),
        "content": result.content,
        "start_line": result.start_line,
        "end_line": result.end_line,
    }


def _route_payload(route: QueryRoute) -> dict[str, Any]:
    return {
        "intent": route.intent.value,
        "confidence": route.confidence,
        "reason": route.reason,
        "method": route.method,
    }


def _configured_min_score() -> float:
    value = get_config_value("RAG_MIN_SCORE", "0.50")
    return float(value)
