from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db, async_session
from app.schemas import ChatRequest, ChatResponse
from app.models import Session, Message
from app import graph as graph_module
from app.auth import verify_api_key
from app.summarizer import maybe_summarize_messages
import json
import logging

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(dependencies=[Depends(verify_api_key)])

NODE_TO_STAGE = {"question": "questioning", "advise": "completed"}
STREAMING_NODES = set(NODE_TO_STAGE.keys())
PROGRESS_NODES = {
    "triage": "triaging",
    "supervisor": "routing",
    "analyze_symptoms": "analyzing",
    "match_diseases": "diagnosing",
}


async def _maybe_summarize_state(cfg: dict):
    """检查图状态中的消息数量，超过阈值则摘要早期消息"""
    st = await graph_module.medical_graph.aget_state(cfg)
    values = st.values or {}
    messages = values.get("messages", [])
    if len(messages) <= 12:
        return

    # 提取消息为 dict 列表
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
        # 更新图状态中的消息
        graph_module.medical_graph.update_state(cfg, {"messages": summarized})


async def _persist_assistant_msg(session_id: str, content: str, diagnosis: str | None):
    async with async_session() as db:
        db.add(Message(session_id=session_id, role="assistant", content=content))
        if diagnosis:
            s = await db.get(Session, session_id)
            if s:
                s.diagnosis = diagnosis
        await db.commit()


def _build_graph_input(user_message: str, session_id: str, is_new: bool) -> dict:
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
    return {"messages": [{"role": "user", "content": user_message}]}


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


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest, db: AsyncSession = Depends(get_db)):
    session = await _ensure_session_and_log_user(body, db)
    session_id = str(session.id)

    cfg = {"configurable": {"thread_id": session_id}}
    st = await graph_module.medical_graph.aget_state(cfg)
    is_new = st.created_at is None

    if not is_new:
        await _maybe_summarize_state(cfg)

    graph_input = _build_graph_input(body.message, session_id, is_new)
    result = await graph_module.medical_graph.ainvoke(graph_input, config=cfg)

    last_msg = result["messages"][-1] if result.get("messages") else None
    ai_reply = (
        getattr(last_msg, "content", None)
        or (last_msg.get("content") if isinstance(last_msg, dict) else None)
        or "抱歉，我无法处理您的请求。"
    )

    stage = result.get("current_stage", "unknown")
    symptoms = result.get("symptoms", []) or []
    diseases = result.get("possible_diseases", []) or []
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


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(request: Request, body: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        session = await _ensure_session_and_log_user(body, db)
        session_id = str(session.id)

        cfg = {"configurable": {"thread_id": session_id}}
        st = await graph_module.medical_graph.aget_state(cfg)
        is_new = st.created_at is None

        if not is_new:
            await _maybe_summarize_state(cfg)

        graph_input = _build_graph_input(body.message, session_id, is_new)
    except Exception as e:
        logger.error(f"Error in chat_stream setup: {e}", exc_info=True)
        raise

    async def generate():
        full_text_by_node: dict[str, str] = {}
        current_stage_emitted: str | None = None

        try:
            yield f"data: {json.dumps({'type': 'meta', 'session_id': session_id}, ensure_ascii=False)}\n\n"

            async for ev in graph_module.medical_graph.astream_events(
                graph_input, config=cfg, version="v2"
            ):
                ev_event = ev.get("event")
                node = (ev.get("metadata") or {}).get("langgraph_node")

                # 进度事件：analyze/diagnose 节点开始时通知前端
                if ev_event == "on_chain_start" and node in PROGRESS_NODES:
                    stage = PROGRESS_NODES[node]
                    if current_stage_emitted != stage:
                        yield f"data: {json.dumps({'type': 'stage', 'stage': stage}, ensure_ascii=False)}\n\n"
                        current_stage_emitted = stage
                    continue

                if ev_event != "on_chat_model_stream":
                    continue
                if node not in STREAMING_NODES:
                    continue

                chunk_obj = ev.get("data", {}).get("chunk")
                chunk = getattr(chunk_obj, "content", "") if chunk_obj is not None else ""
                if not chunk:
                    continue

                full_text_by_node.setdefault(node, "")
                full_text_by_node[node] += chunk

                stage = NODE_TO_STAGE[node]
                if current_stage_emitted != stage:
                    yield f"data: {json.dumps({'type': 'stage', 'stage': stage}, ensure_ascii=False)}\n\n"
                    current_stage_emitted = stage

                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk, 'stage': stage}, ensure_ascii=False)}\n\n"

            final_st = await graph_module.medical_graph.aget_state(cfg)
            v = final_st.values or {}
            final_meta = {
                "type": "meta",
                "session_id": session_id,
                "symptoms": v.get("symptoms", []) or [],
                "stage": v.get("current_stage", "unknown"),
                "need_more_info": bool(v.get("need_more_info", False)),
                "possible_diseases": v.get("possible_diseases", []) or [],
            }
            yield f"data: {json.dumps(final_meta, ensure_ascii=False)}\n\n"

            assistant_text = full_text_by_node.get("advise") or full_text_by_node.get("question") or ""
            diagnosis = None
            if "advise" in full_text_by_node:
                diseases = v.get("possible_diseases") or []
                diagnosis = diseases[0] if diseases else None
            if assistant_text:
                await _persist_assistant_msg(session_id, assistant_text, diagnosis)

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Error in chat_stream generator: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': '服务器内部错误，请稍后重试'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
