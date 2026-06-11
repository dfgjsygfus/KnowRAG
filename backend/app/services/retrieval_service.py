from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any

from backend.app.schemas.ingestion import EmbeddingConfig, MilvusStoreConfig
from backend.app.schemas.retrieval import RetrievalResult
from backend.app.services.chunk_embedder import EmbeddingClient
from backend.app.services.app_config import get_config_int, get_config_value, get_optional_config_int
from backend.app.services.milvus_vector_store import MilvusVectorStore
from backend.app.services.siliconflow_embeddings import SiliconFlowEmbeddingClient


logger = logging.getLogger(__name__)


def retrieve_query(
    query: str,
    top_k: int = 5,
    embedding_client: EmbeddingClient | None = None,
    milvus_client: Any | None = None,
    embedding_config: EmbeddingConfig | None = None,
    store_config: MilvusStoreConfig | None = None,
) -> RetrievalResult:
    """把用户问题向量化后，到 Milvus 中做原生 BM25 混合召回。"""

    embedding_config = embedding_config or _embedding_config()
    store_config = store_config or _milvus_store_config()
    embedding_client = embedding_client or SiliconFlowEmbeddingClient(base_url=_siliconflow_embeddings_url())

    normalized_query = query.strip()
    started_at = perf_counter()
    embedding_response = embedding_client.embed_texts([normalized_query], embedding_config)
    query_vector = [float(value) for value in embedding_response["embeddings"][0]]

    vector_store = MilvusVectorStore(client=milvus_client, config=store_config)
    result = vector_store.search_chunks(query=normalized_query, query_vector=query_vector, top_k=top_k)

    if _retrieval_log_enabled():
        logger.info(json.dumps({
            "event": "retrieval.completed",
            "query": normalized_query, "top_k": top_k, "hybrid": True,
            "collection": result.collection_name,
            "elapsed_ms": round((perf_counter() - started_at) * 1000, 3),
            "total": result.total,
            "hits": [{"chunk_id": item.chunk_id, "score": round(item.score, 6)} for item in result.results],
        }, ensure_ascii=False))
    return result


def retrieve_query_payload(request) -> dict[str, Any]:
    result = retrieve_query(query=request.query, top_k=request.top_k)
    return {
        "query": result.query, "top_k": result.top_k,
        "collection_name": result.collection_name, "total": result.total,
        "results": [
            {"chunk_id": item.chunk_id, "score": item.score, "document_title": item.document_title,
             "source_path": item.source_path, "heading_path": list(item.heading_path),
             "content": item.content, "token_count": item.token_count,
             "start_line": item.start_line, "end_line": item.end_line}
            for item in result.results
        ],
    }


def _embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(
        model=get_config_value("SILICONFLOW_EMBEDDING_MODEL", "Qwen/Qwen3-VL-Embedding-8B"),
        batch_size=get_config_int("SILICONFLOW_EMBEDDING_BATCH_SIZE", 16),
        timeout_seconds=get_config_int("SILICONFLOW_EMBEDDING_TIMEOUT_SECONDS", 60),
        dimensions=get_optional_config_int("SILICONFLOW_EMBEDDING_DIMENSIONS"),
    )


def _milvus_store_config() -> MilvusStoreConfig:
    return MilvusStoreConfig(
        uri=get_config_value("MILVUS_URI", "http://localhost:19530"),
        token=get_config_value("MILVUS_TOKEN"),
        collection_name=get_config_value("MILVUS_COLLECTION", "knowrag_chunks"),
        vector_dim=get_config_int("MILVUS_VECTOR_DIM", 4096),
        metric_type=get_config_value("MILVUS_METRIC_TYPE", "COSINE"),
        timeout_seconds=get_config_int("MILVUS_TIMEOUT_SECONDS", 60),
    )


def _siliconflow_embeddings_url() -> str:
    base_url = get_config_value("SILICONFLOW_BASE_URL").rstrip("/")
    if not base_url:
        return "https://api.siliconflow.cn/v1/embeddings"
    if base_url.endswith("/embeddings"):
        return base_url
    return f"{base_url}/embeddings"


def _retrieval_log_enabled() -> bool:
    return get_config_value("RETRIEVAL_LOG_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
