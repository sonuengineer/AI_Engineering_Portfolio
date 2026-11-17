"""Document processing: extract -> chunk -> scan for injection -> embed -> index."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ingestion.chunking import chunk_segments
from app.ingestion.extractors import extract
from app.ingestion.injection import scan
from app.ingestion.storage import ObjectStorage
from app.llm import get_embedder
from app.models import Chunk, Document

EXT_BY_MIME = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/csv": "csv",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/html": "html",
}


class EmptyDocument(ValueError):
    pass


def index_document(db: Session, doc: Document, storage: ObjectStorage, *, batch: int = 64) -> int:
    if not doc.storage_path:
        raise ValueError("Document has no stored content")
    data = storage.get(doc.storage_path)
    ext = EXT_BY_MIME.get(doc.mime_type, "txt")
    segments = extract(ext, data)
    if ext == "pdf":
        doc.page_count = len(segments)
    drafts = chunk_segments(segments)
    if not drafts:
        raise EmptyDocument("No extractable text found (scanned PDFs need OCR, not supported yet)")
    embedder = get_embedder()
    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    flagged = 0
    for i in range(0, len(drafts), batch):
        part = drafts[i : i + batch]
        vectors = embedder.embed([d.text for d in part])
        for d, vec in zip(part, vectors, strict=True):
            hits = scan(d.text)
            flagged += bool(hits)
            db.add(
                Chunk(
                    org_id=doc.org_id,
                    document_id=doc.id,
                    ordinal=d.ordinal,
                    page=d.page,
                    section=d.section,
                    text=d.text,
                    token_estimate=d.token_estimate,
                    embedding=vec,
                    flags={"suspicious_instructions": hits} if hits else {},
                )
            )
    doc.chunk_count = len(drafts)
    doc.meta = {**(doc.meta or {}), "flagged_chunks": flagged, "embedder": embedder.name}
    return len(drafts)
