# ADR-003: Hybrid retrieval inside PostgreSQL (pgvector + tsvector + RRF)

Status: accepted (2026-11-16)

## Decision
Store chunks in Postgres with a `vector(384)` HNSW index and a generated `tsvector` GIN index.
Retrieve top-25 by cosine distance and top-25 by `ts_rank_cd`, fuse with Reciprocal Rank Fusion
(k=60), then apply a lightweight lexical reranker (term coverage, bigram match, normalized RRF).

## Why
- One datastore keeps tenant filtering (`org_id`) and transactions in a single place.
- Keyword search rescues exact identifiers (quote numbers, batch ids) that embeddings miss.
- RRF needs no score calibration between the two retrievers.

## Consequences
- Embedding dimension is fixed by migration (384). Switching models with other dimensions requires
  a migration and re-embedding.
- The local hashing embedder is lexical, not semantic; semantic quality requires a real provider.
- A cross-encoder reranker is the documented upgrade path.
