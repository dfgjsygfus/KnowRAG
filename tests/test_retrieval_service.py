import json
import unittest
from unittest.mock import patch

from backend.app.schemas.ingestion import EmbeddingConfig, MilvusStoreConfig
from backend.app.services.retrieval_service import retrieve_query


class RetrievalServiceTest(unittest.TestCase):
    def test_retrieve_query_embeds_query_and_searches_milvus_chunks(self):
        embedding_client = FakeEmbeddingClient()
        milvus_client = FakeMilvusClient()

        result = retrieve_query(
            "Prompt 设计是什么？",
            top_k=3,
            embedding_client=embedding_client,
            milvus_client=milvus_client,
            embedding_config=EmbeddingConfig(dimensions=3),
            store_config=MilvusStoreConfig(collection_name="knowrag_chunks", vector_dim=3),
        )

        self.assertEqual(embedding_client.texts, ["Prompt 设计是什么？"])
        self.assertEqual(milvus_client.search_calls[0]["collection_name"], "knowrag_chunks")
        self.assertEqual(milvus_client.search_calls[0]["limit"], 3)
        self.assertEqual(milvus_client.search_calls[0]["data"], [[0.1, 0.2, 0.3]])
        self.assertEqual(result.query, "Prompt 设计是什么？")
        self.assertEqual(result.top_k, 3)
        self.assertEqual(result.collection_name, "knowrag_chunks")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.results[0].chunk_id, "demo:0000")
        self.assertEqual(result.results[0].score, 0.82)
        self.assertEqual(result.results[0].heading_path, ("Root", "Prompt 设计"))
        self.assertIn("PLANNING_PROMPT", result.results[0].content)

    def test_retrieve_query_logs_metadata_without_content_or_vectors(self):
        embedding_client = FakeEmbeddingClient()
        milvus_client = FakeMilvusClient()

        with patch(
            "backend.app.services.retrieval_service.get_config_value",
            side_effect=lambda name, default="": "true" if name == "RETRIEVAL_LOG_ENABLED" else default,
        ), self.assertLogs("backend.app.services.retrieval_service", level="INFO") as captured:
            retrieve_query(
                "Prompt 设计是什么？",
                top_k=3,
                embedding_client=embedding_client,
                milvus_client=milvus_client,
                embedding_config=EmbeddingConfig(dimensions=3),
                store_config=MilvusStoreConfig(collection_name="knowrag_chunks", vector_dim=3),
            )

        payload = json.loads(captured.records[-1].getMessage())
        self.assertEqual(payload["event"], "retrieval.completed")
        self.assertEqual(payload["query"], "Prompt 设计是什么？")
        self.assertEqual(payload["hits"], [{"chunk_id": "demo:0000", "score": 0.82}])
        self.assertIn("elapsed_ms", payload)
        self.assertNotIn("content", captured.records[-1].getMessage())
        self.assertNotIn("vector", captured.records[-1].getMessage())


class FakeEmbeddingClient:
    def __init__(self):
        self.texts = []

    def embed_texts(self, texts, config):
        self.texts = texts
        return {
            "model": config.model,
            "embeddings": [[0.1, 0.2, 0.3]],
            "usage": {"prompt_tokens": 5, "completion_tokens": 0, "total_tokens": 5},
        }


class FakeMilvusClient:
    def __init__(self):
        self.search_calls = []

    def has_collection(self, collection_name):
        return collection_name == "knowrag_chunks"

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return [
            [
                {
                    "id": "demo:0000",
                    "distance": 0.82,
                    "entity": {
                        "chunk_id": "demo:0000",
                        "chunk_index": 0,
                        "source_path": "docs/demo.md",
                        "document_title": "Root",
                        "heading_path_json": "[\"Root\", \"Prompt 设计\"]",
                        "content": "PLANNING_PROMPT 用于生成研究大纲。",
                        "token_count": 20,
                        "start_line": 1,
                        "end_line": 8,
                    },
                }
            ]
        ]


if __name__ == "__main__":
    unittest.main()
