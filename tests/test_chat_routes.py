import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


class ChatRoutesTest(unittest.TestCase):
    def test_admin_route_returns_existing_management_console(self):
        response = client.get("/admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("KnowRAG Admin Console", response.text)
        self.assertIn('src="/admin/app.js"', response.text)

    def test_admin_script_route_returns_management_console_javascript(self):
        response = client.get("/admin/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("API_BASE_URL", response.text)

    def test_chat_stream_route_returns_sse_events(self):
        with patch(
            "backend.app.api.chat.stream_rag_answer",
            return_value=_async_events(
                {"event": "status", "data": {"state": "thinking"}},
                {"event": "routing", "data": {"intent": "knowledge_query", "confidence": 1.0, "method": "rule"}},
                {"event": "delta", "data": {"content": "答案"}},
                {"event": "done", "data": {"state": "success"}},
            ),
        ):
            response = client.post(
                "/api/chat/stream",
                json={"question": "测试问题", "top_k": 5},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertIn("event: status\ndata: {\"state\": \"thinking\"}", response.text)
        self.assertIn("event: routing\ndata: {\"intent\": \"knowledge_query\"", response.text)
        self.assertIn("event: delta\ndata: {\"content\": \"答案\"}", response.text)
        self.assertIn("event: done\ndata: {\"state\": \"success\"}", response.text)

    def test_chat_stream_route_rejects_whitespace_only_question(self):
        response = client.post(
            "/api/chat/stream",
            json={"question": "   \n\t", "top_k": 5},
        )

        self.assertEqual(response.status_code, 422)

    def test_chat_stream_route_rejects_question_longer_than_desktop_limit(self):
        response = client.post(
            "/api/chat/stream",
            json={"question": "a" * 1001, "top_k": 5},
        )

        self.assertEqual(response.status_code, 422)

    def test_chat_stream_route_does_not_expose_internal_error_details(self):
        with patch(
            "backend.app.api.chat.stream_rag_answer",
            side_effect=RuntimeError("secret provider response"),
        ):
            response = client.post(
                "/api/chat/stream",
                json={"question": "测试问题", "top_k": 5},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: error", response.text)
        self.assertNotIn("secret provider response", response.text)


async def _async_events(*events):
    for event in events:
        yield event


if __name__ == "__main__":
    unittest.main()
