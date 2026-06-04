from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.schemas.document_routes import DocumentUploadRequest
from backend.app.services.document_repository import DocumentNotFoundError
from backend.app.services.document_service import (
    delete_document_payload,
    get_document_payload,
    index_document_payload,
    list_documents_payload,
    upload_document_payload,
)
from backend.app.services.milvus_vector_store import MilvusVectorStoreError
from backend.app.services.siliconflow_embeddings import SiliconFlowEmbeddingError


router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(request: DocumentUploadRequest) -> dict[str, Any]:
    """上传文档并写入本地 SQLite，避免刷新页面后丢失。"""

    return upload_document_payload(request)


@router.get("")
async def list_documents() -> dict[str, Any]:
    """获取已上传文档列表。"""

    return list_documents_payload()


@router.get("/{document_id}")
async def get_document(document_id: int) -> dict[str, Any]:
    """获取文档详情和本地 chunk 元数据。"""

    try:
        return get_document_payload(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{document_id}/index")
async def index_document(document_id: int) -> dict[str, Any]:
    """对已上传文档执行入库流程，并把结果状态持久化。"""

    try:
        return index_document_payload(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (SiliconFlowEmbeddingError, MilvusVectorStoreError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/{document_id}")
async def delete_document(document_id: int) -> dict[str, Any]:
    """删除文档及其本地 chunk 元数据。"""

    try:
        return delete_document_payload(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
