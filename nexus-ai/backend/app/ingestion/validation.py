"""Upload validation: extension allowlist, size limit and magic-byte content checks.

The client-supplied Content-Type is never trusted; we sniff the bytes.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from app.core.errors import AppError


class UploadRejected(AppError):
    status_code = 415
    code = "upload_rejected"


@dataclass(frozen=True)
class FileKind:
    ext: str
    mime: str


KINDS = {
    "pdf": FileKind("pdf", "application/pdf"),
    "docx": FileKind("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "xlsx": FileKind("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "csv": FileKind("csv", "text/csv"),
    "txt": FileKind("txt", "text/plain"),
    "md": FileKind("md", "text/markdown"),
}


def _zip_names(data: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            # Zip-bomb guard: reject archives that inflate to > 50x their size or > 200 MB.
            total = sum(i.file_size for i in zf.infolist())
            if total > 200 * 1024 * 1024 or total > 50 * max(len(data), 1):
                raise UploadRejected("Archive expands too much (possible zip bomb)")
            return names
    except zipfile.BadZipFile as exc:
        raise UploadRejected("File is not a valid Office Open XML package") from exc


def validate_upload(filename: str, data: bytes, max_bytes: int) -> FileKind:
    if not data:
        raise UploadRejected("File is empty")
    if len(data) > max_bytes:
        raise UploadRejected(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit", status_code=413)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    kind = KINDS.get(ext)
    if kind is None:
        raise UploadRejected(f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(KINDS))}")
    if ext == "pdf":
        if not data.startswith(b"%PDF-"):
            raise UploadRejected("Content is not a PDF")
    elif ext in ("docx", "xlsx"):
        if not data.startswith(b"PK\x03\x04"):
            raise UploadRejected("Content is not an Office document")
        names = _zip_names(data)
        marker = "word/document.xml" if ext == "docx" else "xl/workbook.xml"
        if marker not in names:
            raise UploadRejected(f"Archive does not contain {marker}")
        if any(n.endswith("vbaProject.bin") for n in names):
            raise UploadRejected("Macro-enabled documents are not accepted")
    else:
        if b"\x00" in data[:8192]:
            raise UploadRejected("Text file contains binary content")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadRejected("Text files must be UTF-8 encoded") from exc
    return kind
