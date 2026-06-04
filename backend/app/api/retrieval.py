from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.schemas.retrieval import RetrievalSearchRequest
from backend.app.services.milvus_vector_store import MilvusVectorStoreError
from backend.app.services.retrieval_service import retrieve_query_payload
from backend.app.services.siliconflow_embeddings import SiliconFlowEmbeddingError


router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


@router.post("/search")
async def search_chunks(request: RetrievalSearchRequest) -> dict[str, Any]:
    """检索测试：把问题向量化后从 Milvus 召回相关 chunk。"""

    try:
        return retrieve_query_payload(request)
    except SiliconFlowEmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except MilvusVectorStoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
