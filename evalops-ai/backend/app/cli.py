"""EvalOps CLI.

  python -m app.cli gate    --run-id X [--baseline Y] --thresholds ../evalops.gate.yaml
  python -m app.cli run     --project support-qa --dataset support_faq --target "Scripted assistant v1"
  python -m app.cli ci-gate --thresholds ../evalops.gate.yaml   (run candidate + gate vs baseline)

Exit codes: 0 = gate passed, 1 = gate failed (threshold or regression), 2 = usage/config/runtime error.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.logging import configure_logging
from app.engine.runner import execute_run
from app.models import Dataset, DatasetVersion, EvaluatorConfig, Org, Project, Run, Target
from app.services.compare_runs import compare_runs
from app.services.gate import check_thresholds, regression_failures
from app.services.runs import create_runs

EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2


class CliError(Exception):
    pass


def load_config(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise CliError(f"thresholds file not found: {path}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise CliError("thresholds file must be a YAML mapping")
    return data


def gate(run_id: uuid.UUID, baseline_id: uuid.UUID | None, cfg: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise CliError(f"run {run_id} not found")
        if run.status != "completed":
            return EXIT_FAIL, {"run_id": str(run_id), "baseline_id": str(baseline_id) if baseline_id else None,
                               "passed": False, "failures": [f"run status is {run.status}, not completed"],
                               "overall_pass_rate": None, "error_rate": None}
        failures = check_thresholds(run.summary, cfg.get("thresholds") or {})
        comparison = None
        if baseline_id is not None:
            base = s.get(Run, baseline_id)
            if base is None or base.org_id != run.org_id:
                raise CliError(f"baseline run {baseline_id} not found")
            reg = cfg.get("regression") or {}
            comparison = compare_runs(
                s, run.org_id, baseline_id, run_id, tolerance=float(reg.get("tolerance", 0.02)),
                metric_tolerances=reg.get("metric_tolerances"),
                latency_tolerance_pct=float(reg.get("latency_tolerance_pct", 0.25)),
            )
            failures += regression_failures(comparison)
            if comparison["cases"]["newly_failing"]:
                failures.append(f"newly failing cases: {', '.join(comparison['cases']['newly_failing'][:20])}")
        report = {
            "run_id": str(run_id), "baseline_id": str(baseline_id) if baseline_id else None,
            "passed": not failures, "failures": failures,
            "overall_pass_rate": run.summary.get("overall_pass_rate"),
            "error_rate": run.summary.get("error_rate"),
        }
        return (EXIT_PASS if not failures else EXIT_FAIL), report


def _resolve(s: Any, org_slug: str, project_slug: str, dataset: str, target: str) -> tuple[Org, Project, DatasetVersion, Target]:
    org = s.scalar(select(Org).where(Org.slug == org_slug))
    if org is None:
        raise CliError(f"org '{org_slug}' not found (did you run scripts.seed?)")
    proj = s.scalar(select(Project).where(Project.org_id == org.id, Project.slug == project_slug))
    if proj is None:
        raise CliError(f"project '{project_slug}' not found")
    ds = s.scalar(select(Dataset).where(Dataset.project_id == proj.id, Dataset.name == dataset))
    if ds is None:
        raise CliError(f"dataset '{dataset}' not found")
    dv = s.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == ds.id).order_by(DatasetVersion.version.desc()))
    if dv is None:
        raise CliError(f"dataset '{dataset}' has no versions")
    tgt = s.scalar(select(Target).where(Target.project_id == proj.id, Target.name == target))
    if tgt is None:
        raise CliError(f"target '{target}' not found")
    return org, proj, dv, tgt


def run_inline(org_slug: str, project_slug: str, dataset: str, target: str, label: str, seed: int = 0) -> uuid.UUID:
    with session_scope() as s:
        org, proj, dv, tgt = _resolve(s, org_slug, project_slug, dataset, target)
        ev_ids = list(s.scalars(select(EvaluatorConfig.id).where(EvaluatorConfig.project_id == proj.id)))
        runs = create_runs(s, org_id=org.id, user_id=None, project_id=proj.id, dataset_version_id=dv.id,
                           target_ids=[tgt.id], evaluator_ids=ev_ids, label=label, seed=seed)
        runs[0].status = "running"  # executed inline by this process, never picked up by a worker
        run_id = runs[0].id
    status = execute_run(run_id)
    if status != "completed":
        raise CliError(f"run {run_id} finished with status {status}")
    return run_id


def find_baseline(org_slug: str, project_slug: str, label: str) -> uuid.UUID:
    with session_scope() as s:
        org = s.scalar(select(Org).where(Org.slug == org_slug))
        proj = s.scalar(select(Project).where(Project.org_id == org.id, Project.slug == project_slug)) if org else None
        if proj is None:
            raise CliError(f"project '{project_slug}' not found")
        rid = s.scalar(select(Run.id).where(Run.project_id == proj.id, Run.label == label, Run.status == "completed")
                       .order_by(Run.created_at.desc()))
        if rid is None:
            raise CliError(f"no completed baseline run labeled '{label}'")
        return rid


def _print(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2))
        return
    print(f"EvalOps gate: {'PASSED' if report['passed'] else 'FAILED'}")
    print(f"  run={report['run_id']} baseline={report.get('baseline_id')}")
    print(f"  overall_pass_rate={report.get('overall_pass_rate')} error_rate={report.get('error_rate')}")
    for f in report["failures"]:
        print(f"  - {f}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="check a stored run against thresholds and an optional baseline")
    g.add_argument("--run-id", required=True)
    g.add_argument("--baseline")
    g.add_argument("--thresholds", required=True)
    g.add_argument("--json", action="store_true")
    r = sub.add_parser("run", help="execute a run inline and print its id")
    r.add_argument("--org", default="acme-eval")
    r.add_argument("--project", required=True)
    r.add_argument("--dataset", required=True)
    r.add_argument("--target", required=True)
    r.add_argument("--label", default="cli run")
    r.add_argument("--seed", type=int, default=0)
    c = sub.add_parser("ci-gate", help="run the candidate from the config's ci section, then gate vs baseline")
    c.add_argument("--thresholds", required=True)
    c.add_argument("--target", help="override ci.candidate_target")
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    configure_logging(get_settings().log_level, stream=sys.stderr)  # keep stdout clean for --json
    try:
        if args.cmd == "gate":
            code, report = gate(uuid.UUID(args.run_id), uuid.UUID(args.baseline) if args.baseline else None,
                                load_config(args.thresholds))
            _print(report, args.json)
            return code
        if args.cmd == "run":
            print(run_inline(args.org, args.project, args.dataset, args.target, args.label, args.seed))
            return EXIT_PASS
        cfg = load_config(args.thresholds)
        ci = cfg.get("ci") or {}
        for key in ("project", "dataset", "candidate_target", "baseline_label"):
            if key not in ci:
                raise CliError(f"ci.{key} missing in {args.thresholds}")
        org = ci.get("org", "acme-eval")
        baseline = find_baseline(org, ci["project"], ci["baseline_label"])
        target = args.target or ci["candidate_target"]
        run_id = run_inline(org, ci["project"], ci["dataset"], target, f"ci-gate candidate: {target}")
        code, report = gate(run_id, baseline, cfg)
        _print(report, args.json)
        return code
    except (CliError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
