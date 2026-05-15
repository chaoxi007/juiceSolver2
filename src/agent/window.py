from __future__ import annotations

from ..llm.base import LLMMessage


class ConversationWindow:
    """Sliding window that retains only the most recent K turns of conversation.

    Each 'turn' is a pair of (assistant_message, user_result_message).
    Older turns are dropped once the window is full — their key facts
    have already been absorbed into WorkingMemory.
    """

    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self._turns: list[tuple[LLMMessage, LLMMessage]] = []

    def append(self, assistant_msg: LLMMessage, result_msg: LLMMessage) -> None:
        """Add a turn and trim the window if it exceeds max_turns."""
        self._turns.append((assistant_msg, result_msg))
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns:]

    def get_messages(self) -> list[LLMMessage]:
        """Return all messages in the window, in chronological order."""
        messages: list[LLMMessage] = []
        for assistant_msg, result_msg in self._turns:
            messages.append(assistant_msg)
            messages.append(result_msg)
        return messages

    @property
    def size(self) -> int:
        """Number of turns currently in the window."""
        return len(self._turns)

    def clear(self) -> None:
        self._turns.clear()
