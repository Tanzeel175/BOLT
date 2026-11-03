"""
Continuous Conversation Mode State Machine for BOLT (Phase 7).
Enables multi-turn conversational interactions without repeating the wake phrase.
Includes turn-taking, follow-up timeouts, approval handling, and standby transitions.
"""

import enum
import time
from typing import Any, Callable, Dict, Optional
from bolt.core.logger import get_logger

logger = get_logger("ConversationMode")


class ConversationState(enum.Enum):
    IDLE = "IDLE"
    ACTIVE_LISTENING = "ACTIVE_LISTENING"
    EXECUTING = "EXECUTING"
    AWAITING_FOLLOW_UP = "AWAITING_FOLLOW_UP"
    WAITING_APPROVAL = "WAITING_APPROVAL"


class ConversationSession:
    """
    Manages conversational session state, follow-up window timeout,
    and voice dialogue flow.
    """

    def __init__(self, follow_up_timeout: float = 8.0):
        self.follow_up_timeout = follow_up_timeout
        self.state = ConversationState.IDLE
        self.last_active_time = time.time()
        self.pending_approval_task_id: Optional[str] = None
        self.current_context: Dict[str, Any] = {}

    @property
    def is_in_conversation(self) -> bool:
        """True if the conversation session is currently active and awaiting follow-up or command."""
        if self.state in (ConversationState.ACTIVE_LISTENING, ConversationState.AWAITING_FOLLOW_UP, ConversationState.WAITING_APPROVAL):
            # Check for expiration
            if time.time() - self.last_active_time > self.follow_up_timeout:
                logger.info("Follow-up conversation window timed out. Returning to IDLE.")
                self.state = ConversationState.IDLE
                return False
            return True
        return False

    def trigger_wake_phrase(self) -> str:
        """User said 'Hey Bolt'. Transition to ACTIVE_LISTENING and return greeting."""
        self.state = ConversationState.ACTIVE_LISTENING
        self.last_active_time = time.time()
        logger.info("Conversation activated by wake phrase.")
        return "I'm listening."

    def start_execution(self, command: str) -> None:
        """Mark start of task execution."""
        self.state = ConversationState.EXECUTING
        self.last_active_time = time.time()
        self.current_context["last_command"] = command

    def complete_execution(self, spoken_response: str) -> None:
        """Mark task completion and open follow-up listening window."""
        self.state = ConversationState.AWAITING_FOLLOW_UP
        self.last_active_time = time.time()
        self.current_context["last_response"] = spoken_response
        logger.info(f"Execution complete. Awaiting follow-up commands ({self.follow_up_timeout}s timeout).")

    def enter_approval_state(self, prompt: str, task_id: Optional[str] = None, is_critical: bool = False) -> str:
        """Encountered a sensitive action requiring explicit user approval."""
        self.state = ConversationState.WAITING_APPROVAL
        self.pending_approval_task_id = task_id
        self.last_active_time = time.time()
        logger.info(f"Voice approval state entered for task: {task_id} (critical={is_critical})")
        if is_critical:
            return f"Critical action detected: {prompt}. For security, this cannot be authorized by voice. Please type CONFIRM on the screen."
        return f"This action requires your approval: {prompt}. Do you approve?"

    def handle_approval_response(self, user_text: str) -> Optional[bool]:
        """Evaluate if user text represents approval or rejection."""
        lower = user_text.strip().lower()
        if lower in ["yes", "approve", "approved", "proceed", "sure", "ok", "i approve", "go ahead", "allow session", "approve session"]:
            self.state = ConversationState.EXECUTING
            self.last_active_time = time.time()
            return True
        elif lower in ["no", "reject", "cancel", "stop", "abort", "don't do it"]:
            self.state = ConversationState.IDLE
            self.last_active_time = time.time()
            return False
        return None

    def close_session(self) -> None:
        """Explicitly end conversational session."""
        self.state = ConversationState.IDLE
        self.current_context.clear()
        self.pending_approval_task_id = None
        logger.info("Conversation session ended.")


_CONVERSATION_SESSION_INSTANCE: Optional[ConversationSession] = None


def get_conversation_session() -> ConversationSession:
    global _CONVERSATION_SESSION_INSTANCE
    if _CONVERSATION_SESSION_INSTANCE is None:
        _CONVERSATION_SESSION_INSTANCE = ConversationSession()
    return _CONVERSATION_SESSION_INSTANCE

