from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class RetrievalSearchResult:
    """一次向量检索命中的 chunk 摘要。"""

    chunk_id: str
    score: float
    document_title: str
    source_path: str
    heading_path: tuple[str, ...]
    content: str
    token_count: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class RetrievalResult:
    """一次 query 检索的完整结果。"""

    query: str
    top_k: int
    collection_name: str
    total: int
    results: list[RetrievalSearchResult]


class RetrievalSearchRequest(BaseModel):
    """检索测试接口请求体。"""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
