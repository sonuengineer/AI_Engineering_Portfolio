"""Projects, datasets, prompts, model configs, targets, evaluators, experiments."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, Member, get_project_or_404, request_id
from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.evaluators import REGISTRY
from app.models import (
    Dataset,
    DatasetVersion,
    EvaluatorConfig,
    Experiment,
    ModelConfig,
    Project,
    PromptTemplate,
    PromptVersion,
    Target,
    TestCase,
)
from app.schemas import (
    DatasetIn,
    DatasetOut,
    DatasetVersionOut,
    EvaluatorIn,
    EvaluatorOut,
    ExperimentIn,
    ExperimentOut,
    ModelConfigIn,
    ModelConfigOut,
    ProjectIn,
    ProjectOut,
    PromptTemplateIn,
    PromptTemplateOut,
    PromptVersionIn,
    PromptVersionOut,
    TargetIn,
    TargetOut,
    TestCaseOut,
)
from app.services import audit
from app.services.datasets import create_version, parse_jsonl
from app.services.runs import validate_target_config

router = APIRouter(prefix="/api/v1", tags=["resources"])


def _audit(db: DB, p: Any, request: Request, action: str, rtype: str, rid: Any, details: dict[str, Any] | None = None) -> None:
    audit.record(db, org_id=p.org_id, user_id=p.user_id, action=action, resource_type=rtype, resource_id=rid,
                 details=details, request_id=request_id(request))


# ----------------------------------------------------------------------------- projects


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(p: CurrentUser, db: DB) -> list[Project]:
    return list(db.scalars(select(Project).where(Project.org_id == p.org_id).order_by(Project.name)))


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, p: Member, db: DB, request: Request) -> Project:
    if db.scalar(select(Project).where(Project.org_id == p.org_id, Project.slug == body.slug)):
        raise Conflict("project slug already exists")
    proj = Project(org_id=p.org_id, **body.model_dump())
    db.add(proj)
    db.flush()
    _audit(db, p, request, "project.create", "project", proj.id)
    db.commit()
    return proj


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, p: CurrentUser, db: DB) -> Project:
    return get_project_or_404(db, p, project_id)


# ----------------------------------------------------------------------------- datasets


def _dataset_out(db: DB, ds: Dataset) -> DatasetOut:
    versions = db.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id == ds.id)
                          .order_by(DatasetVersion.version.desc())).all()
    out = DatasetOut.model_validate(ds)
    out.versions = [DatasetVersionOut.model_validate(v) for v in versions]
    return out


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetOut])
def list_datasets(project_id: uuid.UUID, p: CurrentUser, db: DB) -> list[DatasetOut]:
    get_project_or_404(db, p, project_id)
    rows = db.scalars(select(Dataset).where(Dataset.project_id == project_id, Dataset.org_id == p.org_id)
                      .order_by(Dataset.name)).all()
    return [_dataset_out(db, d) for d in rows]


@router.post("/projects/{project_id}/datasets", response_model=DatasetOut, status_code=201)
def create_dataset(project_id: uuid.UUID, body: DatasetIn, p: Member, db: DB, request: Request) -> DatasetOut:
    get_project_or_404(db, p, project_id)
    if db.scalar(select(Dataset).where(Dataset.project_id == project_id, Dataset.name == body.name)):
        raise Conflict("dataset name already exists in project")
    ds = Dataset(org_id=p.org_id, project_id=project_id, **body.model_dump())
    db.add(ds)
    db.flush()
    _audit(db, p, request, "dataset.create", "dataset", ds.id)
    db.commit()
    return _dataset_out(db, ds)


def _get_dataset(db: DB, p: Any, dataset_id: uuid.UUID) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if ds is None or ds.org_id != p.org_id:
        raise NotFound("dataset not found")
    return ds


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: uuid.UUID, p: CurrentUser, db: DB) -> DatasetOut:
    return _dataset_out(db, _get_dataset(db, p, dataset_id))


@router.post("/datasets/{dataset_id}/versions", response_model=DatasetVersionOut, status_code=201)
def upload_dataset_version(
    dataset_id: uuid.UUID, p: Member, db: DB, request: Request,
    file: UploadFile = File(...), notes: str = Form(default=""),
) -> DatasetVersion:
    ds = _get_dataset(db, p, dataset_id)
    s = get_settings()
    name = file.filename or ""
    if not name.lower().endswith((".jsonl", ".ndjson")):
        raise ValidationFailed("only .jsonl / .ndjson files are accepted")
    if file.content_type not in (None, "", "application/jsonl", "application/x-ndjson", "application/json",
                                 "application/octet-stream", "text/plain", "application/x-jsonlines"):
        raise ValidationFailed(f"unsupported content type '{file.content_type}'")
    # Sync handler (runs in FastAPI's threadpool): the parsing and DB work below are blocking and
    # must not run on the event loop. Bounded read: never buffer more than the limit + 1 byte.
    content = file.file.read(s.max_upload_bytes + 1)
    if len(content) > s.max_upload_bytes:
        raise ValidationFailed(f"file exceeds {s.max_upload_bytes} bytes", status_code=413, code="payload_too_large")
    cases = parse_jsonl(content, max_cases=s.max_cases_per_upload)
    dv = create_version(db, ds, cases, notes=notes[:2000], source_filename=name[:300])
    _audit(db, p, request, "dataset.version_upload", "dataset_version", dv.id,
           {"cases": len(cases), "content_hash": dv.content_hash})
    db.commit()
    return dv


@router.get("/dataset-versions/{version_id}/cases", response_model=list[TestCaseOut])
def list_cases(
    version_id: uuid.UUID, p: CurrentUser, db: DB, response: Response,
    limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0),
    tag: str | None = None,
) -> list[TestCase]:
    dv = db.get(DatasetVersion, version_id)
    if dv is None or dv.org_id != p.org_id:
        raise NotFound("dataset version not found")
    q = select(TestCase).where(TestCase.dataset_version_id == version_id)
    if tag:
        q = q.where(TestCase.tags.contains([tag]))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    response.headers["X-Total-Count"] = str(total)
    return list(db.scalars(q.order_by(TestCase.position).offset(offset).limit(limit)))


# ----------------------------------------------------------------------------- prompts


def _template_out(db: DB, t: PromptTemplate) -> PromptTemplateOut:
    out = PromptTemplateOut.model_validate(t)
    out.versions = [PromptVersionOut.model_validate(v) for v in db.scalars(
        select(PromptVersion).where(PromptVersion.template_id == t.id).order_by(PromptVersion.version.desc()))]
    return out


@router.get("/projects/{project_id}/prompts", response_model=list[PromptTemplateOut])
def list_prompts(project_id: uuid.UUID, p: CurrentUser, db: DB) -> list[PromptTemplateOut]:
    get_project_or_404(db, p, project_id)
    return [_template_out(db, t) for t in db.scalars(
        select(PromptTemplate).where(PromptTemplate.project_id == project_id).order_by(PromptTemplate.name))]


@router.post("/projects/{project_id}/prompts", response_model=PromptTemplateOut, status_code=201)
def create_prompt(project_id: uuid.UUID, body: PromptTemplateIn, p: Member, db: DB, request: Request) -> PromptTemplateOut:
    get_project_or_404(db, p, project_id)
    if db.scalar(select(PromptTemplate).where(PromptTemplate.project_id == project_id,
                                              PromptTemplate.name == body.name)):
        raise Conflict("prompt name already exists in project")
    t = PromptTemplate(org_id=p.org_id, project_id=project_id, **body.model_dump())
    db.add(t)
    db.flush()
    _audit(db, p, request, "prompt.create", "prompt_template", t.id)
    db.commit()
    return _template_out(db, t)


def prompt_hash(system_prompt: str, user_template: str) -> str:
    return hashlib.sha256(f"{system_prompt}\x00{user_template}".encode()).hexdigest()


@router.post("/prompts/{template_id}/versions", response_model=PromptVersionOut, status_code=201)
def create_prompt_version(template_id: uuid.UUID, body: PromptVersionIn, p: Member, db: DB, request: Request) -> PromptVersion:
    t = db.get(PromptTemplate, template_id)
    if t is None or t.org_id != p.org_id:
        raise NotFound("prompt template not found")
    h = prompt_hash(body.system_prompt, body.user_template)
    existing = db.scalar(select(PromptVersion).where(PromptVersion.template_id == t.id, PromptVersion.content_hash == h))
    if existing:
        return existing
    nxt = (db.scalar(select(func.max(PromptVersion.version)).where(PromptVersion.template_id == t.id)) or 0) + 1
    pv = PromptVersion(org_id=p.org_id, template_id=t.id, version=nxt, content_hash=h, **body.model_dump())
    db.add(pv)
    db.flush()
    _audit(db, p, request, "prompt.version_create", "prompt_version", pv.id, {"version": nxt})
    db.commit()
    return pv


# ----------------------------------------------------------------------------- model configs


@router.get("/providers")
def list_providers(p: CurrentUser) -> list[dict[str, Any]]:
    s = get_settings()
    return [
        {"name": "local", "configured": True, "is_real_llm": False,
         "label": "Deterministic local adapter (rule-based, not an LLM)"},
        {"name": "mock_scripted", "configured": True, "is_real_llm": False,
         "label": "Scripted outputs from dataset (regression demos, not a model)"},
        {"name": "gemini", "configured": bool(s.gemini_api_key), "is_real_llm": True, "label": "Google Gemini"},
        {"name": "openai", "configured": bool(s.openai_api_key), "is_real_llm": True, "label": "OpenAI"},
    ]


@router.get("/projects/{project_id}/model-configs", response_model=list[ModelConfigOut])
def list_model_configs(project_id: uuid.UUID, p: CurrentUser, db: DB) -> list[ModelConfig]:
    get_project_or_404(db, p, project_id)
    return list(db.scalars(select(ModelConfig).where(ModelConfig.project_id == project_id).order_by(ModelConfig.name)))


@router.post("/projects/{project_id}/model-configs", response_model=ModelConfigOut, status_code=201)
def create_model_config(project_id: uuid.UUID, body: ModelConfigIn, p: Member, db: DB, request: Request) -> ModelConfig:
    get_project_or_404(db, p, project_id)
    validate_target_config(body.params)
    mc = ModelConfig(org_id=p.org_id, project_id=project_id, **body.model_dump())
    db.add(mc)
    db.flush()
    _audit(db, p, request, "model_config.create", "model_config", mc.id, {"provider": body.provider})
    db.commit()
    return mc


# ----------------------------------------------------------------------------- targets


@router.get("/projects/{project_id}/targets", response_model=list[TargetOut])
def list_targets(project_id: uuid.UUID, p: CurrentUser, db: DB) -> list[Target]:
    get_project_or_404(db, p, project_id)
    return list(db.scalars(select(Target).where(Target.project_id == project_id).order_by(Target.name)))


@router.post("/projects/{project_id}/targets", response_model=TargetOut, status_code=201)
def create_target(project_id: uuid.UUID, body: TargetIn, p: Member, db: DB, request: Request) -> Target:
    get_project_or_404(db, p, project_id)
    validate_target_config(body.config)
    if body.kind == "llm":
        mc = db.get(ModelConfig, body.model_config_id) if body.model_config_id else None
        if mc is None or mc.project_id != project_id:
            raise ValidationFailed("llm targets require a model_config_id from this project")
        if body.prompt_version_id:
            pv = db.get(PromptVersion, body.prompt_version_id)
            if pv is None or pv.org_id != p.org_id:
                raise ValidationFailed("prompt version not found")
    t = Target(org_id=p.org_id, project_id=project_id, **body.model_dump())
    db.add(t)
    db.flush()
    _audit(db, p, request, "target.create", "target", t.id, {"kind": body.kind})
    db.commit()
    return t


# ----------------------------------------------------------------------------- evaluators


@router.get("/evaluator-types")
def evaluator_types(p: CurrentUser) -> list[dict[str, str]]:
    return [{"type": s.type, "kind": s.kind, "description": s.description} for s in REGISTRY.values()]


@router.get("/projects/{project_id}/evaluators", response_model=list[EvaluatorOut])
def list_evaluators(project_id: uuid.UUID, p: CurrentUser, db: DB) -> list[EvaluatorConfig]:
    get_project_or_404(db, p, project_id)
    return list(db.scalars(select(EvaluatorConfig).where(EvaluatorConfig.project_id == project_id)
                           .order_by(EvaluatorConfig.name)))


@router.post("/projects/{project_id}/evaluators", response_model=EvaluatorOut, status_code=201)
def create_evaluator(project_id: uuid.UUID, body: EvaluatorIn, p: Member, db: DB, request: Request) -> EvaluatorConfig:
    get_project_or_404(db, p, project_id)
    spec = REGISTRY.get(body.type)
    if spec is None:
        raise ValidationFailed(f"unknown evaluator type '{body.type}'")
    ev = EvaluatorConfig(org_id=p.org_id, project_id=project_id, name=body.name, type=body.type, kind=spec.kind,
                         params=body.params, threshold=body.threshold,
                         gating=body.gating and spec.kind == "deterministic")
    db.add(ev)
    db.flush()
    _audit(db, p, request, "evaluator.create", "evaluator_config", ev.id, {"type": body.type})
    db.commit()
    return ev


# ----------------------------------------------------------------------------- experiments


@router.get("/projects/{project_id}/experiments", response_model=list[ExperimentOut])
def list_experiments(project_id: uuid.UUID, p: CurrentUser, db: DB) -> list[Experiment]:
    get_project_or_404(db, p, project_id)
    return list(db.scalars(select(Experiment).where(Experiment.project_id == project_id)
                           .order_by(Experiment.created_at.desc())))


@router.post("/projects/{project_id}/experiments", response_model=ExperimentOut, status_code=201)
def create_experiment(project_id: uuid.UUID, body: ExperimentIn, p: Member, db: DB, request: Request) -> Experiment:
    get_project_or_404(db, p, project_id)
    if body.dataset_id:
        ds = db.get(Dataset, body.dataset_id)
        if ds is None or ds.project_id != project_id:
            raise ValidationFailed("dataset not found in project")
    e = Experiment(org_id=p.org_id, project_id=project_id, **body.model_dump())
    db.add(e)
    db.flush()
    _audit(db, p, request, "experiment.create", "experiment", e.id)
    db.commit()
    return e
