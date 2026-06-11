from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


_BM25_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "bm25_vocab.json")


class BM25SparseEncoder:
    """共享词表的 BM25 稀疏编码器，入库和查询使用同一 vocabulary。"""

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._is_fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted and self._vectorizer is not None

    def fit(self, texts: list[str]) -> None:
        self._vectorizer = TfidfVectorizer(
            use_idf=True, norm=None, analyzer="char_wb",
            ngram_range=(1, 4), max_features=8192,
        )
        self._vectorizer.fit(texts)
        self._is_fitted = True

    def encode(self, text: str) -> dict[int, float]:
        if not self._vectorizer or not self._is_fitted:
            return {}
        row = self._vectorizer.transform([text])
        return {int(idx): float(val) for idx, val in zip(row.indices, row.data)
                if val > 0 and int(idx) < 65536}

    def save(self, path: str | None = None) -> None:
        if not self._vectorizer or not self._is_fitted:
            raise RuntimeError("BM25SparseEncoder not fitted")
        target = path or _BM25_VOCAB_PATH
        os.makedirs(os.path.dirname(target), exist_ok=True)
        data = {
            "vocabulary": {str(k): int(v) for k, v in self._vectorizer.vocabulary_.items()},
            "idf": [float(x) for x in self._vectorizer.idf_],
            "ngram_range": [int(x) for x in self._vectorizer.ngram_range],
            "max_features": int(self._vectorizer.max_features),
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str | None = None) -> "BM25SparseEncoder":
        target = path or _BM25_VOCAB_PATH
        if not os.path.exists(target):
            raise FileNotFoundError(f"BM25 vocab not found: {target}")
        with open(target, encoding="utf-8") as f:
            data = json.load(f)
        encoder = cls()
        encoder._vectorizer = TfidfVectorizer(
            use_idf=True, norm=None, analyzer="char_wb",
            ngram_range=tuple(data["ngram_range"]),
            max_features=int(data["max_features"]),
            vocabulary=data["vocabulary"],
        )
        encoder._vectorizer.idf_ = np.array(data["idf"], dtype=np.float64)
        encoder._is_fitted = True
        return encoder
