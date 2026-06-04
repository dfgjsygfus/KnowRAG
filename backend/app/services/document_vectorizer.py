from __future__ import annotations

from pathlib import Path

from backend.app.schemas.ingestion import (
    ChunkingConfig,
    EmbeddingConfig,
    IndexingResult,
    MilvusStoreConfig,
    VectorizationResult,
)
from backend.app.services.chunk_embedder import EmbeddingClient, embed_chunking_result
from backend.app.services.document_chunker import chunk_cleaned_document
from backend.app.services.markdown_cleaner import clean_markdown_document
from backend.app.services.milvus_vector_store import MilvusVectorStore


def vectorize_markdown_document(
    markdown: str,
    source_path: str | Path = "",
    client: EmbeddingClient | None = None,
    chunking_config: ChunkingConfig | None = None,
    embedding_config: EmbeddingConfig | None = None,
) -> VectorizationResult:
    """执行 Markdown 离线向量化流水线：清洗 -> 切分 -> embedding。"""

    cleaned = clean_markdown_document(markdown, source_path=source_path)
    chunking = chunk_cleaned_document(cleaned, chunking_config)
    embedding = embed_chunking_result(chunking, client=client, config=embedding_config)

    return VectorizationResult(
        source_path=str(source_path),
        document_title=cleaned.title,
        cleaned=cleaned,
        chunking=chunking,
        embedding=embedding,
    )


def vectorize_markdown_file(
    path: str | Path,
    client: EmbeddingClient | None = None,
    chunking_config: ChunkingConfig | None = None,
    embedding_config: EmbeddingConfig | None = None,
    encoding: str = "utf-8",
) -> VectorizationResult:
    """从本地 Markdown 文件读取内容并完成离线向量化。"""

    markdown_path = Path(path)
    markdown = markdown_path.read_text(encoding=encoding)
    return vectorize_markdown_document(
        markdown,
        source_path=markdown_path,
        client=client,
        chunking_config=chunking_config,
        embedding_config=embedding_config,
    )


def index_markdown_document(
    markdown: str,
    source_path: str | Path = "",
    client: EmbeddingClient | None = None,
    vector_store: MilvusVectorStore | None = None,
    chunking_config: ChunkingConfig | None = None,
    embedding_config: EmbeddingConfig | None = None,
    store_config: MilvusStoreConfig | None = None,
) -> IndexingResult:
    """执行 Markdown 离线入库流水线：清洗 -> 切分 -> embedding -> Milvus。"""

    vectorized = vectorize_markdown_document(
        markdown,
        source_path=source_path,
        client=client,
        chunking_config=chunking_config,
        embedding_config=embedding_config,
    )
    store = vector_store or MilvusVectorStore(config=store_config)
    store_result = store.upsert_embeddings(vectorized.embedding)

    return IndexingResult(
        source_path=vectorized.source_path,
        document_title=vectorized.document_title,
        cleaned=vectorized.cleaned,
        chunking=vectorized.chunking,
        embedding=vectorized.embedding,
        store=store_result,
    )
