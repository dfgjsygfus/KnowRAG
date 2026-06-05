import unittest

from backend.app.schemas.ingestion import (
    ChunkEmbedding,
    EmbeddingResult,
    EmbeddingUsage,
    MilvusStoreConfig,
)
from backend.app.services.milvus_vector_store import MilvusVectorStore


class FakeMilvusClient:
    def __init__(self):
        self.collections = set()
        self.created = []
        self.upserts = []
        self.deletes = []

    def has_collection(self, collection_name):
        return collection_name in self.collections

    def create_collection(self, **kwargs):
        self.created.append(kwargs)
        self.collections.add(kwargs["collection_name"])

    def upsert(self, collection_name, data):
        self.upserts.append({"collection_name": collection_name, "data": data})
        return {"upsert_count": len(data)}

    def delete(self, collection_name, ids):
        self.deletes.append({"collection_name": collection_name, "ids": ids})


class MilvusVectorStoreTest(unittest.TestCase):
    def test_creates_collection_and_upserts_embedding_payload(self):
        client = FakeMilvusClient()
        store = MilvusVectorStore(
            client=client,
            config=MilvusStoreConfig(
                uri="http://localhost:19530",
                collection_name="knowrag_chunks",
                vector_dim=4096,
                metric_type="COSINE",
            ),
        )

        result = store.upsert_embeddings(_embedding_result())

        self.assertEqual(result.collection_name, "knowrag_chunks")
        self.assertEqual(result.stored_count, 1)
        self.assertEqual(result.dimension, 4096)
        self.assertEqual(result.metric_type, "COSINE")
        self.assertEqual(client.created[0]["dimension"], 4096)
        self.assertEqual(client.created[0]["metric_type"], "COSINE")
        self.assertEqual(client.created[0]["id_type"], "string")
        point = client.upserts[0]["data"][0]
        self.assertEqual(point["id"], "demo:0000")
        self.assertEqual(point["vector"], [0.1] * 4096)
        self.assertEqual(point["source_path"], "docs/demo.md")
        self.assertEqual(point["heading_path"], ["Root", "Child"])
        self.assertEqual(point["heading_path_json"], "[\"Root\", \"Child\"]")
        self.assertIn("Useful content", point["content"])
        self.assertTrue(point["content_b64"])

    def test_uses_existing_collection_without_creating_again(self):
        client = FakeMilvusClient()
        client.collections.add("knowrag_chunks")
        store = MilvusVectorStore(client=client, config=MilvusStoreConfig(collection_name="knowrag_chunks"))

        store.upsert_embeddings(_embedding_result())

        self.assertEqual(client.created, [])
        self.assertEqual(len(client.upserts), 1)

    def test_deletes_chunks_by_vector_id(self):
        client = FakeMilvusClient()
        client.collections.add("knowrag_chunks")
        store = MilvusVectorStore(client=client, config=MilvusStoreConfig(collection_name="knowrag_chunks"))

        deleted_count = store.delete_chunk_ids(["demo:0000", "demo:0001"])

        self.assertEqual(deleted_count, 2)
        self.assertEqual(
            client.deletes,
            [{"collection_name": "knowrag_chunks", "ids": ["demo:0000", "demo:0001"]}],
        )


def _embedding_result() -> EmbeddingResult:
    return EmbeddingResult(
        model="Qwen/Qwen3-VL-Embedding-8B",
        usage=EmbeddingUsage(prompt_tokens=1, total_tokens=1),
        total_vectors=1,
        embeddings=[
            ChunkEmbedding(
                chunk_id="demo:0000",
                chunk_index=0,
                source_path="docs/demo.md",
                document_title="Root",
                heading_path=("Root", "Child"),
                content="Useful content",
                vector=[0.1] * 4096,
                dimension=4096,
                token_count=12,
                start_line=1,
                end_line=3,
            )
        ],
    )


if __name__ == "__main__":
    unittest.main()
