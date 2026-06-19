from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from backend.app.schemas.ingestion import ChunkingConfig, EmbeddingConfig, MilvusStoreConfig
from backend.app.schemas.ingestion_routes import IngestionRequest
from backend.app.services.app_config import (
    get_config_int,
    get_config_value,
    get_optional_config_int,
)
from backend.app.services.document_chunker import chunk_cleaned_document
from backend.app.services.document_vectorizer import index_markdown_document, vectorize_markdown_document
from backend.app.services.markdown_cleaner import clean_markdown_document
from backend.app.services.siliconflow_embeddings import SiliconFlowEmbeddingClient


def clean_markdown_payload(request: IngestionRequest) -> dict[str, Any]:
    """执行 Markdown 清洗，并组装路由响应。"""

    _validate_markdown(request.markdown)
    document = clean_markdown_document(request.markdown, source_path=request.source_path)

    return {
        "source_path": document.source_path,
        "document_title": document.title,
        "cleaned_text": document.cleaned_text,
        "sections_count": len(document.sections),
        "sections": [_section_to_dict(section) for section in document.sections],
    }


def chunk_markdown_payload(request: IngestionRequest) -> dict[str, Any]:
    """执行 Markdown 清洗和切分，并组装路由响应。"""

    _validate_markdown(request.markdown)
    document = clean_markdown_document(request.markdown, source_path=request.source_path)
    chunking = chunk_cleaned_document(document, _chunking_config(request))

    return {
        "source_path": chunking.source_path,
        "document_title": chunking.document_title,
        "chunks_count": chunking.total_chunks,
        "chunks": [_chunk_to_dict(chunk) for chunk in chunking.chunks],
    }


def vectorize_markdown_payload(request: IngestionRequest) -> dict[str, Any]:
    """执行清洗、切分、向量化，并组装路由响应。"""

    _validate_markdown(request.markdown)
    result = vectorize_markdown_document(
        request.markdown,
        source_path=request.source_path,
        client=_siliconflow_client(),
        chunking_config=_chunking_config(request),
        embedding_config=_embedding_config(request),
    )

    return {
        "source_path": result.source_path,
        "document_title": result.document_title,
        "sections_count": len(result.cleaned.sections),
        "chunks_count": result.chunking.total_chunks,
        "vectors_count": result.embedding.total_vectors,
        "model": result.embedding.model,
        "usage": {
            "prompt_tokens": result.embedding.usage.prompt_tokens,
            "completion_tokens": result.embedding.usage.completion_tokens,
            "total_tokens": result.embedding.usage.total_tokens,
        },
        "embeddings": [
            _embedding_to_dict(
                embedding,
                include_vector=request.include_vectors,
                preview_size=request.vector_preview_size,
            )
            for embedding in result.embedding.embeddings
        ],
    }


def index_markdown_payload(request: IngestionRequest) -> dict[str, Any]:
    """执行清洗、切分、向量化、Milvus 入库，并组装路由响应。"""

    _validate_markdown(request.markdown)
    result = index_markdown_document(
        request.markdown,
        source_path=request.source_path,
        chunking_config=_chunking_config(request),
        embedding_config=_embedding_config(request),
        store_config=_milvus_store_config(request),
    )

    return {
        "source_path": result.source_path,
        "document_title": result.document_title,
        "sections_count": len(result.cleaned.sections),
        "chunks_count": result.chunking.total_chunks,
        "vectors_count": result.embedding.total_vectors,
        "stored_count": result.store.stored_count,
        "collection_name": result.store.collection_name,
        "dimension": result.store.dimension,
        "metric_type": result.store.metric_type,
        "ids": result.store.ids,
    }


def _validate_markdown(markdown: str) -> None:
    if not markdown.strip():
        raise HTTPException(status_code=400, detail="markdown cannot be empty")


def _chunking_config(request: IngestionRequest) -> ChunkingConfig:
    return ChunkingConfig(
        max_tokens=request.max_tokens or get_config_int("CHUNK_MAX_TOKENS", 700),
        overlap_tokens=request.overlap_tokens or get_config_int("CHUNK_OVERLAP_TOKENS", 100),
        min_tokens=request.min_tokens or get_config_int("CHUNK_MIN_TOKENS", 80),
        preserve_code_blocks=request.preserve_code_blocks,
    )


def _embedding_config(request: IngestionRequest) -> EmbeddingConfig:
    return EmbeddingConfig(
        model=request.embedding_model or get_config_value(
            "SILICONFLOW_EMBEDDING_MODEL",
            "Qwen/Qwen3-VL-Embedding-8B",
        ),
        batch_size=request.embedding_batch_size or get_config_int("SILICONFLOW_EMBEDDING_BATCH_SIZE", 16),
        timeout_seconds=request.embedding_timeout_seconds or get_config_int(
            "SILICONFLOW_EMBEDDING_TIMEOUT_SECONDS",
            60,
        ),
        dimensions=request.embedding_dimensions or get_optional_config_int("SILICONFLOW_EMBEDDING_DIMENSIONS"),
    )


def _siliconflow_client() -> SiliconFlowEmbeddingClient:
    return SiliconFlowEmbeddingClient(base_url=_siliconflow_embeddings_url())


def _milvus_store_config(request: IngestionRequest) -> MilvusStoreConfig:
    return MilvusStoreConfig(
        uri=request.milvus_uri or get_config_value("MILVUS_URI", "http://localhost:19530"),
        token=request.milvus_token or get_config_value("MILVUS_TOKEN"),
        collection_name=request.milvus_collection or get_config_value("MILVUS_COLLECTION", "knowrag_chunks"),
        vector_dim=request.milvus_vector_dim or get_config_int("MILVUS_VECTOR_DIM", 4096),
        metric_type=request.milvus_metric_type or get_config_value("MILVUS_METRIC_TYPE", "COSINE"),
        timeout_seconds=request.milvus_timeout_seconds or get_config_int("MILVUS_TIMEOUT_SECONDS", 60),
        lite_enabled=get_config_value("MILVUS_LITE_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
        lite_path=get_config_value("MILVUS_LITE_PATH", "./data/milvus.db"),
    )


def _siliconflow_embeddings_url() -> str:
    base_url = get_config_value("SILICONFLOW_BASE_URL").rstrip("/")
    if not base_url:
        return "https://api.siliconflow.cn/v1/embeddings"
    if base_url.endswith("/embeddings"):
        return base_url
    return f"{base_url}/embeddings"


def _section_to_dict(section) -> dict[str, Any]:
    return {
        "heading": section.heading,
        "heading_path": list(section.heading_path),
        "level": section.level,
        "content": section.content,
        "start_line": section.start_line,
        "end_line": section.end_line,
    }


def _chunk_to_dict(chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "chunk_index": chunk.chunk_index,
        "source_path": chunk.source_path,
        "document_title": chunk.document_title,
        "heading": chunk.heading,
        "heading_path": list(chunk.heading_path),
        "content": chunk.content,
        "token_count": chunk.token_count,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "section_indexes": list(chunk.section_indexes),
    }


def _embedding_to_dict(embedding, include_vector: bool, preview_size: int) -> dict[str, Any]:
    data = {
        "chunk_id": embedding.chunk_id,
        "chunk_index": embedding.chunk_index,
        "source_path": embedding.source_path,
        "document_title": embedding.document_title,
        "heading_path": list(embedding.heading_path),
        "dimension": embedding.dimension,
        "token_count": embedding.token_count,
        "start_line": embedding.start_line,
        "end_line": embedding.end_line,
        "vector_preview": embedding.vector[:preview_size],
    }
    if include_vector:
        data["vector"] = embedding.vector
    return data
