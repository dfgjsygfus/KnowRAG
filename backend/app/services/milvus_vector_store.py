from __future__ import annotations

import base64
import json
import logging
from typing import Any


logger = logging.getLogger(__name__)

# 在导入 pymilvus 之前应用 Windows 兼容性补丁（Milvus Lite 3.0 manifest rename bug）
from backend.app.services import milvus_lite_patch  # noqa: F401

from backend.app.services.app_config import PROJECT_ROOT, get_config_int, get_config_value
from backend.app.schemas.ingestion import (
    EmbeddingResult,
    MilvusStoreConfig,
    VectorStoreResult,
)
from backend.app.schemas.retrieval import RetrievalResult, RetrievalSearchResult


class MilvusVectorStoreError(RuntimeError):
    """Milvus 向量库操作失败。"""


class MilvusVectorStore:
    """Milvus 向量入库 + 原生 BM25 混合检索（Milvus 2.5+）。"""

    def __init__(self, client: Any | None = None, config: MilvusStoreConfig | None = None) -> None:
        self.config = config or MilvusStoreConfig()
        self.client = client or _create_milvus_client(self.config)

    def ensure_collection(self, dimension: int | None = None) -> None:
        """确保 collection 存在且 schema 兼容；不兼容时自动重建。"""

        from pymilvus import DataType, Function, FunctionType

        collection_name = self.config.collection_name
        target_fields = _required_schema_fields(dimension or self.config.vector_dim)

        if self.client.has_collection(collection_name):
            existing = self.client.describe_collection(collection_name)
            existing_names = {field["name"] for field in existing.get("fields", [])}
            required_names = set(target_fields.keys())
            if required_names.issubset(existing_names):
                self.client.load_collection(collection_name)
                return

            logger.warning(
                "Collection %s schema is stale (missing %s). Dropping and recreating.",
                collection_name,
                sorted(required_names - existing_names),
            )
            self.client.drop_collection(collection_name)

        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        for name, spec in target_fields.items():
            schema.add_field(name, **spec)

        bm25_fn = Function(
            name="bm25_fn",
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse_bm25"],
        )
        schema.add_function(bm25_fn)

        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type=self.config.metric_type)
        index_params.add_index(field_name="sparse_bm25", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")

        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )
        self.client.load_collection(collection_name)

    def upsert_embeddings(self, embedding_result: EmbeddingResult) -> VectorStoreResult:
        """把 embedding 结果 upsert 到 Milvus（text 字段由 BM25 函数自动生成 sparse_bm25）。"""

        if not embedding_result.embeddings:
            return VectorStoreResult(
                collection_name=self.config.collection_name,
                stored_count=0, dimension=self.config.vector_dim,
                metric_type=self.config.metric_type, ids=[],
            )

        dimension = embedding_result.embeddings[0].dimension
        self.ensure_collection(dimension)
        points = [_embedding_to_point(embedding) for embedding in embedding_result.embeddings]
        response = self.client.upsert(collection_name=self.config.collection_name, data=points)

        return VectorStoreResult(
            collection_name=self.config.collection_name,
            stored_count=int(response.get("upsert_count", len(points)) if isinstance(response, dict) else len(points)),
            dimension=dimension, metric_type=self.config.metric_type,
            ids=[point["id"] for point in points],
        )

    def delete_chunk_ids(self, chunk_ids: list[str]) -> int:
        unique_ids = list(dict.fromkeys(chunk_id for chunk_id in chunk_ids if chunk_id))
        if not unique_ids or not self.client.has_collection(self.config.collection_name):
            return 0
        self.client.delete(collection_name=self.config.collection_name, ids=unique_ids)
        return len(unique_ids)

    def search_chunks(self, query: str, query_vector: list[float], top_k: int = 5) -> RetrievalResult:
        """原生 BM25 混合检索 + RRF 融合。"""

        self.ensure_collection()

        from pymilvus import AnnSearchRequest, WeightedRanker

        candidate_limit = _candidate_limit(top_k)
        dense_req = AnnSearchRequest(
            data=[query_vector], anns_field="vector",
            param={"metric_type": self.config.metric_type}, limit=candidate_limit,
        )
        sparse_req = AnnSearchRequest(
            data=[query], anns_field="sparse_bm25",
            param={"metric_type": "BM25"}, limit=candidate_limit,
        )
        ranker = WeightedRanker(_dense_weight(), _sparse_weight())

        raw_results = self.client.hybrid_search(
            collection_name=self.config.collection_name,
            reqs=[dense_req, sparse_req], ranker=ranker, limit=top_k,
            output_fields=_output_fields(),
        )
        first_group = raw_results[0] if raw_results else []
        results = [_search_hit_to_result(hit) for hit in first_group]
        return RetrievalResult(
            query=query, top_k=top_k,
            collection_name=self.config.collection_name,
            total=len(results), results=results,
        )


