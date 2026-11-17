"""Embedding providers. Local = signed feature hashing (lexical, NOT semantic) for keyless demos."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from app.core.config import Settings
from app.models.documents import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "we",
        "you",
        "your",
        "do",
        "does",
        "did",
        "not",
    ]
)


def normalize_token(tok: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(tok) > len(suffix) + 3 and tok.endswith(suffix):
            return tok[: -len(suffix)]
    return tok


def tokenize(text: str) -> list[str]:
    return [normalize_token(t) for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class HashingEmbedder:
    """Deterministic hashing-trick embedder over unigrams + bigrams.

    Captures lexical overlap only. It is a stand-in so pgvector retrieval works without an API
    key; swap EMBEDDING_PROVIDER to gemini/openai for semantic embeddings.
    """

    name = "local-hashing"

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        toks = tokenize(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:], strict=False)]
        for f in feats:
            h = hashlib.blake2b(f.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign * (1.0 if "_" not in f else 0.5)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            vec[0] = 1.0  # avoid zero vector (cosine undefined)
            return vec
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


class GeminiEmbedder:
    name = "gemini"

    def __init__(self, api_key: str, model: str, dim: int = EMBEDDING_DIM):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types

        contents: list[Any] = list(texts)
        resp = self._client.models.embed_content(
            model=self._model,
            contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=self.dim),
        )
        out = [list(e.values or []) for e in (resp.embeddings or [])]
        # Truncated-dimension Gemini embeddings are not unit length; normalize for cosine.
        return [_l2(v) for v in out]


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, api_key: str, model: str, dim: int = EMBEDDING_DIM):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=list(texts), dimensions=self.dim)
        return [list(d.embedding) for d in resp.data]


def _l2(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def build_embedder(s: Settings) -> HashingEmbedder | GeminiEmbedder | OpenAIEmbedder:
    if s.embedding_provider == "gemini":
        if not s.gemini_api_key:
            raise ValueError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY")
        return GeminiEmbedder(s.gemini_api_key, s.gemini_embedding_model)
    if s.embedding_provider == "openai":
        if not s.openai_api_key:
            raise ValueError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY")
        return OpenAIEmbedder(s.openai_api_key, s.openai_embedding_model)
    return HashingEmbedder()
