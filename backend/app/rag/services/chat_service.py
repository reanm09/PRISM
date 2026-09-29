from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.database import supabase
from app.rag.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
)

logger = logging.getLogger(__name__)

# In-memory store fallback if Supabase tables chat_sessions / chat_messages are not yet created
_MEM_SESSIONS: Dict[str, Dict[str, Any]] = {}
_MEM_MESSAGES: List[Dict[str, Any]] = []


class ChatService:
    """
    Manages chat sessions and conversation history for authenticated Supabase users.
    Persists to Supabase `chat_sessions` and `chat_messages` tables with fallback.
    """

    def __init__(self, client=None):
        self.client = client or supabase

    def create_session(self, user_id: str, title: Optional[str] = "New Investigation Chat") -> ChatSessionResponse:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        clean_title = title or "New Investigation Chat"

        try:
            res = self.client.table("chat_sessions").insert({
                "id": session_id,
                "user_id": user_id,
                "title": clean_title,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }).execute()

            if res.data:
                row = res.data[0]
                return ChatSessionResponse(
                    id=str(row["id"]),
                    user_id=str(row["user_id"]),
                    title=row["title"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
        except Exception as exc:
            logger.info("Using in-memory session persistence (Supabase chat_sessions table note: %s)", exc)

        # Fallback in-memory
        sess_data = {
            "id": session_id,
            "user_id": user_id,
            "title": clean_title,
            "created_at": now,
            "updated_at": now,
        }
        _MEM_SESSIONS[session_id] = sess_data
        return ChatSessionResponse(**sess_data)

    def list_sessions(self, user_id: str) -> List[ChatSessionResponse]:
        try:
            res = self.client.table("chat_sessions").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
            if res.data:
                return [
                    ChatSessionResponse(
                        id=str(r["id"]),
                        user_id=str(r["user_id"]),
                        title=r["title"],
                        created_at=datetime.fromisoformat(r["created_at"]),
                        updated_at=datetime.fromisoformat(r["updated_at"]),
                    )
                    for r in res.data
                ]
        except Exception as exc:
            logger.debug("Falling back to in-memory sessions: %s", exc)

        user_sessions = [
            ChatSessionResponse(**s) for s in _MEM_SESSIONS.values() if s["user_id"] == user_id
        ]
        user_sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return user_sessions

    def add_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        retrieval_metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatMessageResponse:
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        meta = retrieval_metadata or {}

        try:
            res = self.client.table("chat_messages").insert({
                "id": msg_id,
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "retrieval_metadata": meta,
                "created_at": now.isoformat(),
            }).execute()

            if res.data:
                row = res.data[0]
                return ChatMessageResponse(
                    id=str(row["id"]),
                    session_id=str(row["session_id"]),
                    user_id=str(row["user_id"]),
                    role=row["role"],
                    content=row["content"],
                    retrieval_metadata=row.get("retrieval_metadata") or {},
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
        except Exception as exc:
            logger.debug("Falling back to in-memory messages: %s", exc)

        msg_data = {
            "id": msg_id,
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "retrieval_metadata": meta,
            "created_at": now,
        }
        _MEM_MESSAGES.append(msg_data)
        return ChatMessageResponse(**msg_data)

    def get_messages(self, session_id: str, user_id: str) -> List[ChatMessageResponse]:
        try:
            res = self.client.table("chat_messages").select("*").eq("session_id", session_id).eq("user_id", user_id).order("created_at", desc=False).execute()
            if res.data:
                return [
                    ChatMessageResponse(
                        id=str(r["id"]),
                        session_id=str(r["session_id"]),
                        user_id=str(r["user_id"]),
                        role=r["role"],
                        content=r["content"],
                        retrieval_metadata=r.get("retrieval_metadata") or {},
                        created_at=datetime.fromisoformat(r["created_at"]),
                    )
                    for r in res.data
                ]
        except Exception as exc:
            logger.debug("Falling back to in-memory messages: %s", exc)

        return [
            ChatMessageResponse(**m)
            for m in _MEM_MESSAGES
            if m["session_id"] == session_id and m["user_id"] == user_id
        ]
