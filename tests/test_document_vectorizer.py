import unittest

from backend.app.schemas.ingestion import ChunkingConfig, EmbeddingConfig
from backend.app.services.document_vectorizer import vectorize_markdown_document


class FakeEmbeddingClient:
    def embed_texts(self, texts, config):
        return {
            "model": config.model,
            "embeddings": [[1.0, 2.0, 3.0] for _ in texts],
            "usage": {"prompt_tokens": len(texts), "completion_tokens": 0, "total_tokens": len(texts)},
        }


class DocumentVectorizerTest(unittest.TestCase):
    def test_vectorizes_markdown_through_clean_chunk_and_embedding_pipeline(self):
        markdown = "# Root\n\n## Child\n\nUseful knowledge content for the vector store."

        result = vectorize_markdown_document(
            markdown,
            source_path="pipeline.md",
            client=FakeEmbeddingClient(),
            chunking_config=ChunkingConfig(max_tokens=80, min_tokens=1),
            embedding_config=EmbeddingConfig(batch_size=4),
        )

        self.assertEqual(result.source_path, "pipeline.md")
        self.assertEqual(result.document_title, "Root")
        self.assertEqual(result.chunking.total_chunks, result.embedding.total_vectors)
        self.assertEqual(result.embedding.embeddings[0].vector, [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
