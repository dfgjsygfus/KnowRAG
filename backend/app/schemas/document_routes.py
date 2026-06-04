from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    """前端上传 Markdown 文档时使用的请求体。"""

    filename: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    source_path: str = ""
    size: int | None = Field(default=None, ge=0)


class DocumentListResponse(BaseModel):
    """文档列表响应，包含总数和文档摘要。"""

    total: int
    documents: list[dict]
