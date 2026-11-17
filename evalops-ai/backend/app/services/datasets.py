"""Dataset parsing (JSONL), validation, content hashing and immutable versioning."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import Dataset, DatasetVersion, TestCase

ALLOWED_CASE_KEYS = {"id", "input", "expected_output", "reference_contexts", "expected_citations", "tags", "metadata"}


def _norm_case(raw: Any, line_no: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationFailed(f"line {line_no}: each line must be a JSON object")
    unknown = set(raw) - ALLOWED_CASE_KEYS
    if unknown:
        raise ValidationFailed(f"line {line_no}: unknown keys {sorted(unknown)}")
    if not isinstance(raw.get("input"), str) or not raw["input"].strip():
        raise ValidationFailed(f"line {line_no}: 'input' must be a non-empty string")
    if len(raw["input"]) > 20000:
        raise ValidationFailed(f"line {line_no}: 'input' exceeds 20000 characters")
    exp = raw.get("expected_output")
    if exp is not None and not isinstance(exp, str):
        raise ValidationFailed(f"line {line_no}: 'expected_output' must be a string or null")
    for key in ("reference_contexts", "expected_citations", "tags"):
        val = raw.get(key, [])
        if not isinstance(val, list) or not all(isinstance(v, str) for v in val):
            raise ValidationFailed(f"line {line_no}: '{key}' must be a list of strings")
    meta = raw.get("metadata", {})
    if not isinstance(meta, dict):
        raise ValidationFailed(f"line {line_no}: 'metadata' must be an object")
    return {
        "id": str(raw.get("id") or f"case-{line_no:04d}"),
        "input": raw["input"],
        "expected_output": exp,
        "reference_contexts": raw.get("reference_contexts", []),
        "expected_citations": raw.get("expected_citations", []),
        "tags": raw.get("tags", []),
        "metadata": meta,
    }


def parse_jsonl(content: bytes, *, max_cases: int) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationFailed("file must be UTF-8 encoded JSONL") from exc
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationFailed(f"line {i}: invalid JSON ({exc.msg})") from exc
        case = _norm_case(raw, i)
        if case["id"] in seen:
            raise ValidationFailed(f"line {i}: duplicate case id '{case['id']}'")
        seen.add(case["id"])
        cases.append(case)
        if len(cases) > max_cases:
            raise ValidationFailed(f"too many cases (max {max_cases})")
    if not cases:
        raise ValidationFailed("dataset file contains no cases")
    return cases


def content_hash(cases: list[dict[str, Any]]) -> str:
    canonical = json.dumps(cases, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_version(
    session: Session, dataset: Dataset, cases: list[dict[str, Any]], *, notes: str = "",
    source_filename: str | None = None,
) -> DatasetVersion:
    """Create a new immutable version. Re-uploading identical content returns the existing version."""
    h = content_hash(cases)
    existing = session.scalar(
        select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id, DatasetVersion.content_hash == h)
    )
    if existing:
        return existing
    next_version = (session.scalar(
        select(func.max(DatasetVersion.version)).where(DatasetVersion.dataset_id == dataset.id)
    ) or 0) + 1
    dv = DatasetVersion(
        id=uuid.uuid4(), org_id=dataset.org_id, dataset_id=dataset.id, version=next_version, content_hash=h,
        case_count=len(cases), notes=notes, source_filename=source_filename,
    )
    session.add(dv)
    session.flush()
    for pos, c in enumerate(cases):
        session.add(TestCase(
            org_id=dataset.org_id, dataset_version_id=dv.id, external_id=c["id"], position=pos, input=c["input"],
            expected_output=c["expected_output"], reference_contexts=c["reference_contexts"],
            expected_citations=c["expected_citations"], tags=c["tags"], meta=c["metadata"],
        ))
    session.flush()
    return dv
