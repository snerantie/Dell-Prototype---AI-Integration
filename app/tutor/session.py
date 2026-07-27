"""In-memory conversation state.

A real deployment would back this with Redis (USSD sessions are short-lived;
WhatsApp conversations persist), but the interface is small so swapping the
store later is trivial. State is keyed by (channel, user_id).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.models.schemas import Channel, Diagnosis


class Stage(str, Enum):
    NEW = "new"
    CHOOSE_LANGUAGE = "choose_language"
    CHOOSE_SUBJECT = "choose_subject"
    AWAIT_PROBLEM = "await_problem"
    AWAIT_WORKING = "await_working"
    TUTORING = "tutoring"
    FREE_FORM = "free_form"


@dataclass
class ConversationState:
    user_id: str
    channel: Channel
    language: str = "en"
    grade: str = "9"
    stage: Stage = Stage.NEW
    subject: Optional[str] = None
    problem: Optional[str] = None
    working_steps: list[str] = field(default_factory=list)
    last_diagnosis: Optional[Diagnosis] = None
    hint_level: int = 0
    history: list[str] = field(default_factory=list)
    past_paper_id: Optional[str] = None   # e.g. "2026_jun_nw:p1:1.1.1"
    past_paper_attempts: int = 0
    # Multi-turn conversation history for the Ask-me-anything path, so
    # follow-up questions ("is that the full solution?", "explain step 3
    # again", "what about the other root?") reach the LLM WITH context.
    # Structure matches the OpenAI chat-completions format directly —
    # every entry is {"role": "user"|"assistant", "content": <text>}.
    # Cleared on Main-menu / mode-switch transitions so a new topic
    # starts fresh; capped to the most recent CHAT_HISTORY_MAX messages
    # to keep prompt cost + latency predictable.
    chat_history: list[dict] = field(default_factory=list)
    # Free-form ("Ask AI") pagination state for USSD. WhatsApp doesn't need
    # this because it can deliver the whole answer in one message, but USSD
    # replies are ~160 chars, so we cache the chunked LLM answer and walk an
    # index across screens. Fields are new + optional (default factories) so
    # existing WhatsApp sessions are unaffected.
    free_form_chunks: list[str] = field(default_factory=list)
    free_form_idx: int = 0
    updated_at: float = field(default_factory=time.time)

    def reset_problem(self) -> None:
        self.problem = None
        self.working_steps = []
        self.last_diagnosis = None
        self.hint_level = 0

    def reset_chat_history(self) -> None:
        """Clear multi-turn conversation history. Called on every top-level
        menu navigation (Main menu / Practice / Solve / Ask me anything)
        so a new topic doesn't inherit context from the previous one."""
        self.chat_history = []



class SessionStore:
    """Thread-safe in-memory session map with lazy TTL expiry."""

    def __init__(self, ttl_seconds: int = 3600):
        self._data: dict[str, ConversationState] = {}
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    @staticmethod
    def _key(channel: Channel, user_id: str) -> str:
        return f"{channel.value}:{user_id}"

    def get_or_create(self, channel: Channel, user_id: str) -> ConversationState:
        key = self._key(channel, user_id)
        with self._lock:
            state = self._data.get(key)
            if state is not None and (time.time() - state.updated_at) > self._ttl:
                state = None
            if state is None:
                state = ConversationState(user_id=user_id, channel=channel)
                self._data[key] = state
            return state

    def save(self, state: ConversationState) -> None:
        state.updated_at = time.time()
        with self._lock:
            self._data[self._key(state.channel, state.user_id)] = state

    def clear(self, channel: Channel, user_id: str) -> None:
        with self._lock:
            self._data.pop(self._key(channel, user_id), None)