# ── helpers ──────────────────────────────────────────────────────────

def _required_schema_fields(vector_dim: int) -> dict[str, dict[str, Any]]:
    """当前代码依赖的全部字段定义；用于创建/校验 collection schema。"""

    from pymilvus import DataType

    return {
        "id": {"datatype": DataType.VARCHAR, "is_primary": True, "max_length": 512},
        "vector": {"datatype": DataType.FLOAT_VECTOR, "dim": vector_dim},
        "text": {
            "datatype": DataType.VARCHAR,
            "max_length": 65535,
            "enable_analyzer": True,
            "analyzer_params": {"tokenizer": "jieba"},
        },
        "sparse_bm25": {"datatype": DataType.SPARSE_FLOAT_VECTOR},
        "chunk_id": {"datatype": DataType.VARCHAR, "max_length": 512},
        "chunk_index": {"datatype": DataType.INT64},
        "source_path": {"datatype": DataType.VARCHAR, "max_length": 4096},
        "document_title": {"datatype": DataType.VARCHAR, "max_length": 1024},
        "heading_path_json": {"datatype": DataType.VARCHAR, "max_length": 4096},
        "heading_path": {
            "datatype": DataType.ARRAY,
            "element_type": DataType.VARCHAR,
            "max_length": 512,
            "max_capacity": 64,
        },
        "content": {"datatype": DataType.VARCHAR, "max_length": 65535},
        "content_b64": {"datatype": DataType.VARCHAR, "max_length": 65535},
        "token_count": {"datatype": DataType.INT64},
        "start_line": {"datatype": DataType.INT64},
        "end_line": {"datatype": DataType.INT64},
    }


def _output_fields() -> list[str]:
    return [
        "chunk_id", "chunk_index", "source_path", "document_title",
        "heading_path_json", "heading_path", "content", "content_b64",
        "token_count", "start_line", "end_line",
    ]


def _candidate_limit(top_k: int) -> int:
    configured = get_config_int("RETRIEVAL_CANDIDATE_LIMIT", 0)
    if configured > 0:
        return configured
    return max(top_k * 4, 20)


def _dense_weight() -> float:
    return _config_float("RETRIEVAL_DENSE_WEIGHT", 0.1)


def _sparse_weight() -> float:
    return _config_float("RETRIEVAL_SPARSE_WEIGHT", 0.9)


def _config_float(name: str, default: float) -> float:
    value = get_config_value(name)
    return float(value) if value else default


def _create_milvus_client(config: MilvusStoreConfig):
    try:
        from pymilvus import MilvusClient
    except ImportError as exc:
        raise MilvusVectorStoreError("Missing pymilvus.") from exc

    uri = _resolve_milvus_uri(config)
    kwargs: dict[str, Any] = {"uri": uri}
    if config.token:
        kwargs["token"] = config.token
    try:
        return MilvusClient(**kwargs, timeout=config.timeout_seconds)
    except Exception as exc:
        raise MilvusVectorStoreError(f"Failed to connect to Milvus at {uri}: {exc}") from exc


def _resolve_milvus_uri(config: MilvusStoreConfig) -> str:
    """根据配置选择 Milvus 服务地址或本地 Milvus Lite db 路径。"""

    if config.lite_enabled:
        lite_path = config.lite_path.strip()
        if not lite_path:
            raise MilvusVectorStoreError("MILVUS_LITE_PATH is empty but MILVUS_LITE_ENABLED=true")
        if lite_path.startswith("http://") or lite_path.startswith("https://") or lite_path.startswith("/"):
            return lite_path
        db_path = PROJECT_ROOT / lite_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return str(db_path.resolve())

    uri = config.uri.strip()
    if not uri:
        raise MilvusVectorStoreError("MILVUS_URI is empty and MILVUS_LITE_ENABLED=false")
    return uri


def _embedding_to_point(embedding) -> dict[str, Any]:
    heading_text = " > ".join(embedding.heading_path)
    text = f"{embedding.document_title}\n{heading_text}\n{embedding.content}"

    return {
        "id": embedding.chunk_id,
        "vector": embedding.vector,
        "chunk_id": embedding.chunk_id,
        "chunk_index": embedding.chunk_index,
        "source_path": embedding.source_path,
        "document_title": embedding.document_title,
        "heading_path": list(embedding.heading_path),
        "heading_path_json": json.dumps(list(embedding.heading_path), ensure_ascii=True),
        "heading_path_text": heading_text,
        "content": embedding.content,
        "content_b64": base64.b64encode(embedding.content.encode("utf-8")).decode("ascii"),
        "text": text,
        "token_count": embedding.token_count,
        "start_line": embedding.start_line,
        "end_line": embedding.end_line,
    }


def _search_hit_to_result(hit: dict[str, Any]) -> RetrievalSearchResult:
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
