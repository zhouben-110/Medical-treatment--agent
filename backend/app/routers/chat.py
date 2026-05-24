from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ChatRequest, ChatResponse
from app.schemas import Session, Message
from app.graph import medical_graph
from app.state import Message as StateMessage
from datetime import datetime
import uuid

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    # 获取或创建会话
    if request.session_id:
        session = await db.get(Session, request.session_id)
        if not session:
            session = Session(id=request.session_id, title=request.message[:20])
            db.add(session)
    else:
        session = Session(title=request.message[:20])
        db.add(session)
        await db.flush()

    # 保存用户消息
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=request.message
    )
    db.add(user_msg)

    # 获取历史消息
    from sqlalchemy import select
    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.timestamp)
    )
    history = result.scalars().all()

    messages = [{"role": m.role, "content": m.content} for m in history]

    # 调用状态机
    initial_state = {
        "messages": messages,
        "symptoms": [],
        "current_stage": "start",
        "confidence": 0.0,
        "possible_diseases": [],
        "treatment_plan": "",
        "need_more_info": True,
        "session_id": session.id,
        "user_message": request.message
    }

    result = await medical_graph.ainvoke(initial_state)

    # 获取AI回复
    ai_reply = result["messages"][-1]["content"] if result["messages"] else "抱歉，我无法处理您的请求。"

    # 保存AI回复
    ai_msg = Message(
        session_id=session.id,
        role="assistant",
        content=ai_reply
    )
    db.add(ai_msg)

    # 更新会话诊断
    if result.get("treatment_plan"):
        session.diagnosis = result["possible_diseases"][0] if result["possible_diseases"] else None

    await db.commit()

    return ChatResponse(
        reply=ai_reply,
        stage=result.get("current_stage", "unknown"),
        symptoms=result.get("symptoms", []),
        session_id=session.id
    )
