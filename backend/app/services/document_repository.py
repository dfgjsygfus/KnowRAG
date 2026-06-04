from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from backend.app.schemas.documents import ChunkRecord, DocumentDetail, DocumentRecord
from backend.app.schemas.ingestion import IndexingResult
from backend.app.services.app_config import get_config_value


class DocumentNotFoundError(RuntimeError):
    """文档不存在。"""


class DocumentRepository:
    """SQLite 文档元数据仓储。"""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or get_config_value("DATABASE_URL", "sqlite:///./data/app.db")
        self.database_path = _database_path(self.database_url)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def init_schema(self) -> None:
        """初始化 SQLite 表结构。"""

        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    sections_count INTEGER NOT NULL DEFAULT 0,
                    chunks_count INTEGER NOT NULL DEFAULT 0,
                    vectors_count INTEGER NOT NULL DEFAULT 0,
                    stored_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    heading_path_json TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    milvus_collection TEXT NOT NULL,
                    milvus_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    UNIQUE(document_id, chunk_id)
                );

                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT,
                    error_message TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                """
            )

    def create_document(self, filename: str, source_path: str, content: str, size: int) -> DocumentRecord:
        """保存上传文档，初始状态为 uploaded。"""

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (filename, source_path, content, content_hash, size, status)
                VALUES (?, ?, ?, ?, ?, 'uploaded')
                """,
                (filename, source_path, content, content_hash, size),
            )
            document_id = int(cursor.lastrowid)
        return self.get_document(document_id)

    def list_documents(self) -> list[DocumentRecord]:
        """按更新时间倒序返回文档列表。"""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, filename, source_path, content_hash, size, status, title,
                       sections_count, chunks_count, vectors_count, stored_count,
                       error_message, created_at, updated_at
                FROM documents
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def find_document(self, document_id: int) -> DocumentDetail | None:
        """查找文档，找不到时返回 None。"""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, filename, source_path, content, content_hash, size, status, title,
                       sections_count, chunks_count, vectors_count, stored_count,
                       error_message, created_at, updated_at
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
        return _detail_from_row(row) if row else None

    def get_document(self, document_id: int) -> DocumentDetail:
        """获取文档详情，找不到时抛出业务错误。"""

        document = self.find_document(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found.")
        return document

    def list_chunks(self, document_id: int) -> list[ChunkRecord]:
        """返回某个文档的 chunk 元数据。"""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, document_id, chunk_id, chunk_index, heading_path_json,
                       content, token_count, start_line, end_line,
                       milvus_collection, milvus_id, created_at
                FROM chunks
                WHERE document_id = ?
                ORDER BY chunk_index ASC
                """,
                (document_id,),
            ).fetchall()
        return [_chunk_from_row(row) for row in rows]

    def mark_indexing(self, document_id: int) -> None:
        """标记文档开始入库。"""

        self.get_document(document_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET status = 'indexing', error_message = '', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (document_id,),
            )
            conn.execute(
                "INSERT INTO ingestion_jobs (document_id, status) VALUES (?, 'running')",
                (document_id,),
            )

    def save_index_result(self, document_id: int, result: IndexingResult) -> None:
        """保存入库成功后的文档摘要和 chunk 元数据。"""

        self.get_document(document_id)
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            for embedding in result.embedding.embeddings:
                conn.execute(
                    """
                    INSERT INTO chunks (
                        document_id, chunk_id, chunk_index, heading_path_json, content,
                        token_count, start_line, end_line, milvus_collection, milvus_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        embedding.chunk_id,
                        embedding.chunk_index,
                        json.dumps(list(embedding.heading_path), ensure_ascii=False),
                        embedding.content,
                        embedding.token_count,
                        embedding.start_line,
                        embedding.end_line,
                        result.store.collection_name,
                        embedding.chunk_id,
                    ),
                )
            conn.execute(
                """
                UPDATE documents
                SET status = 'ready',
                    title = ?,
                    sections_count = ?,
                    chunks_count = ?,
                    vectors_count = ?,
                    stored_count = ?,
                    error_message = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    result.document_title,
                    len(result.cleaned.sections),
                    result.chunking.total_chunks,
                    result.embedding.total_vectors,
                    result.store.stored_count,
                    document_id,
                ),
            )
            conn.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'completed', finished_at = CURRENT_TIMESTAMP
                WHERE document_id = ? AND status = 'running'
                """,
                (document_id,),
            )

    def mark_failed(self, document_id: int, error_message: str) -> None:
        """保存入库失败状态。"""

        self.get_document(document_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (error_message, document_id),
            )
            conn.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'failed', finished_at = CURRENT_TIMESTAMP, error_message = ?
                WHERE document_id = ? AND status = 'running'
                """,
                (error_message, document_id),
            )

    def delete_document(self, document_id: int) -> None:
        """删除文档及其本地元数据。"""

        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _database_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// DATABASE_URL is supported for local metadata storage.")
    raw_path = database_url.removeprefix("sqlite:///")
    return Path(raw_path).resolve()


def _record_from_row(row: sqlite3.Row) -> DocumentRecord:
    data = dict(row)
    return DocumentRecord(**data)


def _detail_from_row(row: sqlite3.Row) -> DocumentDetail:
    data: dict[str, Any] = dict(row)
    return DocumentDetail(**data)


def _chunk_from_row(row: sqlite3.Row) -> ChunkRecord:
    data = dict(row)
    return ChunkRecord(**data)
