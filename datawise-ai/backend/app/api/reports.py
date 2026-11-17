from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_ask_service, rate_limit_ask, request_id
from app.core.errors import AppError
from app.models import AuditEvent, SavedReport
from app.schemas.api import AskResponse, SavedReportCreate, SavedReportOut, SavedReportUpdate
from app.schemas.plan import QueryPlan
from app.services.ask import AskService
from app.services.compiler import PlanError, compile_plan

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _get_owned(db: DbSession, user: CurrentUser, report_id: int) -> SavedReport:
    rep = db.get(SavedReport, report_id)
    if rep is None or rep.org_id != user.org_id:  # never reveal other orgs' reports
        raise AppError(404, "not_found", "Report not found")
    return rep


@router.get("", response_model=list[SavedReportOut])
def list_reports(user: CurrentUser, db: DbSession) -> list[SavedReportOut]:
    rows = db.scalars(select(SavedReport).where(SavedReport.org_id == user.org_id)
                      .order_by(SavedReport.updated_at.desc())).all()
    return [SavedReportOut.model_validate(r) for r in rows]


@router.post("", response_model=SavedReportOut, status_code=201)
def create_report(body: SavedReportCreate, user: CurrentUser, db: DbSession, request: Request) -> SavedReportOut:
    try:
        compile_plan(body.plan, 1000)  # reject plans that do not compile
    except PlanError as e:
        raise AppError(422, "invalid_plan", "; ".join(e.issues)) from e
    rep = SavedReport(org_id=user.org_id, user_id=user.id, name=body.name, question=body.question,
                      plan=body.plan.model_dump(mode="json"))
    db.add(rep)
    db.flush()
    db.add(AuditEvent(org_id=user.org_id, user_id=user.id, action="report.created", detail={"report_id": rep.id},
                      request_id=request_id(request)))
    db.commit()
    db.refresh(rep)
    return SavedReportOut.model_validate(rep)


@router.get("/{report_id}", response_model=SavedReportOut)
def get_report(report_id: int, user: CurrentUser, db: DbSession) -> SavedReportOut:
    return SavedReportOut.model_validate(_get_owned(db, user, report_id))


@router.patch("/{report_id}", response_model=SavedReportOut)
def rename_report(report_id: int, body: SavedReportUpdate, user: CurrentUser, db: DbSession) -> SavedReportOut:
    rep = _get_owned(db, user, report_id)
    rep.name = body.name
    db.commit()
    db.refresh(rep)
    return SavedReportOut.model_validate(rep)


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: int, user: CurrentUser, db: DbSession, request: Request) -> Response:
    rep = _get_owned(db, user, report_id)
    db.delete(rep)
    db.add(AuditEvent(org_id=user.org_id, user_id=user.id, action="report.deleted", detail={"report_id": report_id},
                      request_id=request_id(request)))
    db.commit()
    return Response(status_code=204)


@router.post("/{report_id}/run", response_model=AskResponse, dependencies=[Depends(rate_limit_ask)])
def run_report(report_id: int, user: CurrentUser, db: DbSession, request: Request,
               svc: Annotated[AskService, Depends(get_ask_service)]) -> AskResponse:
    """Re-runs the stored plan directly (no planner call): same compiler + validator + executor path."""
    rep = _get_owned(db, user, report_id)
    plan = QueryPlan.model_validate(rep.plan)
    return svc.run_plan(db, user, rep.question, plan, request_id(request))
