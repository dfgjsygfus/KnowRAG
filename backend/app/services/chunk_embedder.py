from __future__ import annotations

from typing import Protocol

from backend.app.schemas.ingestion import (
    ChunkEmbedding,
    ChunkingResult,
    EmbeddingConfig,
    EmbeddingResult,
    EmbeddingUsage,
)
from backend.app.services.siliconflow_embeddings import SiliconFlowEmbeddingClient


class EmbeddingClient(Protocol):
    def embed_texts(self, texts: list[str], config: EmbeddingConfig) -> dict:
        """把一批文本转成向量。"""


def embed_chunking_result(
    chunking_result: ChunkingResult,
    client: EmbeddingClient | None = None,
    config: EmbeddingConfig | None = None,
) -> EmbeddingResult:
    """对切分结果批量向量化，并把向量映射回 chunk 元数据。"""

    config = config or EmbeddingConfig()
    client = client or SiliconFlowEmbeddingClient()

    all_embeddings: list[ChunkEmbedding] = []
    usage = EmbeddingUsage()

    for batch_start in range(0, len(chunking_result.chunks), config.batch_size):
        batch_chunks = chunking_result.chunks[batch_start : batch_start + config.batch_size]
        texts = [_embedding_text(chunk) for chunk in batch_chunks]
        response = client.embed_texts(texts, config)
        usage = _merge_usage(usage, response.get("usage") or {})

        for chunk, vector in zip(batch_chunks, response["embeddings"]):
            all_embeddings.append(
                ChunkEmbedding(
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    source_path=chunk.source_path,
                    document_title=chunk.document_title,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    vector=[float(value) for value in vector],
                    dimension=len(vector),
                    token_count=chunk.token_count,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                )
            )

    return EmbeddingResult(
        model=config.model,
        embeddings=all_embeddings,
        usage=usage,
        total_vectors=len(all_embeddings),
    )


def _embedding_text(chunk) -> str:
    """把标题路径拼进 embedding 文本，提升层级化文档的召回稳定性。"""

    heading_path = " > ".join(chunk.heading_path)
    return (
        f"文档标题：{chunk.document_title}\n"
        f"章节路径：{heading_path}\n\n"
        f"{chunk.content.strip()}"
    ).strip()


def _merge_usage(current: EmbeddingUsage, usage: dict) -> EmbeddingUsage:
    """累加多批请求的 token 用量。"""

    return EmbeddingUsage(
        prompt_tokens=current.prompt_tokens + int(usage.get("prompt_tokens", 0) or 0),
        completion_tokens=current.completion_tokens + int(usage.get("completion_tokens", 0) or 0),
        total_tokens=current.total_tokens + int(usage.get("total_tokens", 0) or 0),
    )
