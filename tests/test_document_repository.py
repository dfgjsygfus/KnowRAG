from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from backend.app.schemas.ingestion import (
    ChunkEmbedding,
    EmbeddingResult,
    EmbeddingUsage,
    IndexingResult,
    VectorStoreResult,
)
from backend.app.services.document_repository import DocumentRepository
from backend.app.services.markdown_cleaner import clean_markdown_document
from backend.app.services.document_chunker import chunk_cleaned_document


class DocumentRepositoryTest(unittest.TestCase):
    def test_persists_document_and_detail(self):
        with TemporaryDirectory() as temp_dir:
            repo = DocumentRepository(f"sqlite:///{Path(temp_dir) / 'app.db'}")

            document = repo.create_document(
                filename="demo.md",
                source_path="frontend-upload/demo.md",
                content="# Root\n\nUseful content.",
                size=22,
            )
            loaded = repo.get_document(document.id)

            self.assertEqual(loaded.id, document.id)
            self.assertEqual(loaded.filename, "demo.md")
            self.assertEqual(loaded.status, "uploaded")
            self.assertEqual(loaded.content, "# Root\n\nUseful content.")
            self.assertEqual(len(repo.list_documents()), 1)

    def test_reuses_existing_document_when_content_hash_matches(self):
        with TemporaryDirectory() as temp_dir:
            repo = DocumentRepository(f"sqlite:///{Path(temp_dir) / 'app.db'}")

            first, first_deduplicated = repo.create_or_get_document(
                filename="first.md",
                source_path="frontend-upload/first.md",
                content="# Same content",
                size=14,
            )
            second, second_deduplicated = repo.create_or_get_document(
                filename="renamed.md",
                source_path="frontend-upload/renamed.md",
                content="# Same content",
                size=14,
            )

            self.assertFalse(first_deduplicated)
            self.assertTrue(second_deduplicated)
            self.assertEqual(second.id, first.id)
            self.assertEqual(second.filename, "first.md")
            self.assertEqual(len(repo.list_documents()), 1)

    def test_saves_index_result_and_chunk_metadata(self):
        with TemporaryDirectory() as temp_dir:
            repo = DocumentRepository(f"sqlite:///{Path(temp_dir) / 'app.db'}")
            document = repo.create_document("demo.md", "frontend-upload/demo.md", "# Root", 6)

            repo.save_index_result(document.id, _indexing_result())
            loaded = repo.get_document(document.id)
            chunks = repo.list_chunks(document.id)

            self.assertEqual(loaded.status, "ready")
            self.assertEqual(loaded.sections_count, 1)
            self.assertEqual(loaded.chunks_count, 1)
            self.assertEqual(loaded.vectors_count, 1)
            self.assertEqual(loaded.stored_count, 1)
            self.assertEqual(chunks[0].chunk_id, "demo:0000")
            self.assertEqual(chunks[0].milvus_collection, "knowrag_chunks")
            self.assertIn("Root", chunks[0].heading_path_json)

    def test_marks_failed_and_deletes_document_with_chunks(self):
        with TemporaryDirectory() as temp_dir:
            repo = DocumentRepository(f"sqlite:///{Path(temp_dir) / 'app.db'}")
            document = repo.create_document("demo.md", "frontend-upload/demo.md", "# Root", 6)
            repo.save_index_result(document.id, _indexing_result())

            repo.mark_failed(document.id, "boom")
            self.assertEqual(repo.get_document(document.id).status, "failed")
            self.assertEqual(repo.get_document(document.id).error_message, "boom")

            repo.delete_document(document.id)
            self.assertIsNone(repo.find_document(document.id))
            self.assertEqual(repo.list_chunks(document.id), [])


def _indexing_result() -> IndexingResult:
    cleaned = clean_markdown_document("# Root\n\nUseful content.", "demo.md")
    chunking = chunk_cleaned_document(cleaned)
    embedding = EmbeddingResult(
        model="Qwen/Qwen3-VL-Embedding-8B",
        usage=EmbeddingUsage(prompt_tokens=1, total_tokens=1),
        total_vectors=1,
        embeddings=[
            ChunkEmbedding(
                chunk_id="demo:0000",
                chunk_index=0,
                source_path="demo.md",
                document_title="Root",
                heading_path=("Root",),
                content="# Root\n\nUseful content.",
                vector=[0.1, 0.2, 0.3],
                dimension=3,
                token_count=5,
                start_line=1,
                end_line=3,
            )
        ],
    )
    return IndexingResult(
        source_path="demo.md",
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
