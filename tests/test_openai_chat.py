import unittest
from unittest.mock import patch

from backend.app.services.openai_chat import OpenAIChatClient, OpenAIChatError


class OpenAIChatClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_chat_sends_openai_compatible_payload_and_yields_deltas(self):
        transport = FakeStreamingTransport(
            [
                'data: {"choices":[{"delta":{"content":"你好"}}]}',
                'data: {"choices":[{"delta":{"content":"，世界"}}]}',
                "data: [DONE]",
            ]
        )
        client = OpenAIChatClient(
            api_key="test-key",
            base_url="https://example.com/v1",
            model="demo-model",
            transport=transport,
        )

        chunks = [chunk async for chunk in client.stream_chat([{"role": "user", "content": "回答问题"}])]

        self.assertEqual(chunks, ["你好", "，世界"])
        self.assertEqual(transport.url, "https://example.com/v1/chat/completions")
        self.assertEqual(transport.headers["Authorization"], "Bearer test-key")
        self.assertEqual(transport.payload["model"], "demo-model")
        self.assertTrue(transport.payload["stream"])
        self.assertEqual(transport.payload["messages"][0]["content"], "回答问题")

    async def test_stream_chat_requires_generation_configuration(self):
        client = OpenAIChatClient(api_key="", base_url="", model="")

        with self.assertRaisesRegex(OpenAIChatError, "OPENAI_API_KEY"):
            _ = [chunk async for chunk in client.stream_chat([{"role": "user", "content": "hello"}])]

    def test_uses_siliconflow_configuration_as_generation_fallback(self):
        values = {
            "OPENAI_API_KEY": "",
            "OPENAI_BASE_URL": "",
            "OPENAI_MODEL": "",
            "SILICONFLOW_API_KEY": "silicon-key",
            "SILICONFLOW_BASE_URL": "https://api.siliconflow.cn/v1",
        }
        with (
            patch("backend.app.services.openai_chat.get_effective_chat_model_config", return_value=None),
            patch(
                "backend.app.services.openai_chat.get_config_value",
                side_effect=lambda name, default="": values.get(name, default) or default,
            ),
        ):
            client = OpenAIChatClient()

        self.assertEqual(client.api_key, "silicon-key")
        self.assertEqual(client.base_url, "https://api.siliconflow.cn/v1")
        self.assertEqual(client.model, "Qwen/Qwen3-8B")

    def test_uses_saved_chat_model_settings_before_environment_fallback(self):
        with patch(
            "backend.app.services.openai_chat.get_effective_chat_model_config",
            return_value=("deepseek-secret", "https://api.deepseek.com", "deepseek-chat", 90),
        ):
            client = OpenAIChatClient()

        self.assertEqual(client.api_key, "deepseek-secret")
        self.assertEqual(client.base_url, "https://api.deepseek.com")
        self.assertEqual(client.model, "deepseek-chat")
        self.assertEqual(client.timeout_seconds, 90)

    async def test_does_not_mix_partial_openai_configuration_with_siliconflow(self):
        values = {
            "OPENAI_API_KEY": "deepseek-key",
            "OPENAI_BASE_URL": "",
            "OPENAI_MODEL": "deepseek-chat",
            "SILICONFLOW_API_KEY": "silicon-key",
            "SILICONFLOW_BASE_URL": "https://api.siliconflow.cn/v1",
        }
        with (
            patch("backend.app.services.openai_chat.get_effective_chat_model_config", return_value=None),
            patch(
                "backend.app.services.openai_chat.get_config_value",
                side_effect=lambda name, default="": values.get(name, default),
            ),
        ):
            client = OpenAIChatClient()

        self.assertEqual(client.api_key, "deepseek-key")
        self.assertEqual(client.base_url, "")
        self.assertEqual(client.model, "deepseek-chat")
        with self.assertRaisesRegex(OpenAIChatError, "OPENAI_BASE_URL"):
            _ = [chunk async for chunk in client.stream_chat([{"role": "user", "content": "hello"}])]


class FakeStreamingTransport:
    def __init__(self, lines):
        self.lines = lines
        self.url = ""
        self.headers = {}
        self.payload = {}
        self.timeout = 0

    def __call__(self, url, headers, payload, timeout):
        self.url = url
        self.headers = headers
        self.payload = payload
        self.timeout = timeout
        return iter(self.lines)


if __name__ == "__main__":
    unittest.main()
