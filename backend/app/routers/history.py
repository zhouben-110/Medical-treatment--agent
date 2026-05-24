from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import SessionResponse, SessionDetailResponse, MessageResponse
from app.schemas import Session, Message

router = APIRouter()


@router.get("/history", response_model=list[SessionResponse])
async def get_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()

    response = []
    for session in sessions:
        msg_count = await db.execute(
            select(func.count()).where(Message.session_id == session.id)
        )
        count = msg_count.scalar()
        response.append(SessionResponse(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            message_count=count
        ))

    return response


@router.get("/history/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        return {"error": "Session not found"}, 404

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.timestamp)
    )
    messages = result.scalars().all()

    return SessionDetailResponse(
        messages=[MessageResponse(
            role=m.role,
            content=m.content,
            timestamp=m.timestamp
        ) for m in messages],
        diagnosis=session.diagnosis
    )
