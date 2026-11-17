"""Gate CLI exit codes: 0 pass, 1 fail (threshold/regression), 2 usage/config error."""

from __future__ import annotations

import uuid

import yaml

from app.cli import main
from app.core.db import session_scope
from app.models import Run
from app.services.runs import create_runs
from app.worker import process_available

from helpers import build_project


def _cfg(tmp_path, **extra):
    cfg = {"thresholds": {"min_overall_pass_rate": 0.9, "max_error_rate": 0.0, "min_pass_rate": {"citations": 0.9}},
           "regression": {"tolerance": 0.02, "latency_tolerance_pct": 100.0}}
    cfg.update(extra)
    p = tmp_path / "gate.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return str(p)


def _runs(org):
    proj = build_project(org["org_id"], slug="support")
    ids = {}
    for name in ("good", "bad"):
        with session_scope() as s:
            r = create_runs(s, org_id=org["org_id"], user_id=None, project_id=proj["project_id"],
                            dataset_version_id=proj["dv_id"], target_ids=[proj["targets"][name]],
                            evaluator_ids=proj["evaluators"], label=f"{name} run")
            ids[name] = str(r[0].id)
    process_available("w")
    return proj, ids


def test_gate_pass_and_fail(org_a, tmp_path, capsys):
    _, ids = _runs(org_a)
    cfg = _cfg(tmp_path)
    assert main(["gate", "--run-id", ids["good"], "--thresholds", cfg]) == 0
    assert main(["gate", "--run-id", ids["good"], "--baseline", ids["good"], "--thresholds", cfg]) == 0
    assert main(["gate", "--run-id", ids["bad"], "--thresholds", cfg]) == 1
    capsys.readouterr()
    assert main(["gate", "--run-id", ids["bad"], "--baseline", ids["good"], "--thresholds", cfg, "--json"]) == 1
    out = capsys.readouterr().out
    assert "regression in citations" in out and "newly failing cases: c1, c3" in out


def test_regression_only_gate(org_a, tmp_path):
    _, ids = _runs(org_a)
    lenient = _cfg(tmp_path, thresholds={})
    assert main(["gate", "--run-id", ids["bad"], "--thresholds", lenient]) == 0  # no thresholds -> pass
    assert main(["gate", "--run-id", ids["bad"], "--baseline", ids["good"], "--thresholds", lenient]) == 1


def test_gate_errors_exit_2(org_a, tmp_path):
    _, ids = _runs(org_a)
    assert main(["gate", "--run-id", str(uuid.uuid4()), "--thresholds", _cfg(tmp_path)]) == 2
    assert main(["gate", "--run-id", ids["good"], "--thresholds", str(tmp_path / "missing.yaml")]) == 2
    assert main(["gate", "--run-id", "not-a-uuid", "--thresholds", _cfg(tmp_path)]) == 2


def test_incomplete_run_fails_gate(org_a, tmp_path):
    proj = build_project(org_a["org_id"])
    with session_scope() as s:
        r = create_runs(s, org_id=org_a["org_id"], user_id=None, project_id=proj["project_id"],
                        dataset_version_id=proj["dv_id"], target_ids=[proj["targets"]["good"]], evaluator_ids=[])
        rid = str(r[0].id)
    assert main(["gate", "--run-id", rid, "--thresholds", _cfg(tmp_path)]) == 1


def test_ci_gate_runs_candidate_and_compares(org_a, tmp_path):
    _runs(org_a)
    ci = {"org": "alpha", "project": "support", "dataset": "qa", "candidate_target": "good",
          "baseline_label": "good run"}
    cfg = _cfg(tmp_path, ci=ci)
    assert main(["ci-gate", "--thresholds", cfg]) == 0
    assert main(["ci-gate", "--thresholds", cfg, "--target", "bad"]) == 1
    with session_scope() as s:
        assert s.query(Run).filter(Run.label.like("ci-gate candidate%")).count() == 2
    bad_ci = _cfg(tmp_path, ci={**ci, "baseline_label": "nope"})
    assert main(["ci-gate", "--thresholds", bad_ci]) == 2
