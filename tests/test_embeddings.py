import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os

from backend.app.schemas.ingestion import (
    ChunkingConfig,
    EmbeddingConfig,
)
from backend.app.services.chunk_embedder import embed_chunking_result
from backend.app.services.document_chunker import chunk_cleaned_document
from backend.app.services.markdown_cleaner import clean_markdown_document
from backend.app.services.siliconflow_embeddings import SiliconFlowEmbeddingClient


class FakeEmbeddingClient:
    def __init__(self):
        self.calls = []

    def embed_texts(self, texts, config):
        self.calls.append((list(texts), config))
        start = sum(len(call[0]) for call in self.calls[:-1])
        vectors = [[float(start + index), 1.0, 2.0] for index, _ in enumerate(texts)]
        return {
            "model": config.model,
            "embeddings": vectors,
            "usage": {"prompt_tokens": len(texts), "completion_tokens": 0, "total_tokens": len(texts)},
        }


class EmbeddingsTest(unittest.TestCase):
    def test_embeds_chunks_and_preserves_chunk_metadata(self):
        document = clean_markdown_document(
            "# Root\n\n## Child\n\nThis is useful content for retrieval.",
            source_path="demo.md",
        )
        chunks = chunk_cleaned_document(document, ChunkingConfig(max_tokens=80, min_tokens=1))

        result = embed_chunking_result(chunks, client=FakeEmbeddingClient(), config=EmbeddingConfig(batch_size=8))

        self.assertEqual(result.model, "Qwen/Qwen3-VL-Embedding-8B")
        self.assertEqual(result.total_vectors, len(chunks.chunks))
        first = result.embeddings[0]
        self.assertEqual(first.chunk_id, chunks.chunks[0].chunk_id)
        self.assertEqual(first.source_path, "demo.md")
        self.assertEqual(first.heading_path, chunks.chunks[0].heading_path)
        self.assertEqual(first.dimension, 3)
        self.assertEqual(first.vector, [0.0, 1.0, 2.0])

    def test_batches_requests_and_keeps_embedding_order(self):
        document = clean_markdown_document(
            "# Root\n\n" + "\n\n".join(f"## H{i}\n\nContent {i} " * 12 for i in range(5)),
            source_path="batch.md",
        )
        chunks = chunk_cleaned_document(document, ChunkingConfig(max_tokens=20, min_tokens=1, overlap_tokens=0))
        fake_client = FakeEmbeddingClient()

        result = embed_chunking_result(chunks, client=fake_client, config=EmbeddingConfig(batch_size=2))

        self.assertGreater(len(fake_client.calls), 1)
        self.assertEqual([embedding.chunk_index for embedding in result.embeddings], list(range(len(result.embeddings))))
        self.assertEqual(result.embeddings[0].vector[0], 0.0)
        self.assertEqual(result.embeddings[-1].vector[0], float(len(result.embeddings) - 1))

    def test_siliconflow_client_builds_embeddings_request_payload(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "model": payload["model"],
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2]},
                    {"index": 1, "embedding": [0.3, 0.4]},
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 0, "total_tokens": 2},
            }

        client = SiliconFlowEmbeddingClient(api_key="test-key", transport=transport)
        response = client.embed_texts(["one", "two"], EmbeddingConfig(user="rag-test", truncate=True))

        self.assertEqual(response["embeddings"], [[0.1, 0.2], [0.3, 0.4]])
        url, headers, payload, timeout = calls[0]
        self.assertEqual(url, "https://api.siliconflow.cn/v1/embeddings")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "Qwen/Qwen3-VL-Embedding-8B")
        self.assertEqual(payload["input"], ["one", "two"])
        self.assertEqual(payload["encoding_format"], "float")
        self.assertEqual(payload["user"], "rag-test")
        self.assertTrue(payload["truncate"])
        self.assertEqual(timeout, 60)

    def test_siliconflow_client_reads_api_key_from_dotenv_when_env_is_missing(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "model": payload["model"],
                "data": [{"index": 0, "embedding": [0.1, 0.2]}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
            }

        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                Path(".env").write_text("SILICONFLOW_API_KEY=dotenv-key\n", encoding="utf-8")
                client = SiliconFlowEmbeddingClient(transport=transport)
                client.embed_texts(["one"], EmbeddingConfig())
            finally:
                os.chdir(cwd)

        self.assertEqual(calls[0][1]["Authorization"], "Bearer dotenv-key")


if __name__ == "__main__":
    unittest.main()
