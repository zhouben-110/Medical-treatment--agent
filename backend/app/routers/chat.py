from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.schemas import ChatRequest, ChatResponse
from app.models import Session, Message
from app import graph as graph_module
from app.auth import verify_api_key
from app.summarizer import maybe_summarize_messages
from app.redis import (
    check_rate_limit,
    get_cached_session_state, cache_session_state, invalidate_session_cache,
    track_session,
)
import json
import logging

logger = logging.getLogger(__name__)


async def rate_limit_chat(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    allowed = await check_rate_limit(f"rl:chat:{client_ip}", limit=20, window=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


router = APIRouter(dependencies=[Depends(verify_api_key)])


async def _maybe_summarize_state(cfg: dict):
    st = await graph_module.medical_graph.aget_state(cfg)
    values = st.values or {}
    messages = values.get("messages", [])
    if len(messages) <= 12:
        return

    msg_dicts = []
    for m in messages:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
        content = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
        if role == "human":
            msg_dicts.append({"role": "user", "content": content})
        elif role == "ai":
            msg_dicts.append({"role": "assistant", "content": content})

    summarized = await maybe_summarize_messages(msg_dicts)
    if summarized is not msg_dicts:
        graph_module.medical_graph.update_state(cfg, {"messages": summarized})


async def _persist_assistant_msg(session_id: str, content: str, diagnosis: str | None):
    async with async_session() as db:
        db.add(Message(session_id=session_id, role="assistant", content=content))
        if diagnosis:
            s = await db.get(Session, session_id)
            if s:
                s.diagnosis = diagnosis
        await db.commit()


def _build_graph_input(user_message: str, session_id: str, is_new: bool, current_stage: str = "start", prev_state: dict = None) -> dict:
    if is_new:
        return {
            "messages": [{"role": "user", "content": user_message}],
            "symptoms": [],
            "current_stage": "start",
            "confidence": 0.0,
            "possible_diseases": [],
            "treatment_plan": "",
            "need_more_info": True,
            "session_id": session_id,
            "retrieved_context": "",
            "is_emergency": False,
            "red_flags": [],
            "emergency_message": "",
        }
    # 诊断完成后用户继续提问，重置状态开启新一轮诊断
    if current_stage == "completed":
        # 保留上一轮的症状和诊断结论
        old_symptoms = prev_state.get("symptoms", []) if prev_state else []
        old_diseases = prev_state.get("possible_diseases", []) if prev_state else []
        old_treatment = prev_state.get("treatment_plan", "") if prev_state else ""
        return {
            "messages": [{"role": "user", "content": user_message}],
            "symptoms": old_symptoms,  # 保留已识别症状
            "current_stage": "start",
            "confidence": 0.0,
            "possible_diseases": old_diseases,
            "treatment_plan": old_treatment,
            "need_more_info": True,
            "retrieved_context": "",
            "is_emergency": False,
            "red_flags": [],
            "emergency_message": "",
            "_reset_context": True,  # 标记需要清理旧上下文
        }
    return {"messages": [{"role": "user", "content": user_message}]}


async def _reset_context_if_needed(cfg: dict, graph_input: dict):
    """诊断完成后重置：摘要旧对话，保留诊断结论"""
    if not graph_input.pop("_reset_context", False):
        return

    st = await graph_module.medical_graph.aget_state(cfg)
    old_messages = st.values.get("messages", []) if st.values else []

    if len(old_messages) > 2:
        # 摘要旧对话
        msg_dicts = []
        last_assistant_msg = None
        for m in old_messages:
            role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
            content = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
            if role in ("human", "user"):
                msg_dicts.append({"role": "user", "content": content})
            elif role in ("ai", "assistant"):
                msg_dicts.append({"role": "assistant", "content": content})
                last_assistant_msg = m  # 记录最后一条助手消息

        summarized = await maybe_summarize_messages(msg_dicts)

        # 保留：摘要 + 最后一条诊断消息
        keep_messages = [m for m in summarized if m.get("role") == "system"]
        if last_assistant_msg:
            keep_messages.append(last_assistant_msg)

        # update_state 是同步方法，需要用线程执行
        import asyncio
        await asyncio.to_thread(graph_module.medical_graph.update_state, cfg, {"messages": keep_messages})


async def _ensure_session_and_log_user(request: ChatRequest, db: AsyncSession) -> Session:
    sid = str(request.session_id) if request.session_id else None
    if sid:
        session = await db.get(Session, sid)
        if not session:
            session = Session(id=sid, title=request.message[:20])
            db.add(session)
    else:
        session = Session(title=request.message[:20])
        db.add(session)
        await db.flush()

    db.add(Message(session_id=session.id, role="user", content=request.message))
    await db.commit()
    return session


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_chat)])
async def chat(request: Request, body: ChatRequest, db: AsyncSession = Depends(get_db)):
    session = await _ensure_session_and_log_user(body, db)
    session_id = str(session.id)
    await track_session(session_id)

    cfg = {"configurable": {"thread_id": session_id}}

    # 检查 Redis 会话缓存
    cached_state = await get_cached_session_state(session_id)
    if cached_state is not None:
        is_new = cached_state.get("created_at") is None
    else:
        st = await graph_module.medical_graph.aget_state(cfg)
        is_new = st.created_at is None
        await cache_session_state(session_id, {"created_at": str(st.created_at) if st.created_at else None})

    if not is_new:
        await _maybe_summarize_state(cfg)

    # 获取当前阶段和状态，用于判断是否需要重置
    current_stage = "start"
    prev_state = None
    if not is_new:
        st = await graph_module.medical_graph.aget_state(cfg)
        current_stage = st.values.get("current_stage", "start") if st.values else "start"
        prev_state = st.values or {}

    graph_input = _build_graph_input(body.message, session_id, is_new, current_stage, prev_state)
    await _reset_context_if_needed(cfg, graph_input)
    result = await graph_module.medical_graph.ainvoke(graph_input, config=cfg)
    await invalidate_session_cache(session_id)

    last_msg = result["messages"][-1] if result.get("messages") else None
    ai_reply = (
        getattr(last_msg, "content", None)
        or (last_msg.get("content") if isinstance(last_msg, dict) else None)
        or "Sorry, I could not process your request."
    )

    stage = result.get("current_stage", "unknown")
    symptoms = result.get("symptoms", []) or []
    diseases = result.get("possible_diseases") or []
    need_more = bool(result.get("need_more_info", False))

    diagnosis = diseases[0] if (stage == "completed" and diseases) else None
    await _persist_assistant_msg(session_id, ai_reply, diagnosis)

    return ChatResponse(
        reply=ai_reply,
        stage=stage,
        symptoms=symptoms,
        session_id=session_id,
        need_more_info=need_more,
        possible_diseases=diseases,
    )


