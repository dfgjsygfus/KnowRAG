from __future__ import annotations

import json
from typing import Any

from backend.app.schemas.document_routes import DocumentUploadRequest
from backend.app.schemas.documents import ChunkRecord, DocumentDetail, DocumentRecord
from backend.app.services.document_repository import DocumentRepository
from backend.app.services.document_vectorizer import index_markdown_document
from backend.app.services.milvus_vector_store import MilvusVectorStore
from backend.app.services.retrieval_service import _milvus_store_config


def upload_document_payload(
    request: DocumentUploadRequest,
    repository: DocumentRepository | None = None,
) -> dict[str, Any]:
    """保存前端上传的文档内容，刷新页面后仍可从 SQLite 恢复。"""

    repo = repository or DocumentRepository()
    source_path = request.source_path or f"frontend-upload/{request.filename}"
    size = request.size if request.size is not None else len(request.content.encode("utf-8"))
    document, deduplicated = repo.create_or_get_document(
        filename=request.filename,
        source_path=source_path,
        content=request.content,
        size=size,
    )
    payload = serialize_document_record(document)
    payload["deduplicated"] = deduplicated
    return payload


def list_documents_payload(repository: DocumentRepository | None = None) -> dict[str, Any]:
    """返回后台已经保存过的文档摘要列表。"""

    repo = repository or DocumentRepository()
    documents = [serialize_document_record(item) for item in repo.list_documents()]
    return {"total": len(documents), "documents": documents}


def get_document_payload(
    document_id: int,
    repository: DocumentRepository | None = None,
) -> dict[str, Any]:
    """返回单个文档详情，并附带本地保存的 chunk 元数据。"""

    repo = repository or DocumentRepository()
    document = repo.get_document(document_id)
    chunks = repo.list_chunks(document_id)
    payload = serialize_document_detail(document)
    payload["chunks"] = [serialize_chunk_record(chunk) for chunk in chunks]
    return payload


def delete_document_payload(
    document_id: int,
    repository: DocumentRepository | None = None,
    vector_store: MilvusVectorStore | None = None,
) -> dict[str, Any]:
    """先删除 Milvus 向量，再删除 SQLite 中的文档和 chunk 元数据。"""

    repo = repository or DocumentRepository()
    repo.get_document(document_id)
    old_chunks = repo.list_chunks(document_id)
    if old_chunks:
        store = vector_store or MilvusVectorStore(config=_milvus_store_config())
        store.delete_chunk_ids([chunk.milvus_id for chunk in old_chunks])
    repo.delete_document(document_id)
    return {"id": document_id, "deleted": True}


def index_document_payload(
    document_id: int,
    repository: DocumentRepository | None = None,
    vector_store: MilvusVectorStore | None = None,
) -> dict[str, Any]:
    """读取已上传文档，执行清洗、切分、向量化和 Milvus 入库，并回写状态。"""

    repo = repository or DocumentRepository()
    document = repo.get_document(document_id)
    previous_vector_ids = {chunk.milvus_id for chunk in repo.list_chunks(document_id)}
    repo.mark_indexing(document_id)
    try:
        result = index_markdown_document(
            document.content,
            source_path=document.source_path,
            store_config=_milvus_store_config(),
        )
    except Exception as exc:
        # 这里记录失败原因，便于前端刷新后仍然能看到上次入库错误。
        repo.mark_failed(document_id, str(exc))
        raise

    stale_vector_ids = sorted(previous_vector_ids - set(result.store.ids))
    if stale_vector_ids:
        store = vector_store or MilvusVectorStore()
        store.delete_chunk_ids(stale_vector_ids)
    repo.save_index_result(document_id, result)
    return serialize_document_record(repo.get_document(document_id))


def serialize_document_record(document: DocumentRecord) -> dict[str, Any]:
    """把 dataclass 文档摘要转换为 FastAPI 可返回的 JSON 字典。"""

    return {
        "id": document.id,
        "filename": document.filename,
        "source_path": document.source_path,
        "content_hash": document.content_hash,
        "size": document.size,
        "status": document.status,
        "title": document.title,
        "sections_count": document.sections_count,
        "chunks_count": document.chunks_count,
        "vectors_count": document.vectors_count,
        "stored_count": document.stored_count,
        "error_message": document.error_message,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def serialize_document_detail(document: DocumentDetail) -> dict[str, Any]:
    """文档详情比摘要多返回原始 Markdown 内容。"""

    payload = serialize_document_record(document)
    payload["content"] = document.content
    return payload


def serialize_chunk_record(chunk: ChunkRecord) -> dict[str, Any]:
    """把 chunk 元数据反序列化为前端更容易消费的结构。"""

    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_id": chunk.chunk_id,
        "chunk_index": chunk.chunk_index,
        "heading_path": json.loads(chunk.heading_path_json),
        "content": chunk.content,
        "token_count": chunk.token_count,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "milvus_collection": chunk.milvus_collection,
        "milvus_id": chunk.milvus_id,
        "created_at": chunk.created_at,
    }
