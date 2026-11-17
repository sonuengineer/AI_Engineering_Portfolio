"""Run creation: builds a reproducible config snapshot and enqueues the run."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFound, ValidationFailed
from app.models import (
    Dataset,
    DatasetVersion,
    EvaluatorConfig,
    Experiment,
    ModelConfig,
    PromptVersion,
    Run,
    Target,
)

_SECRET_HINTS = ("password", "secret", "token", "api_key", "apikey", "authorization")


def git_sha() -> str | None:
    s = get_settings()
    if s.git_sha:
        return s.git_sha
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3,
            cwd=Path(__file__).resolve().parents[2],
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def validate_target_config(config: dict[str, Any]) -> None:
    """Targets may reference env var names (keys ending in _env) but never hold secrets."""
    for k, v in config.items():
        lk = k.lower()
        if lk.endswith("_env"):
            continue
        if any(h in lk for h in _SECRET_HINTS):
            raise ValidationFailed(
                f"target config key '{k}' looks like a secret; store an env var name in '{k}_env' instead"
            )
        if isinstance(v, str) and v.lower().startswith("bearer "):
            raise ValidationFailed("target config must not contain bearer tokens")


def target_snapshot(session: Session, target: Target) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "target": {"id": str(target.id), "name": target.name, "kind": target.kind, "config": dict(target.config)},
    }
    if target.kind == "llm":
        mc = session.get(ModelConfig, target.model_config_id) if target.model_config_id else None
        if mc is None:
            raise ValidationFailed(f"target '{target.name}' has no model config")
        snap["model_config"] = {
            "id": str(mc.id), "name": mc.name, "provider": mc.provider, "model": mc.model, "params": dict(mc.params),
            "price_in_per_1k": mc.price_in_per_1k, "price_out_per_1k": mc.price_out_per_1k,
        }
        if target.prompt_version_id:
            pv = session.get(PromptVersion, target.prompt_version_id)
            if pv is not None:
                snap["prompt_version"] = {
                    "id": str(pv.id), "version": pv.version, "system_prompt": pv.system_prompt,
                    "user_template": pv.user_template, "content_hash": pv.content_hash,
                }
    return snap


def create_runs(
    session: Session, *, org_id: uuid.UUID, user_id: uuid.UUID | None, project_id: uuid.UUID,
    dataset_version_id: uuid.UUID, target_ids: list[uuid.UUID], evaluator_ids: list[uuid.UUID],
    experiment_id: uuid.UUID | None = None, label: str = "", concurrency: int = 4, timeout_s: float = 30.0,
    max_retries: int = 2, seed: int = 0,
) -> list[Run]:
    dv = session.get(DatasetVersion, dataset_version_id)
    if dv is None or dv.org_id != org_id:
        raise NotFound("dataset version not found")
    ds = session.get(Dataset, dv.dataset_id)
    if ds is None or ds.project_id != project_id:
        raise ValidationFailed("dataset version does not belong to this project")
    if experiment_id is not None:
        exp = session.get(Experiment, experiment_id)
        if exp is None or exp.org_id != org_id or exp.project_id != project_id:
            raise NotFound("experiment not found")
    if not target_ids:
        raise ValidationFailed("at least one target is required")
    evaluators = session.scalars(
        select(EvaluatorConfig).where(EvaluatorConfig.id.in_(evaluator_ids), EvaluatorConfig.org_id == org_id,
                                      EvaluatorConfig.project_id == project_id)
    ).all() if evaluator_ids else []
    if len(evaluators) != len(set(evaluator_ids)):
        raise NotFound("one or more evaluators not found in this project")
    ev_snap = [
        {"id": str(e.id), "name": e.name, "type": e.type, "kind": e.kind, "params": dict(e.params),
         "threshold": e.threshold, "gating": e.gating and e.kind == "deterministic"}
        for e in sorted(evaluators, key=lambda e: e.name)
    ]
    sha = git_sha()
    runs: list[Run] = []
    for tid in target_ids:
        target = session.get(Target, tid)
        if target is None or target.org_id != org_id or target.project_id != project_id:
            raise NotFound("target not found in this project")
        snap = target_snapshot(session, target)
        snap["evaluators"] = ev_snap
        snap["dataset"] = {"dataset_id": str(ds.id), "name": ds.name, "version_id": str(dv.id),
                           "version": dv.version, "content_hash": dv.content_hash, "case_count": dv.case_count}
        snap["params"] = {"concurrency": max(1, min(32, concurrency)), "timeout_s": max(1.0, min(300.0, timeout_s)),
                          "max_retries": max(0, min(5, max_retries)), "seed": seed, "backoff_base_s": 0.25}
        snap["config_hash"] = hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()
        run = Run(
            org_id=org_id, project_id=project_id, experiment_id=experiment_id, dataset_version_id=dv.id,
            target_id=target.id, label=label or f"{target.name} on {ds.name} v{dv.version}", status="queued",
            config_snapshot=snap, dataset_hash=dv.content_hash, seed=seed, git_sha=sha, created_by=user_id,
            progress_total=dv.case_count,
        )
        session.add(run)
        runs.append(run)
    session.flush()
    return runs
