"""Append-only conversation records and compaction checkpoints."""

import json
from pathlib import Path

from pilab_support.messages import MESSAGE_ADAPTER, AssistantMessage, Message, ToolMessage


def validate_history(messages: list[Message]) -> None:
    """Reject incomplete, orphaned, or ambiguous tool batches without replaying them."""
    pending: dict[str, str] = {}
    seen: set[str] = set()
    for message in messages:
        if isinstance(message, ToolMessage):
            if pending.get(message.tool_call_id) != message.name:
                raise ValueError(f"Unmatched tool result: {message.tool_call_id}")
            del pending[message.tool_call_id]
            continue
        if pending:
            raise ValueError(f"Incomplete session; missing tool results: {sorted(pending)}")
        if isinstance(message, AssistantMessage):
            for call in message.tool_calls:
                if not call.id or call.id in seen:
                    raise ValueError(f"Duplicate or empty tool-call id: {call.id}")
                seen.add(call.id)
                pending[call.id] = call.name
    if pending:
        raise ValueError(f"Incomplete session; missing tool results: {sorted(pending)}")


class Session:
    """Restore active context while leaving all original JSONL records intact."""

    def __init__(self, path: Path, workspace: Path) -> None:
        self.path = path.resolve()
        self.workspace = workspace.resolve()
        self.messages: list[Message] = []
        self.records: list[Message] = []
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps({"type": "session", "version": 1, "cwd": str(self.workspace)}))
                stream.write("\n")
            return
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise ValueError("Session file is empty")
        header = json.loads(lines[0])
        if header.get("type") != "session" or header.get("version") != 1:
            raise ValueError("Unsupported session format")
        if header.get("cwd") != str(self.workspace):
            raise ValueError("Session belongs to another workspace")
        original: list[Message] = []
        for line in lines[1:]:
            record = json.loads(line)
            if record.get("type") == "message":
                message = MESSAGE_ADAPTER.validate_python(record["message"])
                original.append(message)
                self.messages.append(message)
            elif record.get("type") == "checkpoint":
                validate_history(original)
                retained = [MESSAGE_ADAPTER.validate_python(item) for item in record["retained"]]
                validate_history(retained)
                summary = record["summary"]
                if not isinstance(summary, str):
                    raise ValueError("Invalid checkpoint summary")
                summary_fields = {"timestamp": record["summary_timestamp"]}
                self.messages = ([AssistantMessage(content=summary, **summary_fields)] if summary else [])
                self.messages += retained
            elif record.get("type") == "clear":
                validate_history(original)
                self.messages = []
                original = []
            else:
                raise ValueError(f"Unknown session record: {record.get('type')}")
        validate_history(original)
        validate_history(self.messages)
        self.records = original

    def append(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def message(self, message: Message) -> None:
        self.append({"type": "message", "message": message.model_dump(mode="json")})

    def checkpoint(self, summary: AssistantMessage, retained: list[Message]) -> None:
        self.append({
            "type": "checkpoint",
            "summary": summary.content,
            "summary_timestamp": summary.model_dump(mode="json")["timestamp"],
            "retained": [message.model_dump(mode="json") for message in retained],
        })
