"""Coding agent with a small, validated tool set and a bounded ReAct loop."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, TypeAlias

from pilab_support.display import Display
from pilab_support.execution.sandbox import Sandbox
from pilab_support.llm import ModelBackend
from pilab_support.messages import AssistantMessage, Message, ToolCall, ToolMessage, UserMessage
from pilab_support.results import RunResult
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ToolArguments(BaseModel):
    """Common strict configuration for every tool argument model.

    ``extra='forbid'`` is deliberate: silently ignoring an argument generated
    by the model would make a tool call appear successful when it was not
    understood. Strict validation also keeps the execution boundary explicit.
    """

    model_config = ConfigDict(extra="forbid", strict=True)


class ReadFileArguments(ToolArguments):
    """Arguments accepted by the read_file tool."""

    path: str = Field(min_length=1)


class WriteFileArguments(ToolArguments):
    """Arguments accepted by the write_file tool."""

    path: str = Field(min_length=1)
    content: str


class RunCommandArguments(ToolArguments):
    """Arguments accepted by the run_command tool."""

    command: str = Field(min_length=1)
    timeout: float = Field(default=10.0, ge=0.1, le=30.0)


ToolArgumentModel: TypeAlias = (
    type[ReadFileArguments] | type[WriteFileArguments] | type[RunCommandArguments]
)


# These schemas are sent to the model through the standard function-tool
# protocol. The model chooses a tool, while the Agent remains responsible for
# validating and executing the resulting arguments locally.
TOOL_DEFINITIONS: Final[list[dict[str, object]]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the current workspace.",
            "parameters": ReadFileArguments.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write UTF-8 text to a file inside the current workspace. "
                "Parent directories are created automatically."
            ),
            "parameters": WriteFileArguments.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run one non-interactive Bash command in the current workspace. "
                "Use it to test or inspect the project after editing it."
            ),
            "parameters": RunCommandArguments.model_json_schema(),
        },
    },
]


TOOL_ARGUMENT_MODELS: Final[dict[str, ToolArgumentModel]] = {
    "read_file": ReadFileArguments,
    "write_file": WriteFileArguments,
    "run_command": RunCommandArguments,
}


class Agent:
    """A usable chat client extended with validated workspace tools."""

    def __init__(
        self,
        backend: ModelBackend,
        system_prompt: str,
        *,
        messages: Sequence[Message] = (),
        sandbox: Sandbox | None = None,
        max_turns: int = 12,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be positive")

        self.backend = backend
        self.system_prompt = system_prompt
        self.messages = list(messages)
        self.display = Display()
        # Keeping this optional preserves the starter Agent's original
        # constructor behavior for callers that only need ordinary chat.
        self.sandbox = sandbox
        self.max_turns = max_turns

    def run(self, prompt: str) -> RunResult:
        """Perform model turns and tool executions until the task is complete.

        Each iteration follows the ReAct pattern: the model observes the
        conversation, reasons about the next action, requests a tool, receives
        an observation, and then gets another model turn. Tool failures are
        represented as ToolMessage objects so the model can recover instead of
        losing the whole run to an exception.
        """

        self.messages.append(UserMessage(content=prompt))
        model_calls = 0
        tool_calls = 0
        seen_call_ids: set[str] = set()

        for _ in range(self.max_turns):
            model_calls += 1
            try:
                assistant = self.backend.complete(
                    self.messages,
                    TOOL_DEFINITIONS,
                    self.system_prompt,
                )
            except Exception as error:
                return RunResult(
                    status="error",
                    model_calls=model_calls,
                    tool_calls=tool_calls,
                    error=f"{type(error).__name__}: {error}",
                )

            self.messages.append(assistant)
            self.display.assistant(assistant)

            # An assistant response without tool calls is the normal stopping
            # condition and preserves the starter's answer behavior.
            if not assistant.tool_calls:
                return RunResult(
                    answer=assistant.content,
                    model_calls=model_calls,
                    tool_calls=tool_calls,
                )

            for call in assistant.tool_calls:
                tool_calls += 1
                self.display.tool_call(call)

                # A duplicate ID would make it impossible to associate a
                # later observation with exactly one model request.
                if call.id in seen_call_ids:
                    result = ToolMessage(
                        tool_call_id=call.id,
                        name=call.name,
                        content=f"Duplicate tool call id: {call.id}",
                        is_error=True,
                    )
                    self.messages.append(result)
                    self.display.tool_result(result)
                    return RunResult(
                        answer=assistant.content,
                        status="repeated_call",
                        model_calls=model_calls,
                        tool_calls=tool_calls,
                        error=f"Duplicate tool call id: {call.id}",
                    )

                seen_call_ids.add(call.id)
                result = self._dispatch(call)
                self.messages.append(result)
                self.display.tool_result(result)

        return RunResult(
            answer=self._last_assistant_content(),
            status="max_turns",
            model_calls=model_calls,
            tool_calls=tool_calls,
            error=f"Maximum model turns reached: {self.max_turns}",
        )

    def _dispatch(self, call: ToolCall) -> ToolMessage:
        """Validate and execute one tool, returning all failures as feedback."""

        model = TOOL_ARGUMENT_MODELS.get(call.name)
        if model is None:
            return ToolMessage(
                tool_call_id=call.id,
                name=call.name,
                content=f"Unknown tool: {call.name}",
                is_error=True,
            )

        try:
            arguments = model.model_validate(call.arguments)
        except ValidationError as error:
            return ToolMessage(
                tool_call_id=call.id,
                name=call.name,
                content=f"Invalid arguments for {call.name}: {error}",
                is_error=True,
            )

        if self.sandbox is None:
            return ToolMessage(
                tool_call_id=call.id,
                name=call.name,
                content="No workspace sandbox is configured.",
                is_error=True,
            )

        try:
            if isinstance(arguments, ReadFileArguments):
                content = self.sandbox.read_text(arguments.path)
                return ToolMessage(
                    tool_call_id=call.id,
                    name=call.name,
                    content=content,
                )

            if isinstance(arguments, WriteFileArguments):
                self.sandbox.write_text(arguments.path, arguments.content)
                return ToolMessage(
                    tool_call_id=call.id,
                    name=call.name,
                    content=f"Wrote {len(arguments.content)} characters to {arguments.path}",
                )

            if isinstance(arguments, RunCommandArguments):
                command_result = self.sandbox.run(arguments.command, arguments.timeout)
                # A non-zero process exit is not a Python exception, but it is
                # still a failed tool action. Both metadata and readable text
                # are preserved for the evaluator and for the next model turn.
                return ToolMessage(
                    tool_call_id=call.id,
                    name=call.name,
                    content=f"exit_code={command_result.exit_code}\n{command_result.output}",
                    is_error=command_result.exit_code != 0,
                )
        except Exception as error:
            return ToolMessage(
                tool_call_id=call.id,
                name=call.name,
                content=f"{type(error).__name__}: {error}",
                is_error=True,
            )

        return ToolMessage(
            tool_call_id=call.id,
            name=call.name,
            content=f"Tool implementation is incomplete: {call.name}",
            is_error=True,
        )

    def _last_assistant_content(self) -> str:
        """Return the latest assistant text for max-turn reporting."""

        for message in reversed(self.messages):
            if isinstance(message, AssistantMessage):
                return message.content
        return ""

    def compact(self) -> str:
        """Keep recent, user-bounded messages when history grows large."""

        if len(self.messages) <= 10:
            return "Conversation is already compact."

        # Start at a user-message boundary whenever possible. This avoids
        # leaving the model with a ToolMessage whose matching assistant tool
        # request was discarded by the simple length-based trim.
        recent_start = max(0, len(self.messages) - 10)
        boundary = next(
            (
                index
                for index in range(recent_start, len(self.messages))
                if isinstance(self.messages[index], UserMessage)
            ),
            recent_start,
        )
        self.messages = self.messages[boundary:]
        return "Conversation history compacted to recent messages."

    def clear(self) -> None:
        self.messages = []
