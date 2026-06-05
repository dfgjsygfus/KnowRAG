from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QueryIntent(str, Enum):
    """用户问题当前支持的两类意图。"""

    KNOWLEDGE_QUERY = "knowledge_query"
    CASUAL_CHAT = "casual_chat"


@dataclass(frozen=True)
class QueryRoute:
    """一次意图识别结果。"""

    intent: QueryIntent
    confidence: float
    reason: str
    method: str
