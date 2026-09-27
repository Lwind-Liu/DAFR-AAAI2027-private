from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, Sequence

import numpy as np


class TextEncoder(Protocol):
    dimension: int

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        ...


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms > 0.0, norms, 1.0)
    return matrix / norms


@dataclass
class HashingTextEncoder:
    dimension: int = 256
    ngram_range: tuple[int, int] = (1, 2)
    cache_size: int = 20000
    _cache: dict[str, np.ndarray] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._vectorizer = None
        try:
            from sklearn.feature_extraction.text import HashingVectorizer

            self._vectorizer = HashingVectorizer(
                n_features=self.dimension,
                alternate_sign=False,
                norm="l2",
                ngram_range=self.ngram_range,
                lowercase=True,
            )
        except Exception:
            self._vectorizer = None

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        materialized = [str(text) for text in texts]
        if not materialized:
            return np.zeros((0, self.dimension), dtype=float)
        if self.cache_size <= 0:
            return self._encode_uncached(materialized)

        missing = [text for text in dict.fromkeys(materialized) if text not in self._cache]
        if missing:
            vectors = self._encode_uncached(missing)
            for text, vector in zip(missing, vectors):
                if len(self._cache) >= self.cache_size:
                    self._cache.clear()
                self._cache[text] = np.asarray(vector, dtype=float)
        return np.vstack([self._cache[text] for text in materialized]).astype(float, copy=True)

    def _encode_uncached(self, materialized: Sequence[str]) -> np.ndarray:
        if self._vectorizer is not None:
            return self._vectorizer.transform(materialized).toarray().astype(float)
        return l2_normalize(np.vstack([self._fallback_vector(text) for text in materialized]))

    def _fallback_vector(self, text: str) -> np.ndarray:
        tokens = text.lower().split()
        grams: list[str] = []
        lo, hi = self.ngram_range
        for n in range(lo, hi + 1):
            for idx in range(0, max(0, len(tokens) - n + 1)):
                grams.append(" ".join(tokens[idx : idx + n]))
        if not grams:
            grams = [text.lower()]
        vec = np.zeros(self.dimension, dtype=float)
        for gram in grams:
            digest = hashlib.sha1(gram.encode("utf-8")).digest()
            pos = int.from_bytes(digest[:4], "big") % self.dimension
            vec[pos] += 1.0
        return vec


class SentenceTransformerTextEncoder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise RuntimeError("sentence-transformers is not installed") from exc
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=float)
        vectors = self.model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vectors, dtype=float)
