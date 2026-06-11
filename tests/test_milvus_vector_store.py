import unittest

from backend.app.schemas.ingestion import (
    ChunkEmbedding,
    EmbeddingResult,
    EmbeddingUsage,
    MilvusStoreConfig,
)
from backend.app.services.milvus_vector_store import MilvusVectorStore
from backend.app.services.milvus_vector_store import _search_hit_to_result


class FakeMilvusClient:
    def __init__(self):
        self.collections = set()
        self.created = []
        self.upserts = []
        self.deletes = []

    def create_schema(self, **kwargs):
        return FakeSchema(kwargs)

    def prepare_index_params(self):
        return FakeIndexParams()

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
        schema = client.created[0]["schema"]
        self.assertEqual(schema.fields[1]["dim"], 4096)
        self.assertEqual(schema.fields[2]["analyzer_params"], {"tokenizer": "jieba"})
        self.assertEqual(schema.functions[0].input_field_names, ["text"])
        self.assertEqual(client.created[0]["index_params"].indexes[1]["metric_type"], "BM25")
        point = client.upserts[0]["data"][0]
        self.assertEqual(point["id"], "demo:0000")
        self.assertEqual(point["vector"], [0.1] * 4096)
        self.assertEqual(point["source_path"], "docs/demo.md")
        self.assertEqual(point["heading_path"], ["Root", "Child"])
        self.assertEqual(point["heading_path_json"], "[\"Root\", \"Child\"]")
        self.assertIn("Useful content", point["content"])
        self.assertTrue(point["content_b64"])
        self.assertIn("Root > Child", point["text"])

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

    def test_preserves_hybrid_ranker_score(self):
        result = _search_hit_to_result(
            {
                "id": "demo:0000",
                "distance": 0.032,
                "entity": {
                    "chunk_id": "demo:0000",
                    "source_path": "docs/demo.md",
                    "document_title": "Root",
                },
            }
        )

        self.assertEqual(result.score, 0.032)


class FakeSchema:
    def __init__(self, options):
        self.options = options
        self.fields = []
        self.functions = []

    def add_field(self, name, data_type, **kwargs):
        self.fields.append({"name": name, "data_type": data_type, **kwargs})

    def add_function(self, function):
        self.functions.append(function)


class FakeIndexParams:
    def __init__(self):
        self.indexes = []

    def add_index(self, **kwargs):
        self.indexes.append(kwargs)


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
