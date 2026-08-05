from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.schemas import ChatRequest, ChatResponse
from app.models import Session, Message, User
from app import graph as graph_module
from app.auth import get_current_user
from app.summarizer import maybe_summarize_messages
from app.redis import (
    check_rate_limit,
    get_cached_session_state, cache_session_state, invalidate_session_cache,
    track_session,
)
from app.security import check_prompt_injection
from langgraph.errors import GraphRecursionError
import json
import logging

logger = logging.getLogger(__name__)


async def rate_limit_chat(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    allowed = await check_rate_limit(f"rl:chat:{client_ip}", limit=20, window=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


router = APIRouter(dependencies=[Depends(get_current_user)])


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


VALID_STAGES = {"start", "triaged", "analyzing", "questioning", "diagnosing", "completed", "emergency"}


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
            "patient_profile": {"age_group": None, "is_pregnant": None, "allergies": []},
        }

    # ⑤ 续轮 stage 归一化：若持久化的 current_stage 不在已知合法集合内或残留 supervisor 中间态，重置为 start
    if current_stage not in VALID_STAGES or current_stage.startswith("supervisor:"):
        logger.warning(f"检测到异常/残留持久化 current_stage={current_stage!r}，归一化重置为 'start'")
        current_stage = "start"

    # 诊断完成或状态被重置后，开启/恢复诊断
    if current_stage in ("completed", "start"):
        # 保留上一轮的症状和诊断结论
        old_symptoms = prev_state.get("symptoms", []) if prev_state else []
        old_diseases = prev_state.get("possible_diseases", []) if prev_state else []
        old_treatment = prev_state.get("treatment_plan", "") if prev_state else ""
        old_profile = prev_state.get("patient_profile", {"age_group": None, "is_pregnant": None, "allergies": []}) if prev_state else {"age_group": None, "is_pregnant": None, "allergies": []}
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
            "patient_profile": old_profile,
            "_reset_context": True if current_stage == "completed" else False,
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

        await graph_module.medical_graph.aupdate_state(cfg, {"messages": keep_messages})


async def _ensure_session_and_log_user(request: ChatRequest, db: AsyncSession, user_id: str) -> Session:
    sid = str(request.session_id) if request.session_id else None
    if sid:
        session = await db.get(Session, sid)
        # 验证 session 属于当前用户
        if session and session.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问该会话")
        if not session:
            session = Session(id=sid, user_id=user_id, title=request.message[:20])
            db.add(session)
    else:
        session = Session(user_id=user_id, title=request.message[:20])
        db.add(session)
        await db.flush()

    db.add(Message(session_id=session.id, role="user", content=request.message))
    await db.commit()
    return session


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_chat)])
async def chat(request: Request, body: ChatRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    check_prompt_injection(body.message)
    session = await _ensure_session_and_log_user(body, db, user.id)
    session_id = str(session.id)
    await track_session(session_id)

    cfg = {"configurable": {"thread_id": session_id}, "recursion_limit": 20}

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
    try:
        result = await graph_module.medical_graph.ainvoke(graph_input, config=cfg)
    except GraphRecursionError as e:
        logger.error(f"路由死循环被 recursion_limit 截断: {e}", exc_info=True)
        await graph_module.medical_graph.aupdate_state(cfg, {"current_stage": "completed"})
        raise HTTPException(status_code=500, detail="系统繁忙，请稍后重试")

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
async def chat_stream(request: Request, body: ChatRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    check_prompt_injection(body.message)
    try:
        session = await _ensure_session_and_log_user(body, db, user.id)
        session_id = str(session.id)
        await track_session(session_id)

        cfg = {"configurable": {"thread_id": session_id}, "recursion_limit": 20}

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

            # ── 节点级真流式：astream(stream_mode="updates") ────────
            # 每个节点跑完立即 yield 该节点的 state 增量，用户能实时看到
            # "正在分诊/分析/追问" 状态推进，不再是 10s 空白。
            #
            # 为什么不走 token 级流式（astream_events / chain.astream）：
            # 当前 langgraph + PostgresSaver 组合下，astream_events 回调会被吞，
            # 实测 0 个 on_chat_model_stream 事件出来。chain.astream + StreamWriter
            # 是更可靠的方案，但需要改 diagnose/question/finalize 三个节点用
            # get_stream_writer().write() 把 token 推出来，列为后续工作。
            final_output: dict = {}
            streamed_text = ""
            accumulated = dict(graph_input)

            def _sse(payload: dict) -> str:
                return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            STATUS_LABELS = {
                "triage": "正在分诊",
                "analyze": "正在分析症状",
                "question": "正在生成追问",
                "diagnose": "正在生成诊断",
                "finalize": "正在生成诊断报告",
            }
            USER_FACING_NODES = {"diagnose", "question", "finalize", "triage", "supervisor"}

            try:
                async for chunk in graph_module.medical_graph.astream(
                    graph_input, config=cfg, stream_mode="updates"
                ):
                    for node_name, state_delta in chunk.items():
                        if node_name in STATUS_LABELS:
                            yield _sse({"type": "status", "stage": node_name,
                                        "content": STATUS_LABELS[node_name]})
                        if isinstance(state_delta, dict):
                            accumulated.update(state_delta)
                            if state_delta.get("messages") and node_name in USER_FACING_NODES:
                                msgs = state_delta["messages"]
                                last = msgs[-1]
                                content = (
                                    getattr(last, "content", None)
                                    or (last.get("content") if isinstance(last, dict) else "")
                                    or ""
                                )
                                if content and not streamed_text:
                                    streamed_text = content
                                    yield _sse({"type": "chunk",
                                                "content": content,
                                                "stage": node_name})
            except GraphRecursionError as e:
                logger.error(f"路由死循环被 recursion_limit 截断: {e}", exc_info=True)
                # 恢复线程到安全阶段，避免下轮继续卡死
                await graph_module.medical_graph.aupdate_state(
                    cfg, {"current_stage": "completed"}
                )
                yield _sse({"type": "error", "content": "系统繁忙，请稍后重试"})
                return
            except Exception as e:
                logger.error(f"astream failed, fallback to ainvoke: {e}", exc_info=True)
                result = await graph_module.medical_graph.ainvoke(graph_input, config=cfg)
                accumulated = result
                msgs = result.get("messages") or []
                if msgs:
                    last = msgs[-1]
                    content = (
                        getattr(last, "content", None)
                        or (last.get("content") if isinstance(last, dict) else None)
                        or ""
                    )
                    if content and not streamed_text:
                        streamed_text = content
                        yield _sse({"type": "chunk", "content": content, "stage": "fallback"})

            await invalidate_session_cache(session_id)
            final_output = accumulated

            stage = final_output.get("current_stage", "unknown")
            if stage == "completed":
                yield _sse({"type": "stage", "stage": "completed"})
            elif stage == "emergency":
                yield _sse({"type": "stage", "stage": "emergency"})
            elif stage == "questioning":
                yield _sse({"type": "stage", "stage": "questioning"})

            # 如果 streamed_text 为空，但累计 state 中有 assistant 消息（例如急诊/分诊），从中提取
            if not streamed_text and final_output.get("messages"):
                last_m = final_output["messages"][-1]
                content = (
                    getattr(last_m, "content", None)
                    or (last_m.get("content") if isinstance(last_m, dict) else "")
                    or ""
                )
                role = getattr(last_m, "type", None) or (last_m.get("role") if isinstance(last_m, dict) else "")
                if content and role in ("ai", "assistant"):
                    streamed_text = content
                    yield _sse({"type": "chunk", "content": content, "stage": stage})

            symptoms = final_output.get("symptoms", []) or []
            diseases = final_output.get("possible_diseases") or []
            need_more = bool(final_output.get("need_more_info", False))
            yield _sse({
                "type": "meta",
                "session_id": session_id,
                "symptoms": symptoms,
                "stage": stage,
                "need_more_info": need_more,
                "possible_diseases": diseases,
            })

            diagnosis = diseases[0] if (stage == "completed" and diseases) else None
            if streamed_text:
                await _persist_assistant_msg(session_id, streamed_text, diagnosis)

            yield _sse({"type": "done"})
        except Exception as e:
            logger.error(f"Error in chat_stream generator: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Server error'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


from pydantic import BaseModel


class UpdateSymptomsRequest(BaseModel):
    session_id: str
    symptoms: list[str]


@router.post("/chat/symptoms/update")
async def update_symptoms(body: UpdateSymptomsRequest, user: User = Depends(get_current_user)):
    session_id = body.session_id
    cfg = {"configurable": {"thread_id": session_id}}

    st = await graph_module.medical_graph.aget_state(cfg)
    if not st or st.values is None:
        raise HTTPException(status_code=404, detail="未找到会话或状态")

    await graph_module.medical_graph.aupdate_state(cfg, {"symptoms": body.symptoms})
    await invalidate_session_cache(session_id)
    return {"ok": True, "symptoms": body.symptoms}

