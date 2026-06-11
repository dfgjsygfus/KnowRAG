from __future__ import annotations

from typing import Any

from backend.app.services.app_config import get_config_value


class RerankerError(RuntimeError):
    """重排序失败。"""


class CrossEncoderReranker:
    """Cross-Encoder 精排器，对粗排候选做逐对打分。"""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self._model_name = model_name or get_config_value(
            "RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
        )
        self._device = device or get_config_value("RERANKER_DEVICE", "cpu")
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self._model_name,
                    device=self._device,
                    trust_remote_code=True,
                )
            except ImportError:
                raise RerankerError(
                    "sentence-transformers not installed. Run: pip install sentence-transformers"
                )
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        candidates: [{"chunk_id": ..., "content": ..., "score": ..., ...}, ...]
        返回按 rerank 分数降序的 top_k 条，附原始粗排分数。
        """

        if not candidates:
            return []

        pairs = [(query, self._rerank_text(c)) for c in candidates]
        scores = self.model.predict(
            pairs,
            batch_size=32,
            show_progress_bar=False,
            convert_to_tensor=True,
        )

        reranked = []
        for candidate, score in zip(candidates, scores):
            reranked.append({**candidate, "rerank_score": round(float(score), 6)})

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]

    def _rerank_text(self, candidate: dict[str, Any]) -> str:
        heading = ""
        hp = candidate.get("heading_path")
        if isinstance(hp, (list, tuple)):
            heading = " > ".join(str(h) for h in hp)
        elif isinstance(hp, str):
            heading = hp

        content = str(candidate.get("content") or "")
        if heading:
            return f"{heading}\n{content}"
        return content
