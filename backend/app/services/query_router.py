from __future__ import annotations

import json
import re
from typing import Protocol

from backend.app.schemas.query_routing import QueryIntent, QueryRoute
from backend.app.services.app_config import get_config_value
from backend.app.services.openai_chat import OpenAIChatClient


_CASUAL_PATTERNS = (
    re.compile(r"^(你好|您好|嗨|hi|hello)[！!。.？?\s]*$", re.IGNORECASE),
    re.compile(r"^(谢谢|感谢|辛苦了|多谢)[！!。.？?\s]*$"),
    re.compile(r"^(再见|拜拜|bye)[！!。.？?\s]*$", re.IGNORECASE),
    re.compile(r"^(你是谁|你叫什么名字|介绍一下你自己)[？?！!。.？?\s]*$"),
)
_KNOWLEDGE_MARKERS = (
    "是什么",
    "怎么",
    "如何",
    "为什么",
    "文档",
    "资料",
    "知识库",
    "职责",
    "作用",
    "流程",
    "实现",
)
_CODE_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\(\)|\b[A-Z][A-Z0-9_]{2,}\b")


class QueryClassifier(Protocol):
    async def classify(self, question: str) -> str:
        """返回模型生成的意图分类 JSON。"""


class LLMQueryClassifier:
    """使用当前生成模型执行非流式效果的结构化意图分类。"""

    def __init__(self, client: OpenAIChatClient | None = None) -> None:
        self.client = client or OpenAIChatClient()

    async def classify(self, question: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "判断用户问题属于 knowledge_query 或 casual_chat。"
                    "只输出 JSON，字段为 intent、confidence、reason。"
                    "knowledge_query 表示需要查询用户知识库；casual_chat 表示普通闲聊。"
                ),
            },
            {"role": "user", "content": question},
        ]
        return "".join([delta async for delta in self.client.stream_chat(messages)])


async def route_query(
    question: str,
    classifier: QueryClassifier | None = None,
    min_confidence: float | None = None,
    llm_enabled: bool | None = None,
) -> QueryRoute:
    """按规则优先识别意图，模糊问题使用模型，失败时默认检索知识库。"""

    normalized = question.strip()
    rule_route = _route_by_rule(normalized)
    if rule_route is not None:
        return rule_route

    enabled = _llm_enabled() if llm_enabled is None else llm_enabled
    if not enabled:
        return _fallback_route("模型意图识别已关闭")

    threshold = min_confidence if min_confidence is not None else _configured_min_confidence()
    try:
        payload = json.loads(await (classifier or LLMQueryClassifier()).classify(normalized))
        intent = QueryIntent(str(payload["intent"]))
        confidence = float(payload["confidence"])
        reason = str(payload.get("reason") or "")
    except Exception:
        return _fallback_route("模型意图识别失败")

    if confidence < threshold:
        return _fallback_route("意图置信度不足")
    return QueryRoute(intent=intent, confidence=confidence, reason=reason, method="model")


def _route_by_rule(question: str) -> QueryRoute | None:
    if any(pattern.match(question) for pattern in _CASUAL_PATTERNS):
        return QueryRoute(
            intent=QueryIntent.CASUAL_CHAT,
            confidence=1.0,
            reason="命中闲聊规则",
            method="rule",
        )
    if any(marker in question for marker in _KNOWLEDGE_MARKERS) or _CODE_IDENTIFIER_RE.search(question):
        return QueryRoute(
            intent=QueryIntent.KNOWLEDGE_QUERY,
            confidence=1.0,
            reason="命中知识询问规则",
            method="rule",
        )
    return None


def _fallback_route(reason: str) -> QueryRoute:
    return QueryRoute(
        intent=QueryIntent.KNOWLEDGE_QUERY,
        confidence=0.0,
        reason=reason,
        method="fallback",
    )


def _configured_min_confidence() -> float:
    return float(get_config_value("QUERY_ROUTER_MIN_CONFIDENCE", "0.65"))


def _llm_enabled() -> bool:
    return get_config_value("QUERY_ROUTER_LLM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
