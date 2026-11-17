"""Compare two stored runs (DB-level wrapper around comparison.py)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import RunResult
from app.services.comparison import compare_summaries, diff_cases
from app.services.run_queries import get_run, run_dict


def compare_runs(
    session: Session, org_id: uuid.UUID, baseline_id: uuid.UUID, candidate_id: uuid.UUID, *,
    tolerance: float = 0.02, metric_tolerances: dict[str, float] | None = None,
    latency_tolerance_pct: float = 0.25,
) -> dict[str, Any]:
    a = get_run(session, org_id, baseline_id)
    b = get_run(session, org_id, candidate_id)
    if a.status != "completed" or b.status != "completed":
        raise ValidationFailed("both runs must be completed to compare")
    result = compare_summaries(a.summary, b.summary, tolerance=tolerance, metric_tolerances=metric_tolerances,
                               latency_tolerance_pct=latency_tolerance_pct)
    ac = {r.external_id: r.passed for r in session.scalars(select(RunResult).where(RunResult.run_id == a.id))}
    bc = {r.external_id: r.passed for r in session.scalars(select(RunResult).where(RunResult.run_id == b.id))}
    result["cases"] = diff_cases(ac, bc)
    result["same_dataset"] = a.dataset_hash == b.dataset_hash
    result["baseline"] = {k: v for k, v in run_dict(session, a).items() if k != "config_snapshot"}
    result["candidate"] = {k: v for k, v in run_dict(session, b).items() if k != "config_snapshot"}
    return result
