from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkdownSection:
    """按最近标题归组后的 Markdown 清洗片段。"""

    heading: str
    heading_path: tuple[str, ...]
    level: int
    content: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class CleanedDocument:
    """供后续切片和索引阶段消费的结构化清洗结果。"""

    source_path: str
    title: str
    cleaned_text: str
    sections: list[MarkdownSection]


@dataclass(frozen=True)
class ChunkingConfig:
    """文档切分参数，后续可以从知识库配置或接口参数传入。"""

    max_tokens: int = 700
    overlap_tokens: int = 100
    min_tokens: int = 80
    preserve_code_blocks: bool = True


@dataclass(frozen=True)
class DocumentChunk:
    """进入 embedding 和向量库前的最小可检索文本单元。"""

    chunk_id: str
    chunk_index: int
    source_path: str
    document_title: str
    heading: str
    heading_path: tuple[str, ...]
    content: str
    token_count: int
    start_line: int
    end_line: int
    section_indexes: tuple[int, ...]


@dataclass(frozen=True)
class ChunkingResult:
    """一次文档切分的完整结果。"""

    source_path: str
    document_title: str
    chunks: list[DocumentChunk]
    total_chunks: int


@dataclass(frozen=True)
class EmbeddingConfig:
    """向量化配置，默认使用硅基流动的 Qwen3-VL Embedding 模型。"""

    model: str = "Qwen/Qwen3-VL-Embedding-8B"
    batch_size: int = 16
    timeout_seconds: int = 60
    encoding_format: str = "float"
    dimensions: int | None = None
    user: str | None = None
    truncate: bool | None = None


@dataclass(frozen=True)
class EmbeddingUsage:
    """向量化接口返回的 token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ChunkEmbedding:
    """一个 chunk 对应的一条向量及其检索元数据。"""

    chunk_id: str
    chunk_index: int
    source_path: str
    document_title: str
    heading_path: tuple[str, ...]
    content: str
    vector: list[float]
    dimension: int
    token_count: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class EmbeddingResult:
    """一次批量向量化的完整结果。"""

    model: str
    embeddings: list[ChunkEmbedding]
    usage: EmbeddingUsage
    total_vectors: int


@dataclass(frozen=True)
class VectorizationResult:
    """清洗、切分、向量化三步离线处理的聚合结果。"""

    source_path: str
    document_title: str
    cleaned: CleanedDocument
    chunking: ChunkingResult
    embedding: EmbeddingResult


@dataclass(frozen=True)
class MilvusStoreConfig:
    """Milvus 向量库配置。"""

    uri: str = "http://localhost:19530"
    token: str = ""
    collection_name: str = "knowrag_chunks"
    vector_dim: int = 4096
    metric_type: str = "COSINE"
    timeout_seconds: int = 60


@dataclass(frozen=True)
class VectorStoreResult:
    """向量入库结果。"""

    collection_name: str
    stored_count: int
    dimension: int
    metric_type: str
    ids: list[str]


@dataclass(frozen=True)
class IndexingResult:
    """清洗、切分、向量化、入库四步离线处理的聚合结果。"""

    source_path: str
    document_title: str
    cleaned: CleanedDocument
    chunking: ChunkingResult
    embedding: EmbeddingResult
    store: VectorStoreResult
