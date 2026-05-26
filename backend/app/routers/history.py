from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.database import get_db
from app.models import SessionResponse, SessionDetailResponse, MessageResponse
from app.schemas import Session, Message
from app import graph as graph_module

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
        raise HTTPException(status_code=404, detail="Session not found")

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


@router.delete("/history/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.execute(delete(Message).where(Message.session_id == session_id))
    await db.delete(session)
    await db.commit()

    if graph_module.medical_graph is not None:
        try:
            await graph_module.medical_graph.checkpointer.adelete_thread(session_id)
        except Exception as e:
            print(f"[delete_session] checkpoint cleanup failed for {session_id}: {e}")

    return {"ok": True, "session_id": session_id}
