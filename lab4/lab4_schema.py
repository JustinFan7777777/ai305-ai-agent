"""Run: uv run python lab4_schema.py

Complete read_tool, write_tool, and validate_call.
Observe default arguments, the rejected limit, and next_offset for pagination.
File operations use a temporary project copy.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from lab4_bash import project_copy


class BashArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, description="Non-interactive shell command to execute.")


class ReadArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, description="File path relative to the workspace.")
    offset: int = Field(default=1, ge=1, description="First line to read, starting at 1.")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of lines to return.")


class WriteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, description="File path relative to the workspace.")
    content: str = Field(description="Complete replacement content, not a patch.")


ARGUMENT_MODELS = {"bash": BashArguments, "read": ReadArguments, "write": WriteArguments}


def bash_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a non-interactive command in the workspace using the system shell, with a fixed 10-second timeout. Returns stdout, stderr, and exit_code; on timeout, returns partial output, exit_code=null, and an error. Inspect stderr or partial output before retrying. Use read for files and write for file changes.",
            "parameters": BashArguments.model_json_schema(),
        },
    }


def read_tool() -> dict:
    """TODO: Define the read function tool and describe how to continue reading.

    ReadArguments above defines path, offset, limit, and their defaults.
    Set function.parameters to ReadArguments.model_json_schema().
    Explain 1-based offsets and next_offset in the description. Do not add API strict.
    """
    return {
        "type": "function",
        "function": {"name": "read", "description": ..., "parameters": ...},
    }


def write_tool() -> dict:
    """TODO: Define the write function tool and describe full-file replacement.

    WriteArguments above defines the required path and content fields.
    Set function.parameters to WriteArguments.model_json_schema().
    Explain that missing parents are created, existing files are overwritten,
    and empty content clears a file. Describe the path and bytes_written result.
    Tell the model to read the full original before rewriting. Do not add API strict.
    """
    return {
        "type": "function",
        "function": {"name": "write", "description": ..., "parameters": ...},
    }


def validate_call(call: dict) -> dict:
    """TODO: Parse and validate the arguments for a known tool.

    call["function"] contains name and a JSON string arguments.
    Select the class with ARGUMENT_MODELS.get(name); raise ValueError if
    missing. Call model.model_validate_json(call["function"]["arguments"]).
    Return the validated object's model_dump() dict, including defaults.
    Let Pydantic ValidationError reach dispatch; do not execute invalid calls.
    """
    raise NotImplementedError


def resolve_file(root: Path, path: str) -> Path:
    """Resolve a workspace-relative path; reject paths outside root."""
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Path must stay inside the workspace; use a workspace-relative path.")
    return target


def read_file(path: str, root: Path, offset: int = 1, limit: int = 50) -> dict:
    target = resolve_file(root, path)
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    total = len(lines)
    if offset > max(total, 1):
        raise ValueError(f"Offset {offset} exceeds {total} lines in {path}. Restart at offset=1 or use an earlier returned next_offset.")
    start = offset - 1
    end = min(start + limit, total)
    return {
        "path": path,
        "content": "".join(lines[start:end]),
        "start_line": offset if total else 0,
        "end_line": end,
        "total_lines": total,
        "next_offset": end + 1 if end < total else None,
    }


def write_file(path: str, content: str, root: Path) -> dict:
    target = resolve_file(root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "bytes_written": len(content.encode("utf-8"))}


def build_tools() -> list[dict]:
    return [bash_tool(), read_tool(), write_tool()]


def main() -> None:
    print("=== Tool definitions ===")
    print(json.dumps([read_tool(), write_tool()], indent=2))
    print("\n=== Argument validation: defaults and limits ===")
    print("Omitted offset/limit become 1/50; limit=201 must be rejected.")
    for raw in ('{"path": "budget.py"}', '{"path": "budget.py", "limit": 201}'):
        print("Arguments:", raw)
        try:
            print("Accepted:", validate_call({"function": {"name": "read", "arguments": raw}}))
        except ValueError as error:
            print("Rejected:", error)
    with project_copy() as root:
        print("\n=== Pagination: use next_offset until it is null ===")
        print("Create:", write_file("notes/demo.txt", "first\nsecond\nthird\n", root))
        offset = 1
        while offset is not None:
            page = read_file("notes/demo.txt", root, offset=offset, limit=2)
            print("Page:", page)
            offset = page["next_offset"]
        print("\n=== Write: replace the entire file ===")
        print("Overwrite:", write_file("notes/demo.txt", "replacement\n", root))
        print("Read after overwrite:", read_file("notes/demo.txt", root))


if __name__ == "__main__":
    main()
