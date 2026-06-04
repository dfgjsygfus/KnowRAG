from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentRecord:
    """后台文档列表使用的元数据记录。"""

    id: int
    filename: str
    source_path: str
    content_hash: str
    size: int
    status: str
    title: str
    sections_count: int
    chunks_count: int
    vectors_count: int
    stored_count: int
    error_message: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DocumentDetail(DocumentRecord):
    """文档详情，包含原始内容。"""

    content: str


@dataclass(frozen=True)
class ChunkRecord:
    """SQLite 中保存的 chunk 元数据。"""

    id: int
    document_id: int
    chunk_id: str
    chunk_index: int
    heading_path_json: str
    content: str
    token_count: int
    start_line: int
    end_line: int
    milvus_collection: str
    milvus_id: str
    created_at: str
