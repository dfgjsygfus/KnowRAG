from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.services.app_config import get_config_int, get_config_value


CHAT_MODEL_SETTINGS_PATH = Path(__file__).resolve().parents[3] / "data" / "chat_model_settings.json"

DEFAULT_CHAT_MODEL_SETTINGS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "qwen": {
        "label": "Qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "custom": {
        "label": "Custom",
        "base_url": "",
        "model": "",
    },
}


@dataclass(frozen=True)
class ChatProviderProfile:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class ChatModelSettings:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int
    profiles: dict[str, ChatProviderProfile]

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key)


def load_chat_model_settings(settings_path: Path = CHAT_MODEL_SETTINGS_PATH) -> ChatModelSettings:
    if not settings_path.exists():
        return _default_settings()

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    return _settings_from_storage(data)


def save_chat_model_settings(
    payload: dict[str, Any],
    settings_path: Path = CHAT_MODEL_SETTINGS_PATH,
) -> ChatModelSettings:
    settings = build_chat_model_settings(payload, settings_path=settings_path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "provider": settings.provider,
                "profiles": {
                    provider: _profile_storage(profile)
                    for provider, profile in settings.profiles.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return settings


def build_chat_model_settings(
    payload: dict[str, Any],
    settings_path: Path = CHAT_MODEL_SETTINGS_PATH,
) -> ChatModelSettings:
    previous = load_chat_model_settings(settings_path) if settings_path.exists() else _default_settings()
    return _settings_from_payload(payload, previous=previous)


def get_effective_chat_model_config(
    settings_path: Path = CHAT_MODEL_SETTINGS_PATH,
) -> tuple[str, str, str, int] | None:
    if settings_path.exists():
        settings = load_chat_model_settings(settings_path)
        if settings.api_key or settings.base_url or settings.model:
            return settings.api_key, settings.base_url, settings.model, settings.timeout_seconds
    return None


def chat_model_settings_response(settings: ChatModelSettings) -> dict[str, Any]:
    return {
        "provider": settings.provider,
        "api_key": "",
        "api_key_set": settings.api_key_set,
        "base_url": settings.base_url,
        "model": settings.model,
        "timeout_seconds": settings.timeout_seconds,
        "presets": DEFAULT_CHAT_MODEL_SETTINGS,
        "profiles": {
            provider: _profile_response(profile)
            for provider, profile in settings.profiles.items()
        },
    }


def _settings_from_payload(payload: dict[str, Any], previous: ChatModelSettings) -> ChatModelSettings:
    provider = str(payload.get("provider") or previous.provider or "qwen")
    if provider not in DEFAULT_CHAT_MODEL_SETTINGS:
        raise ValueError(f"Unsupported chat model provider: {provider}")

    preset = DEFAULT_CHAT_MODEL_SETTINGS[provider]
    profiles = dict(previous.profiles)
    previous_profile = profiles.get(provider) or _default_profile(provider)
    raw_api_key = payload.get("api_key")
    submitted_api_key = str(raw_api_key).strip() if raw_api_key else ""
    if submitted_api_key:
        api_key = submitted_api_key
    elif previous_profile.api_key:
        api_key = previous_profile.api_key
    else:
        raise ValueError("API Key is required when saving a chat model provider.")

    base_url = _payload_text(payload, "base_url")
    if not base_url:
        base_url = "" if provider == "custom" else preset["base_url"]
    model = _payload_text(payload, "model")
    if not model:
        model = "" if provider == "custom" else preset["model"]
    if provider == "custom" and not base_url:
        raise ValueError("Base URL is required for custom chat model provider.")
    if provider == "custom" and not model:
        raise ValueError("Model name is required for custom chat model provider.")
    timeout_seconds = _payload_timeout(payload, previous_profile.timeout_seconds)

    profiles[provider] = ChatProviderProfile(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )
    return _settings_from_provider(provider, profiles)


def _settings_from_storage(data: dict[str, Any]) -> ChatModelSettings:
    provider = str(data.get("provider") or "qwen")
    if provider not in DEFAULT_CHAT_MODEL_SETTINGS:
        raise ValueError(f"Unsupported chat model provider: {provider}")

    profiles = _default_profiles()
    raw_profiles = data.get("profiles")
    if isinstance(raw_profiles, dict):
        for profile_provider, raw_profile in raw_profiles.items():
            if profile_provider in DEFAULT_CHAT_MODEL_SETTINGS and isinstance(raw_profile, dict):
                profiles[profile_provider] = _profile_from_storage(profile_provider, raw_profile)

    if "profiles" not in data:
        profiles[provider] = _profile_from_storage(provider, data)

    return _settings_from_provider(provider, profiles)


def _default_settings() -> ChatModelSettings:
    return _settings_from_provider("qwen", _default_profiles())


def _default_profiles() -> dict[str, ChatProviderProfile]:
    return {
        provider: _default_profile(provider)
        for provider in DEFAULT_CHAT_MODEL_SETTINGS
    }


def _default_profile(provider: str) -> ChatProviderProfile:
    preset = DEFAULT_CHAT_MODEL_SETTINGS[provider]
    return ChatProviderProfile(
        api_key="",
        base_url=preset["base_url"],
        model=preset["model"],
        timeout_seconds=get_config_int("OPENAI_TIMEOUT_SECONDS", 120),
    )


def _settings_from_provider(
    provider: str,
    profiles: dict[str, ChatProviderProfile],
) -> ChatModelSettings:
    profile = profiles[provider]
    return ChatModelSettings(
        provider=provider,
        api_key=profile.api_key,
        base_url=profile.base_url,
        model=profile.model,
        timeout_seconds=profile.timeout_seconds,
        profiles=profiles,
    )


def _profile_from_storage(provider: str, data: dict[str, Any]) -> ChatProviderProfile:
    preset = DEFAULT_CHAT_MODEL_SETTINGS[provider]
    api_key = str(data.get("api_key") or "").strip()
    base_url = str(data.get("base_url") or preset["base_url"]).strip().rstrip("/")
    model = str(data.get("model") or preset["model"]).strip()
    timeout_seconds = _payload_timeout(data, get_config_int("OPENAI_TIMEOUT_SECONDS", 120))
    return ChatProviderProfile(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )


def _profile_storage(profile: ChatProviderProfile) -> dict[str, Any]:
    return {
        "api_key": profile.api_key,
        "base_url": profile.base_url,
        "model": profile.model,
        "timeout_seconds": profile.timeout_seconds,
    }


def _profile_response(profile: ChatProviderProfile) -> dict[str, Any]:
    return {
        "api_key": "",
        "api_key_set": profile.api_key_set,
        "base_url": profile.base_url,
        "model": profile.model,
        "timeout_seconds": profile.timeout_seconds,
    }


def _payload_text(payload: dict[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip().rstrip("/") if key == "base_url" else str(payload.get(key) or "").strip()


def _payload_timeout(payload: dict[str, Any], default: int) -> int:
    try:
        return int(payload.get("timeout_seconds") or default)
    except (TypeError, ValueError):
        return default


def get_environment_chat_model_config() -> tuple[str, str, str, int]:
    timeout_seconds = get_config_int("OPENAI_TIMEOUT_SECONDS", 120)
    openai_config = (
        get_config_value("OPENAI_API_KEY"),
        get_config_value("OPENAI_BASE_URL"),
        get_config_value("OPENAI_MODEL"),
    )
    if any(openai_config):
        return openai_config[0], openai_config[1], openai_config[2], timeout_seconds

    return (
        get_config_value("SILICONFLOW_API_KEY"),
        get_config_value("SILICONFLOW_BASE_URL"),
        "Qwen/Qwen3-8B",
        timeout_seconds,
    )
