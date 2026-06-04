from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.schemas.ingestion_routes import IngestionRequest
from backend.app.services.ingestion_pipeline import (
    chunk_markdown_payload,
    clean_markdown_payload,
    index_markdown_payload,
    vectorize_markdown_payload,
)
from backend.app.services.siliconflow_embeddings import (
    SiliconFlowEmbeddingError,
)
from backend.app.services.milvus_vector_store import MilvusVectorStoreError


router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.post("/clean")
async def clean_markdown(request: IngestionRequest) -> dict[str, Any]:
    """清洗 Markdown 文档，返回清洗文本和 section 结构。"""

    return clean_markdown_payload(request)


@router.post("/chunk")
async def chunk_markdown(request: IngestionRequest) -> dict[str, Any]:
    """清洗并切分 Markdown 文档，返回 chunk 元数据。"""

    return chunk_markdown_payload(request)


@router.post("/vectorize")
async def vectorize_markdown(request: IngestionRequest) -> dict[str, Any]:
    """执行清洗、切分、向量化流水线，默认只返回向量预览。"""

    try:
        return vectorize_markdown_payload(request)
    except SiliconFlowEmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/index")
async def index_markdown(request: IngestionRequest) -> dict[str, Any]:
    """执行离线入库流水线，并把 chunk 向量写入 Milvus。"""

    try:
        return index_markdown_payload(request)
    except SiliconFlowEmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except MilvusVectorStoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
