from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.models import ChatRequest, ChatResponse
from app.schemas import Session, Message
from app import graph as graph_module
import json
import traceback

router = APIRouter()

NODE_TO_STAGE = {"question": "questioning", "advise": "completed"}
STREAMING_NODES = set(NODE_TO_STAGE.keys())


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
        }
    return {"messages": [{"role": "user", "content": user_message}]}


async def _ensure_session_and_log_user(request: ChatRequest, db: AsyncSession) -> Session:
    if request.session_id:
        session = await db.get(Session, request.session_id)
        if not session:
            session = Session(id=request.session_id, title=request.message[:20])
            db.add(session)
    else:
        session = Session(title=request.message[:20])
        db.add(session)
        await db.flush()

    db.add(Message(session_id=session.id, role="user", content=request.message))
    await db.commit()
    return session


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    session = await _ensure_session_and_log_user(request, db)
    session_id = session.id

    cfg = {"configurable": {"thread_id": session_id}}
    st = await graph_module.medical_graph.aget_state(cfg)
    is_new = st.created_at is None

    graph_input = _build_graph_input(request.message, session_id, is_new)
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
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        session = await _ensure_session_and_log_user(request, db)
        session_id = session.id

        cfg = {"configurable": {"thread_id": session_id}}
        st = await graph_module.medical_graph.aget_state(cfg)
        is_new = st.created_at is None

        graph_input = _build_graph_input(request.message, session_id, is_new)
    except Exception as e:
        print(f"Error in chat_stream setup: {e}")
        traceback.print_exc()
        raise

    async def generate():
        full_text_by_node: dict[str, str] = {}
        current_stage_emitted: str | None = None

        try:
            yield f"data: {json.dumps({'type': 'meta', 'session_id': session_id}, ensure_ascii=False)}\n\n"

            async for ev in graph_module.medical_graph.astream_events(
                graph_input, config=cfg, version="v2"
            ):
                if ev.get("event") != "on_chat_model_stream":
                    continue
                node = (ev.get("metadata") or {}).get("langgraph_node")
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
            print(f"Error in chat_stream generator: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
