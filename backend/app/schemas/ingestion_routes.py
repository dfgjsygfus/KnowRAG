from __future__ import annotations

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    """离线入库相关路由的统一请求体。"""

    markdown: str
    source_path: str = ""

    max_tokens: int | None = Field(default=None, gt=0)
    overlap_tokens: int | None = Field(default=None, ge=0)
    min_tokens: int | None = Field(default=None, ge=0)
    preserve_code_blocks: bool = True

    embedding_model: str | None = None
    embedding_batch_size: int | None = Field(default=None, gt=0)
    embedding_timeout_seconds: int | None = Field(default=None, gt=0)
    embedding_dimensions: int | None = Field(default=None, gt=0)

    include_vectors: bool = False
    vector_preview_size: int = Field(default=8, ge=0, le=32)

    milvus_uri: str | None = None
    milvus_token: str | None = None
    milvus_collection: str | None = None
    milvus_vector_dim: int | None = Field(default=None, gt=0)
    milvus_metric_type: str | None = None
    milvus_timeout_seconds: int | None = Field(default=None, gt=0)
