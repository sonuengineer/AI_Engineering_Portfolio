"""Hybrid retrieval: pgvector cosine + Postgres full-text, fused with Reciprocal Rank Fusion,
then reranked. All queries are tenant-scoped by org_id."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.llm import get_embedder
from app.llm.embeddings import tokenize
from app.models import Chunk, Document

RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    page: int | None
    section: str | None
    text: str
    flags: dict[str, Any]
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    signals: dict[str, float] = field(default_factory=dict)


def _ts_query(text: str) -> str | None:
    terms = sorted({t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2})
    if not terms:
        return None
    return " | ".join(terms[:30])  # OR semantics for recall; ranking handles precision


def hybrid_search(
    db: Session,
    org_id: str,
    query: str,
    *,
    k: int = 6,
    candidates: int = 25,
    document_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    qvec = get_embedder().embed([query])[0]
    base = (
        select(Chunk, Document.title)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.org_id == org_id, Document.org_id == org_id, Document.status == "ready")
    )
    if document_ids:
        base = base.where(Chunk.document_id.in_(document_ids))

    vec_rows = db.execute(base.order_by(Chunk.embedding.cosine_distance(qvec)).limit(candidates)).all()

    kw_rows: list[Any] = []
    tsq = _ts_query(query)
    if tsq:
        q = func.to_tsquery("english", tsq)
        kw_rows = list(
            db.execute(
                base.where(Chunk.tsv.op("@@")(q)).order_by(func.ts_rank_cd(Chunk.tsv, q).desc()).limit(candidates)
            ).all()
        )

    merged: dict[str, RetrievedChunk] = {}
    for rank, (chunk, title) in enumerate(vec_rows, start=1):
        rc = merged.setdefault(chunk.id, _mk(chunk, title))
        rc.vector_rank = rank
        rc.rrf_score += 1.0 / (RRF_K + rank)
    for rank, (chunk, title) in enumerate(kw_rows, start=1):
        rc = merged.setdefault(chunk.id, _mk(chunk, title))
        rc.keyword_rank = rank
        rc.rrf_score += 1.0 / (RRF_K + rank)

    return rerank(query, list(merged.values()))[:k]


def _mk(chunk: Chunk, title: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_title=title,
        page=chunk.page,
        section=chunk.section,
        text=chunk.text,
        flags=chunk.flags or {},
    )


def rerank(query: str, items: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Lightweight lexical reranker (local, deterministic).

    score = 0.5 * query-term coverage + 0.2 * bigram match + 0.3 * normalized RRF.
    A cross-encoder or LLM reranker is the documented upgrade path.
    """
    q_terms = tokenize(query)
    q_set = set(q_terms)
    q_bigrams = {f"{a} {b}" for a, b in zip(q_terms, q_terms[1:], strict=False)}
    max_rrf = max((i.rrf_score for i in items), default=1.0) or 1.0
    for it in items:
        toks = tokenize(it.text + " " + it.document_title)
        t_set = set(toks)
        coverage = len(q_set & t_set) / len(q_set) if q_set else 0.0
        bigrams = {f"{a} {b}" for a, b in zip(toks, toks[1:], strict=False)}
        bigram = len(q_bigrams & bigrams) / len(q_bigrams) if q_bigrams else 0.0
        rrf_norm = it.rrf_score / max_rrf
        it.signals = {"coverage": round(coverage, 3), "bigram": round(bigram, 3), "rrf": round(rrf_norm, 3)}
        it.rerank_score = round(0.5 * coverage + 0.2 * bigram + 0.3 * rrf_norm, 4)
    return sorted(items, key=lambda i: i.rerank_score, reverse=True)
