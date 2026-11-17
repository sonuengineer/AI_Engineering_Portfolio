from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import get_db
from app.core.errors import NotFound
from app.models import Conversation, MemoryItem, Message, User
from app.schemas.api import AskIn, AskOut, ConversationOut, MemoryIn, MemoryOut, MessageOut
from app.services import chat as chat_service
from app.services.audit import audit

router = APIRouter(tags=["chat"])


@router.post("/chat/ask", response_model=AskOut)
def ask(body: AskIn, user: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> AskOut:
    r = chat_service.ask(db, user, body.question, body.conversation_id)
    return AskOut(**r.__dict__)


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(50)
        )
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def messages(conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Message]:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise NotFound("Conversation not found")
    return list(db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)))


@router.get("/memory", response_model=list[MemoryOut])
def list_memory(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[MemoryItem]:
    return list(db.scalars(select(MemoryItem).where(MemoryItem.user_id == user.id).order_by(MemoryItem.key)))


@router.put("/memory", response_model=MemoryOut)
def upsert_memory(body: MemoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> MemoryItem:
    item = db.scalar(select(MemoryItem).where(MemoryItem.user_id == user.id, MemoryItem.key == body.key))
    if item is None:
        item = MemoryItem(org_id=user.org_id, user_id=user.id, key=body.key, value=body.value)
        db.add(item)
    else:
        item.value = body.value
    audit(db, org_id=user.org_id, actor_id=user.id, action="memory.upsert", details={"key": body.key})
    db.commit()
    return item


@router.delete("/memory/{item_id}", status_code=204)
def delete_memory(item_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    item = db.get(MemoryItem, item_id)
    if item is None or item.user_id != user.id:
        raise NotFound("Memory item not found")
    db.delete(item)
    audit(db, org_id=user.org_id, actor_id=user.id, action="memory.delete", details={"key": item.key})
    db.commit()
