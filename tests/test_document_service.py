from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from backend.app.services.document_repository import DocumentRepository
from backend.app.services.document_service import delete_document_payload, index_document_payload
from tests.test_document_repository import _indexing_result


class DocumentServiceTest(unittest.TestCase):
    def test_delete_document_removes_milvus_vectors_before_local_metadata(self):
        with TemporaryDirectory() as temp_dir:
            repo = DocumentRepository(f"sqlite:///{Path(temp_dir) / 'app.db'}")
            document = repo.create_document("demo.md", "frontend-upload/demo.md", "# Root", 6)
            repo.save_index_result(document.id, _indexing_result())
            vector_store = FakeVectorStore()

            delete_document_payload(document.id, repository=repo, vector_store=vector_store)

            self.assertEqual(vector_store.deleted_ids, ["demo:0000"])
            self.assertIsNone(repo.find_document(document.id))

    def test_reindex_removes_only_stale_previous_vectors(self):
        with TemporaryDirectory() as temp_dir:
            repo = DocumentRepository(f"sqlite:///{Path(temp_dir) / 'app.db'}")
            document = repo.create_document("demo.md", "frontend-upload/demo.md", "# Root", 6)
            repo.save_index_result(document.id, _indexing_result())
            vector_store = FakeVectorStore()

            with patch(
                "backend.app.services.document_service.index_markdown_document",
                return_value=_indexing_result_with_ids(["demo:0001"]),
            ):
                index_document_payload(document.id, repository=repo, vector_store=vector_store)

            self.assertEqual(vector_store.deleted_ids, ["demo:0000"])
            self.assertEqual(repo.list_chunks(document.id)[0].milvus_id, "demo:0001")


class FakeVectorStore:
    def __init__(self):
        self.deleted_ids = []

    def delete_chunk_ids(self, ids):
        self.deleted_ids.extend(ids)
        return len(ids)


def _indexing_result_with_ids(ids):
    result = _indexing_result()
    embedding_type = type(result.embedding.embeddings[0])
    embeddings = []
    for index, chunk_id in enumerate(ids):
        source = result.embedding.embeddings[0]
        embeddings.append(
            embedding_type(
                chunk_id=chunk_id,
                chunk_index=index,
                source_path=source.source_path,
                document_title=source.document_title,
                heading_path=source.heading_path,
                content=source.content,
                vector=source.vector,
                dimension=source.dimension,
                token_count=source.token_count,
                start_line=source.start_line,
                end_line=source.end_line,
            )
        )
    return type(result)(
        source_path=result.source_path,
        document_title=result.document_title,
        cleaned=result.cleaned,
        chunking=result.chunking,
        embedding=type(result.embedding)(
            model=result.embedding.model,
            embeddings=embeddings,
            usage=result.embedding.usage,
            total_vectors=len(embeddings),
        ),
        store=type(result.store)(
            collection_name=result.store.collection_name,
            stored_count=len(embeddings),
            dimension=result.store.dimension,
            metric_type=result.store.metric_type,
            ids=list(ids),
        ),
    )


if __name__ == "__main__":
    unittest.main()
