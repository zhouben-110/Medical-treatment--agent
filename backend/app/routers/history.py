from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.database import get_db
from app.schemas import SessionResponse, SessionDetailResponse, MessageResponse
from app.models import Session, Message, User
from app import graph as graph_module
from app.auth import get_current_user
from app.redis import untrack_session, invalidate_session_cache

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/history", response_model=list[SessionResponse])
async def get_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # 只返回当前用户的 session
    result = await db.execute(
        select(
            Session.id,
            Session.title,
            Session.created_at,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.session_id == Session.id)
        .where(Session.user_id == user.id)
        .group_by(Session.id)
        .order_by(Session.created_at.desc())
    )
    rows = result.all()

    return [
        SessionResponse(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            message_count=row.message_count,
        )
        for row in rows
    ]


@router.get("/history/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 验证 session 属于当前用户
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

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
async def delete_session(session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 验证 session 属于当前用户
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权删除该会话")

    await db.execute(delete(Message).where(Message.session_id == session_id))
    await db.delete(session)
    await db.commit()

    if graph_module.medical_graph is not None:
        try:
            await graph_module.medical_graph.checkpointer.adelete_thread(session_id)
        except Exception as e:
            print(f"[delete_session] checkpoint cleanup failed for {session_id}: {e}")

    await untrack_session(session_id)
    await invalidate_session_cache(session_id)

    return {"ok": True, "session_id": session_id}
