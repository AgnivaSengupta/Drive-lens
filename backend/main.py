from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.agent.graph import build_agent
from backend.agent.memory import memory
from backend.middleware.telemetry import TimingMiddleware
from backend.models.schema import (
    ChatRequest,
    ChatResponse,
    CreateSessionRequest,
    FileResult,
    Session,
)

# ---------------------------------------------------------------------------
# Session-metadata database  (stores user→session mappings + titles)
# Conversation content itself lives in the LangGraph SQLite checkpointer.
# ---------------------------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
CHECKPOINT_DB_PATH = os.path.join(DATA_DIR, "checkpoints.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
        await checkpointer.setup()
        app.state.agent = build_agent(checkpointer)
        yield


app = FastAPI(title="TailorTalk Drive Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)

_sessions_conn = sqlite3.connect(
    os.path.join(DATA_DIR, "sessions.db"), check_same_thread=False
)
_sessions_conn.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id  TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL,
        title       TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
""")
_sessions_conn.commit()


# helpers
def _extract_files(result: dict) -> list[FileResult]:
    """Parse the last ToolMessage in the graph result into FileResult objects."""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                return [
                    FileResult(
                        id=f.get("id", ""),
                        name=f.get("name", ""),
                        mimeType=f.get("mimeType", ""),
                        webViewLink=f.get("webViewLink"),
                        modifiedTime=f.get("modifiedTime"),
                        size=f.get("size"),
                        iconLink=f.get("iconLink"),
                    )
                    for f in data.get("files", [])
                    if f.get("id") and f.get("name")
                ]
            except (json.JSONDecodeError, KeyError):
                pass
    return []


def _extract_query(result: dict) -> str | None:
    """Parse the last ToolMessage to extract the Drive query string used."""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                return data.get("query")
            except (json.JSONDecodeError, KeyError):
                pass
    return None


def _serialize_messages(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain message objects to JSON-safe dicts for the frontend."""
    out = []
    pending_tool_data: dict | None = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            out.append({"role": "user", "content": msg.content})
            pending_tool_data = None
        elif isinstance(msg, ToolMessage):
            try:
                pending_tool_data = json.loads(msg.content)
            except json.JSONDecodeError:
                pending_tool_data = None
        elif isinstance(msg, AIMessage) and msg.content:
            assistant_message = {"role": "assistant", "content": msg.content}
            if pending_tool_data:
                assistant_message["files"] = [
                    {
                        "id": f.get("id", ""),
                        "name": f.get("name", ""),
                        "mimeType": f.get("mimeType", ""),
                        "webViewLink": f.get("webViewLink"),
                        "modifiedTime": f.get("modifiedTime"),
                        "size": f.get("size"),
                        "iconLink": f.get("iconLink"),
                    }
                    for f in pending_tool_data.get("files", [])
                    if f.get("id") and f.get("name")
                ]
                assistant_message["drive_query"] = pending_tool_data.get("query")
                pending_tool_data = None
            out.append(assistant_message)
    return out


def _session_exists(session_id: str) -> bool:
    cur = _sessions_conn.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
    )
    return cur.fetchone() is not None


def _create_session_row(session_id: str, user_id: str, title: str) -> None:
    _sessions_conn.execute(
        "INSERT INTO sessions (session_id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, title, datetime.utcnow().isoformat()),
    )
    _sessions_conn.commit()


def _count_sessions(user_id: str) -> int:
    cur = _sessions_conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = ?",
        (user_id,),
    )
    return int(cur.fetchone()[0])


# Routes
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users/{user_id}/sessions", response_model=list[Session])
def list_sessions(user_id: str):
    cur = _sessions_conn.execute(
        "SELECT session_id, user_id, title, created_at FROM sessions "
        "WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    return [Session(session_id=r[0], user_id=r[1], title=r[2], created_at=r[3])
            for r in cur.fetchall()]


@app.get("/users/{user_id}/profile")
def get_user_profile(user_id: str):
    return {
        "user_id": user_id,
        "session_count": _count_sessions(user_id),
        "memory_count": memory.count_memories(user_id),
    }


@app.post("/users/{user_id}/sessions", response_model=Session, status_code=201)
def create_session(user_id: str, req: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    title = (req.title or "New Chat").strip() or "New Chat"
    created_at = datetime.utcnow().isoformat()
    _sessions_conn.execute(
        "INSERT INTO sessions (session_id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, title, created_at),
    )
    _sessions_conn.commit()
    return Session(session_id=session_id, user_id=user_id, title=title, created_at=created_at)


@app.patch("/sessions/{session_id}/title")
def rename_session(session_id: str, body: dict):
    title = str(body.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="title cannot be empty")
    _sessions_conn.execute(
        "UPDATE sessions SET title = ? WHERE session_id = ?", (title, session_id)
    )
    _sessions_conn.commit()
    return {"ok": True}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    _sessions_conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    _sessions_conn.commit()
    return {"ok": True}


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Return serialised chat history so the frontend can restore it on reload."""
    config = {"configurable": {"thread_id": session_id}}
    state = await app.state.agent.aget_state(config)
    messages = state.values.get("messages", []) if state and state.values else []
    return {"messages": _serialize_messages(messages)}


# --- Long-term memory extraction ---

@app.post("/sessions/{session_id}/extract-memory")
async def extract_memory(session_id: str, body: dict):
    user_id: str = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    config = {"configurable": {"thread_id": session_id}}
    state = await app.state.agent.aget_state(config)
    messages = state.values.get("messages", []) if state and state.values else []
    count = await memory.extract_and_save(user_id, session_id, messages)
    return {"memories_saved": count}


# --- Main chat endpoint ---

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    start = time.time()

    if not _session_exists(req.session_id):
        title = req.message[:40] + ("..." if len(req.message) > 40 else "")
        _create_session_row(req.session_id, req.user_id, title)

    memory.save_obvious_facts(req.user_id, req.message, req.session_id)

    long_term_context = memory.format_context(req.user_id)

    config = {"configurable": {"thread_id": req.session_id}}

    # passs ONLY the new message — the checkpointer handles full history accumulation
    try:
        result = await app.state.agent.ainvoke(
            {
                "messages": [HumanMessage(content=req.message)],
                "long_term_context": long_term_context,
            },
            config=config,
        )
    except ChatGoogleGenerativeAIError as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            raise HTTPException(
                status_code=429,
                detail=(
                    "API quota is exhausted for the configured API key. "
                    "Wait for quota reset, enable billing, or use a different key/model."
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="The language model provider failed while processing the request.",
        ) from exc

    final_message = result["messages"][-1]

    return ChatResponse(
        reply=final_message.content,
        files=_extract_files(result),
        drive_query=_extract_query(result),
        latency_ms=round((time.time() - start) * 1000, 2),
    )
