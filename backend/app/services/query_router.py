from __future__ import annotations

import asyncio
import json
import math
import re
from typing import Protocol

from backend.app.schemas.query_routing import QueryIntent, QueryRoute
from backend.app.services.app_config import get_config_value
from backend.app.services.openai_chat import OpenAIChatClient


# ── 规则层：正则 + 关键词 ──────────────────────────────────────────

_CASUAL_PATTERNS = (
    re.compile(r"^(你好|您好|嗨|hi|hello|hey)[！!。.？?\s]*$", re.IGNORECASE),
    re.compile(r"^(谢谢|感谢|辛苦了|多谢|thanks|thank you)[！!。.？?\s]*$", re.IGNORECASE),
    re.compile(r"^(再见|拜拜|bye|goodbye)[！!。.？?\s]*$", re.IGNORECASE),
    re.compile(r"^(你是谁|你叫什么名字|介绍(一下)?你自己|介绍(一下)?自己|who are you)[？?！!。.\s]*$", re.IGNORECASE),
    re.compile(r"^(早上好|下午好|晚上好|晚安|good morning|good afternoon|good night)[！!。.？?\s]*$", re.IGNORECASE),
)

_KNOWLEDGE_MARKERS = (
    "是什么", "为什么", "什么意思", "有什么用",
    "文档", "资料", "知识库", "职责", "作用", "流程", "实现",
    "代码", "函数", "模块", "架构", "设计", "原理", "方法",
    "解释", "说明", "定义", "区别", "对比", "总结",
)

# "怎么"/"如何" 单独处理 — 后跟"样"等为闲聊
_WEAK_MARKERS = ("怎么", "如何")
_FAKE_PATTERNS = (
    "怎么样", "怎么玩", "怎么看", "怎么想", "怎么回事", "怎么办",
    "如何评价", "如何看",
)

# 介绍类 — 只有明确在问知识库里的东西才算
_INTRO_MARKERS = ("介绍一下", "介绍下", "说说", "讲讲", "描述", "概述")

# 单大写字母开头 CamelCase / UPPER_SNAKE 标识符 → 很可能是问代码/架构
_CODE_IDENTIFIER_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*[A-Z][A-Za-z0-9_]*\b|\b[A-Za-z_][A-Za-z0-9_]*\(\)|\b[A-Z][A-Z0-9_]{2,}\b")

# 纯英文 / 代码片段 → 大概率是知识查询
_ENGLISH_QUERY_RE = re.compile(r"^[A-Za-z0-9_\-\.\s\(\)\{\}\[\];:,]+$")


# ── 语义层：embedding 相似度匹配 ────────────────────────────────────

# 每个意图的描述文本（短小精悍，少 token）
_INTENT_DESCRIPTIONS: dict[QueryIntent, str] = {
    QueryIntent.KNOWLEDGE_QUERY: (
        "查询知识库中的文档内容、代码实现、架构设计、项目介绍、技术细节、"
        "函数说明、模块职责、配置文件、使用方法和原理。"
    ),
    QueryIntent.CASUAL_CHAT: (
        "普通闲聊、打招呼、问候、感谢、告别、自我介绍、天气、笑话等非知识查询。"
    ),
}

# 缓存：意图描述 → embedding 向量
_intent_embeddings_cache: dict[QueryIntent, list[float]] = {}


async def _embedding_similarity(
    query: str,
    embedding_client=None,
    threshold: float = 0.65,
) -> tuple[QueryIntent, float] | None:
    """用 embedding 相似度匹配意图；返回 (intent, similarity) 或 None。"""

    try:
        from backend.app.services.siliconflow_embeddings import SiliconFlowEmbeddingClient
        from backend.app.schemas.ingestion import EmbeddingConfig

        client = embedding_client or SiliconFlowEmbeddingClient()

        # 获取或计算 intent 的 embedding 向量
        intent_vectors: dict[QueryIntent, list[float]] = {}
        for intent, description in _INTENT_DESCRIPTIONS.items():
            if intent not in _intent_embeddings_cache:
                resp = await asyncio.to_thread(
                    client.embed_texts,
                    [description],
                    EmbeddingConfig(
                        model=get_config_value("SILICONFLOW_EMBEDDING_MODEL", "Qwen/Qwen3-VL-Embedding-8B"),
                        timeout_seconds=int(get_config_value("SILICONFLOW_EMBEDDING_TIMEOUT_SECONDS", "60")),
                    ),
                )
                _intent_embeddings_cache[intent] = list(resp["embeddings"][0])
            intent_vectors[intent] = _intent_embeddings_cache[intent]

        # 获取 query embedding
        resp = await asyncio.to_thread(
            client.embed_texts,
            [query],
            EmbeddingConfig(
                model=get_config_value("SILICONFLOW_EMBEDDING_MODEL", "Qwen/Qwen3-VL-Embedding-8B"),
                timeout_seconds=int(get_config_value("SILICONFLOW_EMBEDDING_TIMEOUT_SECONDS", "60")),
            ),
        )
        query_vector = list(resp["embeddings"][0])

        # 余弦相似度
        best_intent = None
        best_similarity = -1.0
        for intent, iv in intent_vectors.items():
            sim = _cosine_similarity(query_vector, iv)
            if sim > best_similarity:
                best_similarity = sim
                best_intent = intent

        if best_intent is not None and best_similarity >= threshold:
            return best_intent, round(best_similarity, 4)
        return None

    except Exception:
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── 分类器协议 ──────────────────────────────────────────────────────

