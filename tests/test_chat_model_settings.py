import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.app.services.chat_model_settings import (
    DEFAULT_CHAT_MODEL_SETTINGS,
    chat_model_settings_response,
    get_effective_chat_model_config,
    load_chat_model_settings,
    save_chat_model_settings,
)
from backend.app.services.openai_chat import OpenAIChatError
from main import app


class ChatModelSettingsTest(unittest.TestCase):
    def test_save_and_load_chat_model_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            payload = {
                "provider": "deepseek",
                "api_key": "deepseek-secret",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "timeout_seconds": 90,
            }

            saved = save_chat_model_settings(payload, settings_path=settings_path)
            loaded = load_chat_model_settings(settings_path=settings_path)

        self.assertEqual(saved.provider, "deepseek")
        self.assertEqual(loaded.api_key, "deepseek-secret")
        self.assertEqual(loaded.base_url, "https://api.deepseek.com")
        self.assertEqual(loaded.model, "deepseek-chat")
        self.assertEqual(loaded.timeout_seconds, 90)

    def test_defaults_include_deepseek_and_qwen_presets(self):
        self.assertEqual(DEFAULT_CHAT_MODEL_SETTINGS["deepseek"]["base_url"], "https://api.deepseek.com")
        self.assertEqual(DEFAULT_CHAT_MODEL_SETTINGS["deepseek"]["model"], "deepseek-chat")
        self.assertEqual(
            DEFAULT_CHAT_MODEL_SETTINGS["qwen"]["base_url"],
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(DEFAULT_CHAT_MODEL_SETTINGS["qwen"]["model"], "qwen-plus")
        self.assertEqual(DEFAULT_CHAT_MODEL_SETTINGS["custom"]["base_url"], "")
        self.assertEqual(DEFAULT_CHAT_MODEL_SETTINGS["custom"]["model"], "")

    def test_effective_config_prefers_saved_settings_over_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            save_chat_model_settings(
                {
                    "provider": "qwen",
                    "api_key": "qwen-secret",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                    "timeout_seconds": 45,
                },
                settings_path=settings_path,
            )
            config = get_effective_chat_model_config(settings_path=settings_path)

        self.assertEqual(config, ("qwen-secret", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", 45))

    def test_loads_legacy_single_provider_settings_as_active_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "provider": "qwen",
                        "api_key": "legacy-qwen-secret",
                        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                        "model": "qwen-plus",
                        "timeout_seconds": 45,
                    }
                ),
                encoding="utf-8",
            )

            settings = load_chat_model_settings(settings_path=settings_path)

        self.assertEqual(settings.api_key, "legacy-qwen-secret")
        self.assertEqual(settings.profiles["qwen"].api_key, "legacy-qwen-secret")
        self.assertTrue(settings.profiles["qwen"].api_key_set)

    def test_provider_profiles_keep_api_keys_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            save_chat_model_settings(
                {
                    "provider": "deepseek",
                    "api_key": "deepseek-secret",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                },
                settings_path=settings_path,
            )
            save_chat_model_settings(
                {
                    "provider": "qwen",
                    "api_key": "qwen-secret",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                },
                settings_path=settings_path,
            )

            updated = save_chat_model_settings(
                {
                    "provider": "deepseek",
                    "api_key": "",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-reasoner",
                },
                settings_path=settings_path,
            )
            response = chat_model_settings_response(updated)

        self.assertEqual(updated.api_key, "deepseek-secret")
        self.assertEqual(updated.model, "deepseek-reasoner")
        self.assertTrue(response["profiles"]["deepseek"]["api_key_set"])
        self.assertTrue(response["profiles"]["qwen"]["api_key_set"])
        self.assertEqual(response["profiles"]["deepseek"]["api_key"], "")
        self.assertEqual(response["profiles"]["qwen"]["api_key"], "")

    def test_same_provider_can_reuse_saved_api_key_when_key_field_is_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            save_chat_model_settings(
                {
                    "provider": "qwen",
                    "api_key": "qwen-secret",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                },
                settings_path=settings_path,
            )

            updated = save_chat_model_settings(
                {
                    "provider": "qwen",
                    "api_key": "",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen3.6-plus",
                },
                settings_path=settings_path,
            )

        self.assertEqual(updated.api_key, "qwen-secret")
        self.assertEqual(updated.model, "qwen3.6-plus")

    def test_custom_provider_requires_user_supplied_endpoint_model_and_key(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"

            saved = save_chat_model_settings(
                {
                    "provider": "custom",
                    "api_key": "custom-secret",
                    "base_url": "https://gateway.example.com/v1",
                    "model": "company-chat",
                },
                settings_path=settings_path,
            )

            self.assertEqual(saved.provider, "custom")
            self.assertEqual(saved.api_key, "custom-secret")
            self.assertEqual(saved.base_url, "https://gateway.example.com/v1")
            self.assertEqual(saved.model, "company-chat")

            with self.assertRaisesRegex(ValueError, "Base URL is required"):
                save_chat_model_settings(
                    {
                        "provider": "custom",
                        "api_key": "custom-secret",
                        "base_url": "",
                        "model": "company-chat",
                    },
                    settings_path=Path(directory) / "missing_base.json",
                )

            with self.assertRaisesRegex(ValueError, "Model name is required"):
                save_chat_model_settings(
                    {
                        "provider": "custom",
                        "api_key": "custom-secret",
                        "base_url": "https://gateway.example.com/v1",
                        "model": "",
                    },
                    settings_path=Path(directory) / "missing_model.json",
                )


class ChatModelSettingsRoutesTest(unittest.TestCase):
    def test_chat_model_settings_round_trip_without_exposing_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            with patch("backend.app.api.settings.CHAT_MODEL_SETTINGS_PATH", settings_path):
                client = TestClient(app)
                response = client.put(
                    "/api/settings/chat-model",
                    json={
                        "provider": "deepseek",
                        "api_key": "deepseek-secret",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                        "timeout_seconds": 90,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["api_key"], "")
                self.assertTrue(response.json()["api_key_set"])

                response = client.get("/api/settings/chat-model")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "deepseek")
        self.assertEqual(response.json()["api_key"], "")
        self.assertTrue(response.json()["api_key_set"])
        self.assertEqual(response.json()["model"], "deepseek-chat")

    def test_chat_model_settings_reject_unknown_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            with patch("backend.app.api.settings.CHAT_MODEL_SETTINGS_PATH", settings_path):
                client = TestClient(app)
                response = client.put(
                    "/api/settings/chat-model",
                    json={
                        "provider": "unknown",
                        "api_key": "secret",
                        "base_url": "https://example.com/v1",
                        "model": "demo",
                    },
                )

        self.assertEqual(response.status_code, 422)

    def test_chat_model_settings_rejects_unconfigured_provider_without_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            with patch("backend.app.api.settings.CHAT_MODEL_SETTINGS_PATH", settings_path):
                client = TestClient(app)
                client.put(
                    "/api/settings/chat-model",
                    json={
                        "provider": "deepseek",
                        "api_key": "deepseek-secret",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                    },
                )
                response = client.put(
                    "/api/settings/chat-model",
                    json={
                        "provider": "qwen",
                        "api_key": "",
                        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                        "model": "qwen-plus",
                    },
                )

        self.assertEqual(response.status_code, 422)
        self.assertIn("API Key is required", response.json()["detail"])

    def test_chat_model_settings_accepts_custom_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            with patch("backend.app.api.settings.CHAT_MODEL_SETTINGS_PATH", settings_path):
                client = TestClient(app)
                response = client.put(
                    "/api/settings/chat-model",
                    json={
                        "provider": "custom",
                        "api_key": "custom-secret",
                        "base_url": "https://gateway.example.com/v1",
                        "model": "company-chat",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "custom")
        self.assertEqual(response.json()["base_url"], "https://gateway.example.com/v1")
        self.assertEqual(response.json()["model"], "company-chat")
        self.assertTrue(response.json()["api_key_set"])

    def test_chat_model_connection_test_uses_current_payload_without_saving(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            with (
                patch("backend.app.api.settings.CHAT_MODEL_SETTINGS_PATH", settings_path),
                patch("backend.app.api.settings.OpenAIChatClient") as client_class,
            ):
                client_class.return_value.chat = AsyncMock(return_value="OK")
                client = TestClient(app)
                response = client.post(
                    "/api/settings/chat-model/test",
                    json={
                        "provider": "deepseek",
                        "api_key": "deepseek-secret",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                    },
                )
                stored = client.get("/api/settings/chat-model")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["provider"], "deepseek")
        self.assertEqual(response.json()["model"], "deepseek-chat")
        self.assertEqual(stored.json()["provider"], "qwen")
        self.assertFalse(stored.json()["api_key_set"])
        client_class.return_value.chat.assert_called_once()

    def test_chat_model_connection_test_returns_sanitized_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "chat_model_settings.json"
            with (
                patch("backend.app.api.settings.CHAT_MODEL_SETTINGS_PATH", settings_path),
                patch("backend.app.api.settings.OpenAIChatClient") as client_class,
            ):
                client_class.return_value.chat = AsyncMock(
                    side_effect=OpenAIChatError("Generation API HTTP 401: invalid_api_key")
                )
                client = TestClient(app)
                response = client.post(
                    "/api/settings/chat-model/test",
                    json={
                        "provider": "qwen",
                        "api_key": "qwen-secret",
                        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                        "model": "qwen-plus",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertIn("invalid_api_key", response.json()["message"])
        self.assertNotIn("qwen-secret", str(response.json()))


if __name__ == "__main__":
    unittest.main()
