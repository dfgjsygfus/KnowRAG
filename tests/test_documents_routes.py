from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

from fastapi.testclient import TestClient

from backend.app.schemas.ingestion import (
    EmbeddingResult,
    EmbeddingUsage,
    IndexingResult,
    VectorStoreResult,
)
from backend.app.services.document_chunker import chunk_cleaned_document
from backend.app.services.markdown_cleaner import clean_markdown_document
from main import app


client = TestClient(app)


class DocumentsRoutesTest(unittest.TestCase):
    def test_upload_list_detail_and_delete_document(self):
        with TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"DATABASE_URL": f"sqlite:///{Path(temp_dir) / 'app.db'}"},
        ):
            uploaded = client.post(
                "/api/documents/upload",
                json={
                    "filename": "demo.md",
                    "source_path": "frontend-upload/demo.md",
                    "content": "# Root\n\nUseful content.",
                    "size": 22,
                },
            )

            self.assertEqual(uploaded.status_code, 200)
            document_id = uploaded.json()["id"]
            self.assertEqual(uploaded.json()["status"], "uploaded")

            listed = client.get("/api/documents")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["total"], 1)
            self.assertEqual(listed.json()["documents"][0]["filename"], "demo.md")

            detail = client.get(f"/api/documents/{document_id}")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["content"], "# Root\n\nUseful content.")

            deleted = client.delete(f"/api/documents/{document_id}")
            self.assertEqual(deleted.status_code, 200)
            self.assertEqual(client.get("/api/documents").json()["total"], 0)

    def test_duplicate_upload_returns_existing_document_without_new_record(self):
        with TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"DATABASE_URL": f"sqlite:///{Path(temp_dir) / 'app.db'}"},
        ):
            first = client.post(
                "/api/documents/upload",
                json={
                    "filename": "first.md",
                    "source_path": "frontend-upload/first.md",
                    "content": "# Same content",
                },
            )
            duplicate = client.post(
                "/api/documents/upload",
                json={
                    "filename": "renamed.md",
                    "source_path": "frontend-upload/renamed.md",
                    "content": "# Same content",
                },
            )

            self.assertEqual(first.status_code, 200)
            self.assertFalse(first.json()["deduplicated"])
            self.assertEqual(duplicate.status_code, 200)
            self.assertTrue(duplicate.json()["deduplicated"])
            self.assertEqual(duplicate.json()["id"], first.json()["id"])
            self.assertEqual(client.get("/api/documents").json()["total"], 1)

    def test_index_document_route_persists_index_result(self):
        with TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"DATABASE_URL": f"sqlite:///{Path(temp_dir) / 'app.db'}"},
        ):
            uploaded = client.post(
                "/api/documents/upload",
                json={
                    "filename": "demo.md",
                    "source_path": "frontend-upload/demo.md",
                    "content": "# Root\n\nUseful content.",
                    "size": 22,
                },
            )
            document_id = uploaded.json()["id"]

            with patch(
                "backend.app.services.document_service.index_markdown_document",
                return_value=_indexing_result(),
            ):
                indexed = client.post(f"/api/documents/{document_id}/index")

            self.assertEqual(indexed.status_code, 200)
            body = indexed.json()
            self.assertEqual(body["status"], "ready")
            self.assertEqual(body["stored_count"], 1)
            self.assertEqual(body["chunks_count"], 1)

            detail = client.get(f"/api/documents/{document_id}")
            self.assertEqual(detail.json()["status"], "ready")
            self.assertEqual(len(detail.json()["chunks"]), 1)
            self.assertEqual(detail.json()["chunks"][0]["milvus_id"], "demo:0000")


def _indexing_result() -> IndexingResult:
    cleaned = clean_markdown_document("# Root\n\nUseful content.", "frontend-upload/demo.md")
    chunking = chunk_cleaned_document(cleaned)
    embedding = EmbeddingResult(
        model="Qwen/Qwen3-VL-Embedding-8B",
        usage=EmbeddingUsage(prompt_tokens=1, total_tokens=1),
        total_vectors=1,
        embeddings=[],
    )
    chunk = chunking.chunks[0]
    embedding = EmbeddingResult(
        model="Qwen/Qwen3-VL-Embedding-8B",
        usage=EmbeddingUsage(prompt_tokens=1, total_tokens=1),
        total_vectors=1,
        embeddings=[
            type(
                "Embedding",
                (),
                {
                    "chunk_id": "demo:0000",
                    "chunk_index": chunk.chunk_index,
                    "source_path": chunk.source_path,
                    "document_title": chunk.document_title,
                    "heading_path": chunk.heading_path,
                    "content": chunk.content,
                    "vector": [0.1, 0.2, 0.3],
                    "dimension": 3,
                    "token_count": chunk.token_count,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                },
            )()
        ],
    )
    return IndexingResult(
        source_path="frontend-upload/demo.md",
        document_title="Root",
        cleaned=cleaned,
        chunking=chunking,
        embedding=embedding,
        store=VectorStoreResult(
            collection_name="knowrag_chunks",
            stored_count=1,
            dimension=3,
            metric_type="COSINE",
            ids=["demo:0000"],
        ),
    )


if __name__ == "__main__":
    unittest.main()
