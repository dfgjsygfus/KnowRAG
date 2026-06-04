from __future__ import annotations

import json
from typing import Any, Callable
from urllib import error, request

from backend.app.schemas.ingestion import EmbeddingConfig
from backend.app.services.app_config import get_config_value


SILICONFLOW_EMBEDDINGS_URL = "https://api.siliconflow.cn/v1/embeddings"

Transport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


class SiliconFlowEmbeddingError(RuntimeError):
    """硅基流动向量化接口调用失败。"""


class SiliconFlowEmbeddingClient:
    """硅基流动 embeddings 客户端，兼容测试注入 transport。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = SILICONFLOW_EMBEDDINGS_URL,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key or get_config_value("SILICONFLOW_API_KEY")
        self.base_url = base_url
        self.transport = transport or _urllib_transport

    def embed_texts(self, texts: list[str], config: EmbeddingConfig) -> dict[str, Any]:
        """调用硅基流动 embeddings 接口，返回按输入顺序排列的向量。"""

        if not texts:
            return {
                "model": config.model,
                "embeddings": [],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        if not self.api_key:
            raise SiliconFlowEmbeddingError("Missing SILICONFLOW_API_KEY for SiliconFlow embeddings.")

        payload: dict[str, Any] = {
            "model": config.model,
            "input": texts,
            "encoding_format": config.encoding_format,
        }
        if config.dimensions is not None:
            payload["dimensions"] = config.dimensions
        if config.user is not None:
            payload["user"] = config.user
        if config.truncate is not None:
            payload["truncate"] = config.truncate

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self.transport(self.base_url, headers, payload, config.timeout_seconds)
        return _parse_embedding_response(response, len(texts), config.model)


def _urllib_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    """用标准库发起请求，避免为 MVP 额外引入 HTTP 依赖。"""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SiliconFlowEmbeddingError(f"SiliconFlow embeddings HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise SiliconFlowEmbeddingError(f"SiliconFlow embeddings request failed: {exc.reason}") from exc


def _parse_embedding_response(
    response: dict[str, Any],
    expected_count: int,
    fallback_model: str,
) -> dict[str, Any]:
    """校验并归一化硅基流动返回值。"""

    data = response.get("data")
    if not isinstance(data, list):
        raise SiliconFlowEmbeddingError("SiliconFlow embeddings response missing data list.")

    sorted_items = sorted(data, key=lambda item: int(item.get("index", 0)))
    embeddings = [item.get("embedding") for item in sorted_items]
    if len(embeddings) != expected_count:
        raise SiliconFlowEmbeddingError(
            f"SiliconFlow returned {len(embeddings)} embeddings, expected {expected_count}."
        )
    if not all(isinstance(vector, list) for vector in embeddings):
        raise SiliconFlowEmbeddingError("SiliconFlow embeddings response contains invalid vector.")

    usage = response.get("usage") or {}
    return {
        "model": response.get("model") or fallback_model,
        "embeddings": embeddings,
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        },
    }
