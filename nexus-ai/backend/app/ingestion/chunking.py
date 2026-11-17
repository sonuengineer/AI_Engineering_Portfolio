"""Sentence-aware chunking with overlap, preserving page/section metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.extractors import Segment
from app.llm.base import estimate_tokens

_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


@dataclass
class ChunkDraft:
    text: str
    page: int | None
    section: str | None
    ordinal: int
    token_estimate: int


def chunk_segments(segments: list[Segment], max_chars: int = 900, overlap_chars: int = 150) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    for seg in segments:
        text = re.sub(r"[ \t]+", " ", seg.text).strip()
        if not text:
            continue
        pieces = [p.strip() for p in _SPLIT.split(text) if p and p.strip()]
        buf = ""
        for piece in pieces:
            while len(piece) > max_chars:  # hard-split very long sentences/rows
                head, piece = piece[:max_chars], piece[max_chars:]
                if buf:
                    chunks.append(_mk(buf, seg, len(chunks)))
                    buf = ""
                chunks.append(_mk(head, seg, len(chunks)))
            if len(buf) + len(piece) + 1 > max_chars and buf:
                chunks.append(_mk(buf, seg, len(chunks)))
                tail = buf[-overlap_chars:]
                cut = tail.find(" ")
                buf = (tail[cut + 1 :] if cut >= 0 else tail) + " " + piece
            else:
                buf = f"{buf} {piece}".strip()
        if buf:
            chunks.append(_mk(buf, seg, len(chunks)))
    return chunks


def _mk(text: str, seg: Segment, ordinal: int) -> ChunkDraft:
    prefix = f"[{seg.section}] " if seg.section else ""
    full = prefix + text.strip()
    return ChunkDraft(full, seg.page, seg.section, ordinal, estimate_tokens(full))