class QueryClassifier(Protocol):
    async def classify(self, question: str) -> str:
        """返回模型生成的意图分类 JSON。"""


class LLMQueryClassifier:
    """使用当前生成模型执行非流式结构化意图分类。"""

    def __init__(self, client: OpenAIChatClient | None = None) -> None:
        self.client = client or OpenAIChatClient()

    async def classify(self, question: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "判断用户问题属于 knowledge_query 或 casual_chat。"
                    "只输出 JSON，字段为 intent、confidence、reason。"
                    "knowledge_query 表示需要查询用户知识库（包括问代码、架构、技术细节）；"
                    "casual_chat 表示普通闲聊。"
                ),
            },
            {"role": "user", "content": question},
        ]
        return await self.client.chat(messages, temperature=0.0)


# ── 主路由入口 ──────────────────────────────────────────────────────

async def route_query(
    question: str,
    classifier: QueryClassifier | None = None,
    min_confidence: float | None = None,
    llm_enabled: bool | None = None,
) -> QueryRoute:
    """三层意图识别：规则 → embedding 语义匹配 → LLM → fallback 知识库。"""

    normalized = question.strip()

    # 第一层：规则
    rule_route = _route_by_rule(normalized)
    if rule_route is not None:
        return rule_route

    # 第二层：embedding 语义匹配
    embedding_threshold = float(get_config_value("QUERY_ROUTER_EMBEDDING_THRESHOLD", "0.70"))
    embedding_route = await _embedding_similarity(normalized, threshold=embedding_threshold)
    if embedding_route is not None:
        intent, similarity = embedding_route
        return QueryRoute(
            intent=intent,
            confidence=similarity,
            reason=f"embedding 语义匹配 (sim={similarity:.3f})",
            method="embedding",
        )

    # 第三层：LLM 分类
    enabled = _llm_enabled() if llm_enabled is None else llm_enabled
    if not enabled:
        return _fallback_route("模型意图识别已关闭，embedding 未匹配")

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


# ── 规则匹配 ────────────────────────────────────────────────────────

def _route_by_rule(question: str) -> QueryRoute | None:
    if any(pattern.match(question) for pattern in _CASUAL_PATTERNS):
        return QueryRoute(
            intent=QueryIntent.CASUAL_CHAT,
            confidence=1.0,
            reason="命中闲聊规则",
            method="rule",
        )

    # 如果包含"怎么样"、"怎么玩"等伪知识短语 → 走闲聊
    if any(fp in question for fp in _FAKE_PATTERNS):
        return None  # 不确定，交给 embedding/LLM

    # 强知识标记 → 一定是知识查询
    if any(marker in question for marker in _KNOWLEDGE_MARKERS):
        return QueryRoute(
            intent=QueryIntent.KNOWLEDGE_QUERY,
            confidence=1.0,
            reason="命中知识询问规则",
            method="rule",
        )

    # "怎么"/"如何" → 必须有明确宾语才算知识查询
    if any(question.startswith(m) or m in question for m in _WEAK_MARKERS):
        if len(question) >= 5:  # "怎么A" "如何做B" 至少5字才算
            return QueryRoute(
                intent=QueryIntent.KNOWLEDGE_QUERY,
                confidence=0.85,
                reason="弱知识标记+足够长度",
                method="rule",
            )

    # "介绍一下"/"说说" 等 → 如后面无具体名词就不算
    if any(m in question for m in _INTRO_MARKERS):
        stripped = question
        for m in _INTRO_MARKERS:
            if m in stripped:
                after = stripped[stripped.index(m) + len(m):]
                if after.strip() and not after.strip().startswith("你"):  # "介绍你" 不算
                    return QueryRoute(
                        intent=QueryIntent.KNOWLEDGE_QUERY,
                        confidence=0.85,
                        reason="介绍/描述类标记",
                        method="rule",
                    )

    # 代码标识符
    if _CODE_IDENTIFIER_RE.search(question):
        return QueryRoute(
            intent=QueryIntent.KNOWLEDGE_QUERY,
            confidence=1.0,
            reason="命中代码标识符",
            method="rule",
        )

    # 纯英文短句
    if len(question) < 60 and _ENGLISH_QUERY_RE.match(question):
        return QueryRoute(
            intent=QueryIntent.KNOWLEDGE_QUERY,
            confidence=0.90,
            reason="英文查询预判为知识检索",
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
