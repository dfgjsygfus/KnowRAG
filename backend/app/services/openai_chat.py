from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

import httpx

from backend.app.services.app_config import get_config_int, get_config_value


class OpenAIChatError(RuntimeError):
    """OpenAI-compatible generation request failed."""


StreamingTransport = Callable[[str, dict[str, str], dict[str, Any], int], Iterable[str]]


class OpenAIChatClient:
    """Small streaming client for OpenAI-compatible chat completion APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        transport: StreamingTransport | None = None,
    ) -> None:
        self.api_key, self.base_url, self.model = _generation_config(api_key, base_url, model)
        self.timeout_seconds = timeout_seconds or get_config_int("OPENAI_TIMEOUT_SECONDS", 120)
        self.transport = transport

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield text deltas from an OpenAI-compatible SSE response."""

        self._validate_config()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        url = _chat_completions_url(self.base_url)
        if self.transport is not None:
            for line in self.transport(url, headers, payload, self.timeout_seconds):
                done, content = _parse_sse_line(line)
                if done:
                    break
                if content:
                    yield content
            return

        timeout = httpx.Timeout(self.timeout_seconds, connect=15.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                async with http.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise OpenAIChatError(
                            f"Generation API HTTP {response.status_code}: "
                            f"{body.decode('utf-8', errors='replace')}"
                        )

                    async for line in response.aiter_lines():
                        done, content = _parse_sse_line(line)
                        if done:
                            break
                        if content:
                            yield content

        except httpx.TimeoutException as exc:
            raise OpenAIChatError(f"Generation API request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise OpenAIChatError(f"Generation API request failed: {exc}") from exc

    def _validate_config(self) -> None:
        if not self.api_key:
            raise OpenAIChatError("Missing OPENAI_API_KEY for generation.")
        if not self.base_url:
            raise OpenAIChatError("Missing OPENAI_BASE_URL for generation.")
        if not self.model:
            raise OpenAIChatError("Missing OPENAI_MODEL for generation.")


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _parse_sse_line(line: str) -> tuple[bool, str]:
    """解析单行 OpenAI-compatible SSE，返回是否结束和文本增量。"""

    stripped = line.strip()
    if not stripped or not stripped.startswith("data:"):
        return False, ""

    data = stripped[5:].strip()
    if data == "[DONE]":
        return True, ""

    try:
        item = json.loads(data)
        content = item["choices"][0]["delta"].get("content")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise OpenAIChatError("Generation stream returned an invalid SSE event.") from exc
    return False, str(content or "")


def _generation_config(
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> tuple[str, str, str]:
    if any(value is not None for value in (api_key, base_url, model)):
        return api_key or "", base_url or "", model or ""

    openai_config = (
        get_config_value("OPENAI_API_KEY"),
        get_config_value("OPENAI_BASE_URL"),
        get_config_value("OPENAI_MODEL"),
    )
    if any(openai_config):
        return openai_config

    return (
        get_config_value("SILICONFLOW_API_KEY"),
        get_config_value("SILICONFLOW_BASE_URL"),
        "Qwen/Qwen3-8B",
    )
