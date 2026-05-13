"""
Long-term memory module for TailorTalk.

Architecture:
- Per-user memories are stored in a local SQLite database (backend/data/long_term_memory.db).
- At the end of each session (or on demand via POST /sessions/{id}/extract-memory),
  key facts are extracted by the LLM and stored as discrete entries.
- On every new turn, stored memories are injected into the system prompt so the
  LLM is aware of the user's history across ALL past sessions.

Upgrade path:
  Swap the SQLite row store for a vector database (ChromaDB, Qdrant, pgvector)
  to enable semantic similarity search over memories instead of simple
  recency-based retrieval.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from backend.agent.llm import create_chat_model

logger = logging.getLogger("tailortalk.memory")

_NAME_PATTERNS = [
    re.compile(r"\bmy name is\s+([A-Z][A-Za-z .'-]{1,60})", re.IGNORECASE),
    re.compile(r"\bi am\s+([A-Z][A-Za-z .'-]{1,60})", re.IGNORECASE),
    re.compile(r"\bi'm\s+([A-Z][A-Za-z .'-]{1,60})", re.IGNORECASE),
]

# storage path
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(DATA_DIR, exist_ok=True)
MEMORY_DB_PATH = os.path.join(DATA_DIR, "long_term_memory.db")


# prompt for fact extraction

_EXTRACTION_PROMPT = """You are a memory extractor for a Google Drive search assistant.

From the conversation below, extract 1-5 short, specific, reusable facts about:
  - The user's name or how they refer to themselves
  - Explicit user preferences that should carry across chats
  - Files or folders the user frequently searches for
  - File types, date ranges, or keywords they favour
  - Project names, team names, or recurring topics

Rules:
  - Each fact must be a single concise sentence.
  - Only include stable facts that would help future conversations or searches.
  - If nothing useful can be extracted, return exactly: NONE

Conversation:
{conversation}

Facts (one per line, no bullets or numbering):"""


class LongTermMemory:
    def __init__(self, db_path: str = MEMORY_DB_PATH) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        self._llm = None


    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_memories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                session_id  TEXT,
                memory      TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_user_memories_uid
                ON user_memories (user_id);
        """)
        self._conn.commit()

    # lazy init
    @property
    def llm(self):
        if self._llm is None:
            self._llm = create_chat_model()
        return self._llm

    def save_memory(
        self,
        user_id: str,
        memory_text: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Persist a single memory entry for a user."""
        self._conn.execute(
            "INSERT INTO user_memories (user_id, session_id, memory, created_at) VALUES (?, ?, ?, ?)",
            (user_id, session_id, memory_text.strip(), datetime.utcnow().isoformat()),
        )
        self._conn.commit()
        logger.info("Saved memory for user=%s: %.60s", user_id, memory_text)

    def save_obvious_facts(
        self,
        user_id: str,
        text: str,
        session_id: Optional[str] = None,
    ) -> int:
        """Persist deterministic facts that should be remembered immediately."""
        saved = 0
        for pattern in _NAME_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            name = match.group(1).strip(" .")
            if name:
                self.save_memory(user_id, f"The user's name is {name}.", session_id)
                saved += 1
                break
        return saved

    def delete_user_memories(self, user_id: str) -> None:
        """Remove all memories for a user (GDPR / reset)."""
        self._conn.execute("DELETE FROM user_memories WHERE user_id = ?", (user_id,))
        self._conn.commit()


    def get_memories(self, user_id: str, limit: int = 10) -> List[str]:
        """Return the most recent *limit* memories for a user."""
        cur = self._conn.execute(
            "SELECT memory FROM user_memories WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [row[0] for row in cur.fetchall()]

    def count_memories(self, user_id: str) -> int:
        """Return the number of stored memories for a user."""
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM user_memories WHERE user_id = ?",
            (user_id,),
        )
        return int(cur.fetchone()[0])

    def format_context(self, user_id: str) -> str:
        """
        Format memories as a context block ready to be appended to the system prompt.
        Returns an empty string when the user has no memories yet.
        """
        memories = self.get_memories(user_id)
        if not memories:
            return ""
        lines = "\n".join(f"- {m}" for m in memories)
        return f"## Memory from past conversations:\n{lines}"

   
    # LLM-based extraction  (call when a session ends)
    async def extract_and_save(
        self,
        user_id: str,
        session_id: str,
        messages: List[BaseMessage],
    ) -> int:
        """
        Use the LLM to extract key facts from a conversation and persist them.
        Returns the number of memories saved.
        """
        if not messages:
            return 0

        turns: List[str] = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                turns.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage) and msg.content:
                turns.append(f"Assistant: {msg.content}")

        if not turns:
            return 0

        conversation = "\n".join(turns)
        prompt = _EXTRACTION_PROMPT.format(conversation=conversation)

        try:
            response = await self.llm.ainvoke(prompt)
            raw: str = response.content.strip()
        except Exception as exc:
            logger.error("Memory extraction LLM call failed: %s", exc)
            return 0

        if not raw or raw.upper() == "NONE":
            return 0

        count = 0
        for line in raw.splitlines():
            fact = line.strip().lstrip("-•1234567890. ").strip()
            if fact:
                self.save_memory(user_id, fact, session_id)
                count += 1

        logger.info(
            "Extracted %d memories from session=%s for user=%s",
            count, session_id, user_id,
        )
        return count


memory = LongTermMemory()
