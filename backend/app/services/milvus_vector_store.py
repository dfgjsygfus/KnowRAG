from __future__ import annotations

import base64
import json
from typing import Any

from backend.app.schemas.ingestion import (
    EmbeddingResult,
    MilvusStoreConfig,
    VectorStoreResult,
)
from backend.app.schemas.retrieval import RetrievalResult, RetrievalSearchResult


class MilvusVectorStoreError(RuntimeError):
    """Milvus 向量库操作失败。"""


class MilvusVectorStore:
    """Milvus 向量入库服务。"""

    def __init__(self, client: Any | None = None, config: MilvusStoreConfig | None = None) -> None:
        self.config = config or MilvusStoreConfig()
        self.client = client or _create_milvus_client(self.config)

    def ensure_collection(self, dimension: int | None = None) -> None:
        """确保 collection 存在；不存在时按 embedding 维度创建。"""

        if self.client.has_collection(self.config.collection_name):
            return

        self.client.create_collection(
            collection_name=self.config.collection_name,
            dimension=dimension or self.config.vector_dim,
            primary_field_name="id",
            id_type="string",
            vector_field_name="vector",
            metric_type=self.config.metric_type,
            auto_id=False,
            max_length=512,
            enable_dynamic_field=True,
        )

    def upsert_embeddings(self, embedding_result: EmbeddingResult) -> VectorStoreResult:
        """把 embedding 结果 upsert 到 Milvus。"""

        if not embedding_result.embeddings:
            return VectorStoreResult(
                collection_name=self.config.collection_name,
                stored_count=0,
                dimension=self.config.vector_dim,
                metric_type=self.config.metric_type,
                ids=[],
            )

        dimension = embedding_result.embeddings[0].dimension
        self.ensure_collection(dimension)
        points = [_embedding_to_point(embedding) for embedding in embedding_result.embeddings]
        response = self.client.upsert(collection_name=self.config.collection_name, data=points)

        return VectorStoreResult(
            collection_name=self.config.collection_name,
            stored_count=int(response.get("upsert_count", len(points)) if isinstance(response, dict) else len(points)),
            dimension=dimension,
            metric_type=self.config.metric_type,
            ids=[point["id"] for point in points],
        )

    def delete_chunk_ids(self, chunk_ids: list[str]) -> int:
        """按向量主键删除 chunk；空列表直接返回，避免无意义请求。"""

        unique_ids = list(dict.fromkeys(chunk_id for chunk_id in chunk_ids if chunk_id))
        if not unique_ids:
            return 0
        if not self.client.has_collection(self.config.collection_name):
            return 0

        self.client.delete(collection_name=self.config.collection_name, ids=unique_ids)
        return len(unique_ids)

    def search_chunks(self, query: str, query_vector: list[float], top_k: int = 5) -> RetrievalResult:
        """按 query 向量检索 Milvus 中最相近的 chunk。"""

        if not self.client.has_collection(self.config.collection_name):
            raise MilvusVectorStoreError(f"Milvus collection `{self.config.collection_name}` does not exist.")

        raw_results = self.client.search(
            collection_name=self.config.collection_name,
            data=[query_vector],
            limit=top_k,
            output_fields=[
                "chunk_id",
                "chunk_index",
                "source_path",
                "document_title",
                "heading_path_json",
                "heading_path",
                "content",
                "content_b64",
                "token_count",
                "start_line",
                "end_line",
            ],
            search_params={"metric_type": self.config.metric_type},
        )
        first_group = raw_results[0] if raw_results else []
        results = [_search_hit_to_result(hit) for hit in first_group]
        return RetrievalResult(
            query=query,
            top_k=top_k,
            collection_name=self.config.collection_name,
            total=len(results),
            results=results,
        )


def _create_milvus_client(config: MilvusStoreConfig):
    """延迟导入 pymilvus，避免未安装时影响清洗/切分/向量化功能。"""

    try:
        from pymilvus import MilvusClient
    except ImportError as exc:
        raise MilvusVectorStoreError("Missing pymilvus dependency. Install it with `pip install pymilvus`.") from exc

    kwargs: dict[str, Any] = {"uri": config.uri}
    if config.token:
        kwargs["token"] = config.token
    try:
        return MilvusClient(**kwargs, timeout=config.timeout_seconds)
    except Exception as exc:
        raise MilvusVectorStoreError(f"Failed to connect to Milvus at {config.uri}: {exc}") from exc


def _embedding_to_point(embedding) -> dict[str, Any]:
    """把内部 ChunkEmbedding 转成 Milvus upsert 所需的数据行。"""

    return {
        "id": embedding.chunk_id,
        "vector": embedding.vector,
        "chunk_id": embedding.chunk_id,
        "chunk_index": embedding.chunk_index,
        "source_path": embedding.source_path,
        "document_title": embedding.document_title,
        "heading_path": list(embedding.heading_path),
        "heading_path_json": json.dumps(list(embedding.heading_path), ensure_ascii=True),
        "heading_path_text": " > ".join(embedding.heading_path),
        "content": embedding.content,
        "content_b64": base64.b64encode(embedding.content.encode("utf-8")).decode("ascii"),
        "token_count": embedding.token_count,
        "start_line": embedding.start_line,
        "end_line": embedding.end_line,
    }


def _search_hit_to_result(hit: dict[str, Any]) -> RetrievalSearchResult:
    """把 Milvus search 的命中行整理为前端检索结果。"""

    entity = hit.get("entity") or {}
    raw_score = float(hit.get("distance", hit.get("score", 0.0)) or 0.0)
    return RetrievalSearchResult(
        chunk_id=str(entity.get("chunk_id") or hit.get("id") or ""),
        score=raw_score,
        document_title=str(entity.get("document_title") or ""),
        source_path=str(entity.get("source_path") or ""),
        heading_path=_parse_heading_path(entity),
        content=_parse_content(entity),
        token_count=int(entity.get("token_count", 0) or 0),
        start_line=int(entity.get("start_line", 0) or 0),
        end_line=int(entity.get("end_line", 0) or 0),
    )


def _parse_heading_path(entity: dict[str, Any]) -> tuple[str, ...]:
    raw_json = entity.get("heading_path_json")
    if isinstance(raw_json, str) and raw_json:
        try:
            decoded = json.loads(raw_json)
            if isinstance(decoded, list):
                return tuple(str(item) for item in decoded)
        except json.JSONDecodeError:
            pass

    raw_path = entity.get("heading_path")
    if isinstance(raw_path, list):
        return tuple(str(item) for item in raw_path)
    return ()


def _parse_content(entity: dict[str, Any]) -> str:
    raw_b64 = entity.get("content_b64")
    if isinstance(raw_b64, str) and raw_b64:
        try:
            return base64.b64decode(raw_b64.encode("ascii")).decode("utf-8")
        except Exception:
            pass
    return str(entity.get("content") or "")
