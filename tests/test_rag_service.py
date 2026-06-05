import unittest
from unittest.mock import patch

from backend.app.schemas.query_routing import QueryIntent, QueryRoute
from backend.app.schemas.retrieval import RetrievalResult, RetrievalSearchResult
from backend.app.services.rag_service import build_rag_messages, stream_rag_answer


class RagServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_numbered_context_and_streams_answer_with_sources(self):
        retrieval = _retrieval_result()
        client = FakeChatClient(["职责是制定研究大纲", " [1]。"])

        events = [
            event async for event in stream_rag_answer(
                question="ChiefArchitect 的职责是什么？",
                top_k=3,
                retrieve=lambda question, top_k: retrieval,
                chat_client=client,
            )
        ]

        self.assertEqual(events[0], {"event": "status", "data": {"state": "thinking"}})
        self.assertEqual(events[1]["event"], "routing")
        self.assertEqual(events[1]["data"]["intent"], "knowledge_query")
        self.assertEqual(events[2]["event"], "sources")
        self.assertEqual(events[2]["data"]["sources"][0]["citation"], 1)
        self.assertEqual(events[3], {"event": "status", "data": {"state": "answering"}})
        self.assertEqual(events[4], {"event": "delta", "data": {"content": "职责是制定研究大纲"}})
        self.assertEqual(events[-1], {"event": "done", "data": {"state": "success"}})
        self.assertIn("[1]", client.messages[1]["content"])
        self.assertIn("只能根据提供的资料回答", client.messages[0]["content"])

    async def test_empty_retrieval_returns_insufficient_answer_without_calling_model(self):
        retrieval = RetrievalResult(
            query="unknown",
            top_k=5,
            collection_name="knowrag_chunks",
            total=0,
            results=[],
        )
        client = FakeChatClient(["should not be used"])

        events = [
            event async for event in stream_rag_answer(
                question="unknown",
                retrieve=lambda question, top_k: retrieval,
                chat_client=client,
                route=lambda question: _route(QueryIntent.KNOWLEDGE_QUERY),
            )
        ]

        self.assertEqual(events[2], {"event": "sources", "data": {"sources": []}})
        self.assertEqual(events[3]["event"], "delta")
        self.assertIn("没有找到足够信息", events[3]["data"]["content"])
        self.assertEqual(events[-1], {"event": "done", "data": {"state": "empty"}})
        self.assertEqual(client.messages, None)

    async def test_low_score_retrieval_returns_insufficient_answer_without_calling_model(self):
        retrieval = _retrieval_result(score=0.24)
        client = FakeChatClient(["should not be used"])

        events = [
            event async for event in stream_rag_answer(
                question="不相关的问题",
                retrieve=lambda question, top_k: retrieval,
                chat_client=client,
                min_score=0.55,
                route=lambda question: _route(QueryIntent.KNOWLEDGE_QUERY),
            )
        ]

        self.assertEqual(events[2], {"event": "sources", "data": {"sources": []}})
        self.assertEqual(events[-1], {"event": "done", "data": {"state": "empty"}})
        self.assertEqual(client.messages, None)

    async def test_only_passes_retrieval_results_above_minimum_score_to_model(self):
        retrieval = _retrieval_result(score=0.91)
        retrieval.results.append(_retrieval_result(score=0.31).results[0])
        client = FakeChatClient(["答案 [1]"])

        events = [
            event async for event in stream_rag_answer(
                question="ChiefArchitect 的职责是什么？",
                retrieve=lambda question, top_k: retrieval,
                chat_client=client,
                min_score=0.55,
            )
        ]

        self.assertEqual(len(events[2]["data"]["sources"]), 1)
        self.assertNotIn("[2]", client.messages[1]["content"])

    async def test_default_minimum_score_uses_calibrated_value(self):
        retrieval = _retrieval_result(score=0.52)
        client = FakeChatClient(["答案 [1]"])

        with patch(
            "backend.app.services.rag_service.get_config_value",
            side_effect=lambda name, default="": default,
        ):
            events = [
                event async for event in stream_rag_answer(
                    question="ChiefArchitect 的职责是什么？",
                    retrieve=lambda question, top_k: retrieval,
                    chat_client=client,
                )
            ]

        self.assertEqual(events[-1], {"event": "done", "data": {"state": "success"}})

    async def test_casual_chat_skips_retrieval_and_streams_direct_answer(self):
        retrieval_calls = []
        client = FakeChatClient(["你好，我是你的知识助手。"])

        events = [
            event async for event in stream_rag_answer(
                question="你好",
                retrieve=lambda question, top_k: retrieval_calls.append((question, top_k)),
                chat_client=client,
                route=lambda question: _route(QueryIntent.CASUAL_CHAT),
            )
        ]

        self.assertEqual(events[1]["event"], "routing")
        self.assertEqual(events[1]["data"]["intent"], "casual_chat")
        self.assertEqual(events[2], {"event": "sources", "data": {"sources": []}})
        self.assertEqual(retrieval_calls, [])
        self.assertNotIn("资料：", client.messages[1]["content"])
        self.assertEqual(events[-1], {"event": "done", "data": {"state": "success"}})

    def test_build_rag_messages_includes_source_metadata(self):
        messages = build_rag_messages("问题", _retrieval_result().results)

        self.assertIn("[1] 文档：ChiefArchitect", messages[1]["content"])
        self.assertIn("标题：Agent > 职责", messages[1]["content"])
        self.assertIn("行号：10-20", messages[1]["content"])


class FakeChatClient:
    def __init__(self, deltas):
        self.deltas = deltas
        self.messages = None

    async def stream_chat(self, messages):
        self.messages = messages
        for delta in self.deltas:
            yield delta


def _retrieval_result(score=0.91):
    return RetrievalResult(
        query="ChiefArchitect 的职责是什么？",
        top_k=3,
        collection_name="knowrag_chunks",
        total=1,
        results=[
            RetrievalSearchResult(
                chunk_id="chief:0001",
                score=score,
                document_title="ChiefArchitect",
                source_path="docs/chief.md",
                heading_path=("Agent", "职责"),
                content="ChiefArchitect 负责制定研究大纲。",
                token_count=15,
                start_line=10,
                end_line=20,
            )
        ],
    )


async def _route(intent):
    return QueryRoute(intent=intent, confidence=1.0, reason="test", method="rule")


if __name__ == "__main__":
    unittest.main()
