import hashlib

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Conflict, NotFound
from app.ingestion.jobs import enqueue
from app.ingestion.ssrf import fetch_url
from app.ingestion.storage import get_storage
from app.ingestion.validation import UploadRejected, validate_upload
from app.models import Chunk, Document, User
from app.schemas.api import DocumentOut, UrlIngestIn
from app.services.audit import audit

router = APIRouter(prefix="/documents", tags=["documents"])


def _store(db: Session, user: User, filename: str, title: str, data: bytes, source: str, uri: str) -> Document:
    kind = validate_upload(filename, data, get_settings().max_upload_mb * 1024 * 1024)
    sha = hashlib.sha256(data).hexdigest()
    dup = db.scalar(select(Document).where(Document.org_id == user.org_id, Document.sha256 == sha))
    if dup is not None:
        raise Conflict(f"Identical document already exists: {dup.title}")
    key = f"{user.org_id}/{sha}.{kind.ext}"
    get_storage().put(key, data)
    doc = Document(
        org_id=user.org_id,
        title=title,
        source_type=source,
        source_uri=uri,
        mime_type=kind.mime,
        sha256=sha,
        size_bytes=len(data),
        storage_path=key,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()
    enqueue(db, doc)
    audit(
        db,
        org_id=user.org_id,
        actor_id=user.id,
        action=f"document.{source}",
        target_type="document",
        target_id=doc.id,
        details={"title": title, "size": len(data), "mime": kind.mime},
    )
    db.commit()
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.org_id == user.org_id).order_by(Document.created_at.desc())))


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.org_id != user.org_id:
        raise NotFound("Document not found")
    return doc


@router.get("/{document_id}/chunks")
def document_chunks(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    doc = get_document(document_id, user, db)
    rows = db.scalars(select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.ordinal))
    return [
        {"id": c.id, "ordinal": c.ordinal, "page": c.page, "section": c.section, "text": c.text, "flags": c.flags}
        for c in rows
    ]


@router.post("/upload", response_model=DocumentOut, status_code=202)
async def upload(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
) -> Document:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)  # bounded read: never buffer more than limit + 1 bytes
    if len(data) > limit:
        raise UploadRejected(f"File exceeds the {get_settings().max_upload_mb} MB limit", status_code=413)
    name = (file.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1][:200]
    return _store(db, user, name, (title or name)[:300], data, "upload", name)


@router.post("/url", response_model=DocumentOut, status_code=202)
def ingest_url(
    body: UrlIngestIn, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)
) -> Document:
    s = get_settings()
    data, ctype, final = fetch_url(str(body.url), s.url_allowlist, max_bytes=s.max_upload_mb * 1024 * 1024)
    ext = {"application/pdf": "pdf", "text/markdown": "md"}.get(ctype, "txt")
    if ctype == "text/html":
        from app.ingestion.extractors import extract_html

        data = extract_html(data)[0].text.encode("utf-8")
    return _store(db, user, f"web.{ext}", body.title or final[:300], data, "url", final)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)
) -> None:
    doc = get_document(document_id, user, db)
    key = doc.storage_path
    db.delete(doc)
    audit(
        db,
        org_id=user.org_id,
        actor_id=user.id,
        action="document.delete",
        target_type="document",
        target_id=document_id,
    )
    db.commit()
    # Delete the stored object only after the row is gone and no other document shares the key.
    if key and db.scalar(select(Document.id).where(Document.storage_path == key).limit(1)) is None:
        get_storage().delete(key)
