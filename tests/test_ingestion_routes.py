import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.schemas.ingestion import EmbeddingConfig
from backend.app.services.document_vectorizer import vectorize_markdown_document
from main import app


client = TestClient(app)


class IngestionRoutesTest(unittest.TestCase):
    def test_clean_route_returns_cleaned_sections(self):
        response = client.post(
            "/api/ingestion/clean",
            json={
                "source_path": "demo.md",
                "markdown": "# Root\n\n![](<images/a.png>)\n\n## Child\n\nUseful text.",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_path"], "demo.md")
        self.assertEqual(body["document_title"], "Root")
        self.assertEqual(body["sections_count"], 2)
        self.assertNotIn("images/a.png", body["cleaned_text"])
        self.assertEqual(body["sections"][1]["heading_path"], ["Root", "Child"])

    def test_chunk_route_returns_chunk_metadata(self):
        response = client.post(
            "/api/ingestion/chunk",
            json={
                "source_path": "demo.md",
                "markdown": "# Root\n\n## Child\n\n" + "Useful content. " * 12,
                "max_tokens": 80,
                "min_tokens": 1,
                "overlap_tokens": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_path"], "demo.md")
        self.assertEqual(body["document_title"], "Root")
        self.assertGreaterEqual(body["chunks_count"], 1)
        self.assertEqual(body["chunks"][0]["chunk_index"], 0)
        self.assertEqual(body["chunks"][0]["heading_path"], ["Root", "Child"])

    def test_vectorize_route_returns_vector_preview_without_full_vectors_by_default(self):
        real_result = vectorize_markdown_document(
            "# Root\n\n## Child\n\nUseful content.",
            source_path="demo.md",
            client=_FakeEmbeddingClient(),
            embedding_config=EmbeddingConfig(batch_size=4),
        )

        with patch("backend.app.services.ingestion_pipeline.vectorize_markdown_document", return_value=real_result):
            response = client.post(
                "/api/ingestion/vectorize",
                json={
                    "source_path": "demo.md",
                    "markdown": "# Root\n\n## Child\n\nUseful content.",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["vectors_count"], 1)
        self.assertEqual(body["model"], "Qwen/Qwen3-VL-Embedding-8B")
        self.assertEqual(body["embeddings"][0]["dimension"], 4)
        self.assertEqual(body["embeddings"][0]["vector_preview"], [1.0, 2.0, 3.0, 4.0])
        self.assertNotIn("vector", body["embeddings"][0])

    def test_index_route_returns_store_summary(self):
        with patch(
            "backend.app.api.ingestion.index_markdown_payload",
            return_value={
                "source_path": "demo.md",
                "document_title": "Root",
                "sections_count": 2,
                "chunks_count": 1,
                "vectors_count": 1,
                "stored_count": 1,
                "collection_name": "knowrag_chunks",
                "dimension": 4096,
                "metric_type": "COSINE",
                "ids": ["demo:0000"],
            },
        ):
            response = client.post(
                "/api/ingestion/index",
                json={
                    "source_path": "demo.md",
                    "markdown": "# Root\n\n## Child\n\nUseful content.",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stored_count"], 1)
        self.assertEqual(body["collection_name"], "knowrag_chunks")
        self.assertEqual(body["dimension"], 4096)
        self.assertEqual(body["metric_type"], "COSINE")


class _FakeEmbeddingClient:
    def embed_texts(self, texts, config):
        return {
            "model": config.model,
            "embeddings": [[1.0, 2.0, 3.0, 4.0] for _ in texts],
            "usage": {"prompt_tokens": len(texts), "completion_tokens": 0, "total_tokens": len(texts)},
        }


if __name__ == "__main__":
    unittest.main()
