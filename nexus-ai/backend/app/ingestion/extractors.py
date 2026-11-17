"""Text extraction per file type. Returns page-level segments so citations can reference pages."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class Segment:
    text: str
    page: int | None = None
    section: str | None = None


def extract_pdf(data: bytes) -> list[Segment]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return [Segment(text=(p.extract_text() or ""), page=i + 1) for i, p in enumerate(reader.pages)]


def extract_docx(data: bytes) -> list[Segment]:
    import docx

    d = docx.Document(io.BytesIO(data))
    segs: list[Segment] = []
    section: str | None = None
    buf: list[str] = []
    for para in d.paragraphs:
        style = (para.style.name if para.style is not None else "") or ""
        if style.lower().startswith("heading") and para.text.strip():
            if buf:
                segs.append(Segment("\n".join(buf), section=section))
                buf = []
            section = para.text.strip()
        elif para.text.strip():
            buf.append(para.text.strip())
    for table in d.tables:
        for row in table.rows:
            buf.append(" | ".join(c.text.strip() for c in row.cells))
    if buf:
        segs.append(Segment("\n".join(buf), section=section))
    return segs


def extract_xlsx(data: bytes) -> list[Segment]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    segs: list[Segment] = []
    for idx, ws in enumerate(wb.worksheets, start=1):
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        header = [str(h) if h is not None else f"col{i}" for i, h in enumerate(rows[0])]
        lines = []
        for r in rows[1:]:
            if all(v is None for v in r):
                continue
            lines.append("; ".join(f"{h}: {v}" for h, v in zip(header, r, strict=False) if v is not None))
        segs.append(Segment("\n".join(lines), page=idx, section=f"Sheet {ws.title}"))
    wb.close()
    return segs


def extract_csv(data: bytes) -> list[Segment]:
    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    rows = list(reader)
    if not rows:
        return []
    header = rows[0]
    lines = ["; ".join(f"{h}: {v}" for h, v in zip(header, r, strict=False) if v) for r in rows[1:]]
    return [Segment("\n".join(lines), section="CSV rows")]


_MD_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def extract_text(data: bytes, markdown: bool = False) -> list[Segment]:
    text = data.decode("utf-8")
    if not markdown:
        return [Segment(text)]
    segs: list[Segment] = []
    section: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = _MD_HEADING.match(line)
        if m:
            if "".join(buf).strip():
                segs.append(Segment("\n".join(buf).strip(), section=section))
            buf = []
            section = m.group(1).strip()
        else:
            buf.append(line)
    if "".join(buf).strip():
        segs.append(Segment("\n".join(buf).strip(), section=section))
    return segs


class _TextHTML(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in {"p", "div", "li", "h1", "h2", "h3", "br", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def extract_html(data: bytes) -> list[Segment]:
    p = _TextHTML()
    p.feed(data.decode("utf-8", errors="replace"))
    text = re.sub(r"\n\s*\n+", "\n\n", "".join(p.parts)).strip()
    return [Segment(text)]


def extract(ext: str, data: bytes) -> list[Segment]:
    match ext:
        case "pdf":
            return extract_pdf(data)
        case "docx":
            return extract_docx(data)
        case "xlsx":
            return extract_xlsx(data)
        case "csv":
            return extract_csv(data)
        case "md":
            return extract_text(data, markdown=True)
        case "html":
            return extract_html(data)
        case _:
            return extract_text(data)
