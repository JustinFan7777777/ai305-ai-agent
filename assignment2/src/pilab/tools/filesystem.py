"""Paged reads and complete-file writes in the selected workspace."""

import json
from pathlib import Path

from pydantic import Field

from pilab.tools.base import Tool, ToolArguments


class ReadArguments(ToolArguments):
    path: str = Field(min_length=1, description="Path to a UTF-8 file in the workspace")
    offset: int = Field(default=1, ge=1, description="First line to read, starting at 1")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of lines to return")


class WriteArguments(ToolArguments):
    path: str = Field(min_length=1, description="File path relative to the workspace")
    content: str = Field(
        description="Complete replacement content, not a patch; empty content clears the file"
    )


def resolve_file(workspace: Path, path: str) -> Path:
    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace.resolve()):
        raise ValueError("Path must stay inside the workspace; use a workspace-relative path.")
    return target


class ReadTool(Tool):
    name = "read"
    description = (
        "Read a UTF-8 workspace file by lines. offset starts at 1; limit defaults to 50, at most 200. "
        "Returns content, line counts, and next_offset. If next_offset is not null, use it as offset "
        "to continue. Read the complete original before rewriting a file."
    )
    arguments_type = ReadArguments

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def execute(self, arguments: ReadArguments) -> str:
        path = resolve_file(self.workspace, arguments.path)
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        total = len(lines)
        if arguments.offset > max(total, 1):
            raise ValueError(
                f"Offset {arguments.offset} exceeds {total} lines. "
                "Restart at offset=1 or use an earlier returned next_offset."
            )
        start = arguments.offset - 1
        end = min(start + arguments.limit, total)
        return json.dumps(
            {
                "path": arguments.path,
                "content": "".join(lines[start:end]),
                "start_line": arguments.offset if total else 0,
                "end_line": end,
                "total_lines": total,
                "next_offset": end + 1 if end < total else None,
            }
        )


class WriteTool(Tool):
    name = "write"
    description = (
        "Write complete UTF-8 content to a workspace file, creating missing parent directories. "
        "Replaces all existing content; empty content clears the file. Read the full original "
        "before changing it and send the complete new file, not only changed lines. "
        "Returns path and bytes_written. A successful write does not verify correctness."
    )
    arguments_type = WriteArguments

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def execute(self, arguments: WriteArguments) -> str:
        path = resolve_file(self.workspace, arguments.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments.content, encoding="utf-8")
        return json.dumps({"path": arguments.path, "bytes_written": len(arguments.content.encode("utf-8"))})
