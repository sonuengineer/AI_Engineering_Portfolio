from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_ask_service, rate_limit_ask, request_id
from app.models import QueryHistory
from app.schemas.api import AskRequest, AskResponse, HistoryItem
from app.services.ask import AskService

router = APIRouter(prefix="/api/v1", tags=["questions"])


@router.post("/questions/ask", response_model=AskResponse, dependencies=[Depends(rate_limit_ask)])
def ask(body: AskRequest, user: CurrentUser, db: DbSession, request: Request,
        svc: Annotated[AskService, Depends(get_ask_service)]) -> AskResponse:
    return svc.ask(db, user, body.question, request_id(request))


@router.get("/history", response_model=list[HistoryItem])
def history(user: CurrentUser, db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[HistoryItem]:
    rows = db.scalars(
        select(QueryHistory).where(QueryHistory.org_id == user.org_id)
        .order_by(QueryHistory.created_at.desc(), QueryHistory.id.desc()).limit(limit)
    ).all()
    return [HistoryItem.model_validate(r) for r in rows]
