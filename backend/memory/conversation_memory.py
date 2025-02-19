"""Multi-turn conversation context manager with optional Redis persistence."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from backend.shared.models import ChatMessage, ConversationContext

logger = logging.getLogger("omnirag.memory.conversation")

MAX_CONTEXT_MESSAGES = 20  # Sliding window


class ConversationMemory:
    """Store and retrieve conversation history, supporting Redis for persistence."""

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client
        self._local: dict[str, ConversationContext] = {}
        self._ttl_seconds = 86400  # 24h

    def create_conversation(self, doc_ids: Optional[list[str]] = None) -> ConversationContext:
        """Create a new conversation context."""
        ctx = ConversationContext(
            conversation_id=str(uuid4()),
            doc_ids=doc_ids or [],
        )
        self._persist(ctx)
        logger.info(f"Created conversation: {ctx.conversation_id}")
        return ctx

    def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        """Retrieve conversation by ID from Redis or local cache."""
        # Check local cache first
        if conversation_id in self._local:
            return self._local[conversation_id]

        if self._redis:
            raw = self._redis.get(f"conv:{conversation_id}")
            if raw:
                data = json.loads(raw)
                ctx = ConversationContext(**data)
                self._local[conversation_id] = ctx
                return ctx

        return None

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> Optional[ConversationContext]:
        """Append a message to a conversation, applying sliding window."""
        ctx = self.get_conversation(conversation_id)
        if ctx is None:
            logger.warning(f"Conversation not found: {conversation_id}")
            return None

        msg = ChatMessage(role=role, content=content)
        ctx.messages.append(msg)

        # Enforce sliding window
        if len(ctx.messages) > MAX_CONTEXT_MESSAGES:
            # Keep system messages + recent turns
            system_msgs = [m for m in ctx.messages if m.role == "system"]
            other_msgs = [m for m in ctx.messages if m.role != "system"]
            ctx.messages = system_msgs + other_msgs[-(MAX_CONTEXT_MESSAGES - len(system_msgs)):]

        ctx.updated_at = datetime.utcnow()
        self._persist(ctx)
        return ctx

    def get_context_window(self, conversation_id: str) -> list[dict[str, str]]:
        """Return messages formatted for LLM API consumption."""
        ctx = self.get_conversation(conversation_id)
        if not ctx:
            return []
        return [{"role": m.role, "content": m.content} for m in ctx.messages]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Remove a conversation from storage."""
        self._local.pop(conversation_id, None)
        if self._redis:
            deleted = self._redis.delete(f"conv:{conversation_id}")
            return bool(deleted)
        return True

    def list_conversations(self) -> list[str]:
        """Return all conversation IDs in local cache."""
        return list(self._local.keys())

    def _persist(self, ctx: ConversationContext) -> None:
        """Save to local cache and optionally Redis."""
        self._local[ctx.conversation_id] = ctx
        if self._redis:
            try:
                serialized = ctx.model_dump_json()
                self._redis.setex(
                    f"conv:{ctx.conversation_id}",
                    self._ttl_seconds,
                    serialized,
                )
            except Exception as e:
                logger.warning(f"Redis persist failed: {e}")