@router.post("/chat/stream", dependencies=[Depends(rate_limit_chat)])
async def chat_stream(request: Request, body: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        session = await _ensure_session_and_log_user(body, db)
        session_id = str(session.id)
        await track_session(session_id)

        cfg = {"configurable": {"thread_id": session_id}}

        # 检查 Redis 会话缓存
        cached_state = await get_cached_session_state(session_id)
        if cached_state is not None:
            is_new = cached_state.get("created_at") is None
        else:
            st = await graph_module.medical_graph.aget_state(cfg)
            is_new = st.created_at is None
            await cache_session_state(session_id, {"created_at": str(st.created_at) if st.created_at else None})

        if not is_new:
            await _maybe_summarize_state(cfg)

        # 获取当前阶段和状态，用于判断是否需要重置
        current_stage = "start"
        prev_state = None
        if not is_new:
            st = await graph_module.medical_graph.aget_state(cfg)
            current_stage = st.values.get("current_stage", "start") if st.values else "start"
            prev_state = st.values or {}

        graph_input = _build_graph_input(body.message, session_id, is_new, current_stage, prev_state)
        await _reset_context_if_needed(cfg, graph_input)
    except Exception as e:
        logger.error(f"Error in chat_stream setup: {e}", exc_info=True)
        raise

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'meta', 'session_id': session_id}, ensure_ascii=False)}\n\n"

            result = await graph_module.medical_graph.ainvoke(graph_input, config=cfg)
            await invalidate_session_cache(session_id)

            stage = result.get("current_stage", "unknown")
            if stage == "completed":
                yield f"data: {json.dumps({'type': 'stage', 'stage': 'completed'}, ensure_ascii=False)}\n\n"
            elif stage == "emergency":
                yield f"data: {json.dumps({'type': 'stage', 'stage': 'emergency'}, ensure_ascii=False)}\n\n"
            elif stage == "questioning":
                yield f"data: {json.dumps({'type': 'stage', 'stage': 'questioning'}, ensure_ascii=False)}\n\n"

            last_msg = result["messages"][-1] if result.get("messages") else None
            ai_text = (
                getattr(last_msg, "content", None)
                or (last_msg.get("content") if isinstance(last_msg, dict) else None)
                or ""
            )
            if ai_text:
                chunk_size = 20
                for i in range(0, len(ai_text), chunk_size):
                    chunk = ai_text[i:i + chunk_size]
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk, 'stage': stage}, ensure_ascii=False)}\n\n"

            symptoms = result.get("symptoms", []) or []
            diseases = result.get("possible_diseases") or []
            need_more = bool(result.get("need_more_info", False))
            final_meta = {
                "type": "meta",
                "session_id": session_id,
                "symptoms": symptoms,
                "stage": stage,
                "need_more_info": need_more,
                "possible_diseases": diseases,
            }
            yield f"data: {json.dumps(final_meta, ensure_ascii=False)}\n\n"

            diagnosis = diseases[0] if (stage == "completed" and diseases) else None
            if ai_text:
                await _persist_assistant_msg(session_id, ai_text, diagnosis)

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Error in chat_stream generator: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Server error'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
