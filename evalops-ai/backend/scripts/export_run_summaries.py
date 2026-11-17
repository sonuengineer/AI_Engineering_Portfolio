"""Export stored run summaries to a JSON artifact (no recomputation, no editing).

Usage: python -m scripts.export_run_summaries --label-prefix "NEXUS live" --label-prefix "DATAWISE live" \
         --out ../docs/benchmarks/live-benchmarks.json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.db import session_scope
from app.models import DatasetVersion, Run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label-prefix", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs_out = []
    with session_scope() as s:
        for prefix in a.label_prefix:
            for run in s.scalars(select(Run).where(Run.label.like(f"{prefix}%"), Run.status == "completed")):
                dv = s.get(DatasetVersion, run.dataset_version_id)
                summ = run.summary or {}
                runs_out.append({
                    "run_id": str(run.id), "label": run.label,
                    "dataset_version": dv.version if dv else None,
                    "dataset_hash": dv.content_hash[:12] if dv else None,
                    "case_count": summ.get("case_count"),
                    "overall_pass_rate": summ.get("overall_pass_rate"),
                    "error_rate": summ.get("error_rate"),
                    "latency_ms": summ.get("latency_ms"),
                    "metrics_pass_rate": {k: v.get("pass_rate") for k, v in (summ.get("metrics") or {}).items()},
                    "metrics_scored": {k: v.get("scored") for k, v in (summ.get("metrics") or {}).items()},
                })
    out = {"exported_at": datetime.now(UTC).isoformat(timespec="seconds"), "runs": runs_out,
           "note": "Exported verbatim from stored EvalOps runs against the live NEXUS and DATAWISE APIs "
                   "(both using their deterministic local adapters). overall_pass_rate requires every gating "
                   "metric of a case to pass."}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2)[:1500])


if __name__ == "__main__":
    main()
