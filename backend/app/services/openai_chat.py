from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

import httpx

from backend.app.services.app_config import get_config_int, get_config_value
from backend.app.services.chat_model_settings import (
    get_effective_chat_model_config,
)


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
        self.api_key, self.base_url, self.model, configured_timeout = _generation_config(api_key, base_url, model)
        self.timeout_seconds = timeout_seconds or configured_timeout
        self.transport = transport

    async def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        """Non-streaming chat completion — fast, for classification / routing."""

        self._validate_config()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = _chat_completions_url(self.base_url)
        timeout = httpx.Timeout(self.timeout_seconds, connect=15.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise OpenAIChatError(
                        f"Generation API HTTP {resp.status_code}: "
                        f"{resp.text[:500]}"
                    )
                body = resp.json()
                return str(body["choices"][0]["message"].get("content") or "")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise OpenAIChatError("Generation API returned an invalid response.") from exc
        except httpx.TimeoutException as exc:
            raise OpenAIChatError(f"Generation API request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise OpenAIChatError(f"Generation API request failed: {exc}") from exc

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
        choices = item.get("choices", [])
        if not choices:
            return False, ""  # 最后的 usage-only chunk 没有 content
        content = choices[0].get("delta", {}).get("content")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return False, ""  # 容错：跳过无法解析的事件
    return False, str(content or "")


def _generation_config(
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> tuple[str, str, str, int]:
    if any(value is not None for value in (api_key, base_url, model)):
        return api_key or "", base_url or "", model or "", get_config_int("OPENAI_TIMEOUT_SECONDS", 120)

    saved_config = get_effective_chat_model_config()
    if saved_config is not None:
        return saved_config

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
