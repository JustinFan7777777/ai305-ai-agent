"""Starter agent: working chat before tools are introduced."""

from __future__ import annotations

from collections.abc import Sequence

from pilab_support.display import Display
from pilab_support.llm import ModelBackend
from pilab_support.messages import Message, UserMessage
from pilab_support.results import RunResult


class Agent:
    """A usable chat client that assignments will evolve into an agent."""

    def __init__(
        self,
        backend: ModelBackend,
        system_prompt: str,
        *,
        messages: Sequence[Message] = (),
    ) -> None:
        self.backend = backend
        self.system_prompt = system_prompt
        self.messages = list(messages)
        self.display = Display()

    def run(self, prompt: str) -> RunResult:
        """Perform one model turn; coursework extends this into a tool loop."""
        self.messages.append(UserMessage(content=prompt))
        try:
            assistant = self.backend.complete(self.messages, [], self.system_prompt)
        except Exception as error:
            return RunResult(status="error", model_calls=1, error=f"{type(error).__name__}: {error}")
        self.messages.append(assistant)
        return RunResult(answer=assistant.content, model_calls=1)

    def compact(self) -> str:
        """Keep the supplied TUI stable until context compaction is assigned."""
        return "Compaction is not implemented in the starter."

    def clear(self) -> None:
        self.messages = []
