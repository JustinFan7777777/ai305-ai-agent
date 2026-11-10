"""Run a Bash command in the selected workspace."""

import json
import subprocess
from pathlib import Path

from pydantic import Field

from pilab.tools.base import Tool, ToolArguments, ToolOutput

TIMEOUT_SECONDS = 10


def output_text(value: bytes | str | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


class BashArguments(ToolArguments):
    command: str = Field(min_length=1, description="Bash command to execute in the workspace")


class BashTool(Tool):
    name = "bash"
    description = (
        "Run a non-interactive Bash command in the workspace with a fixed 10-second timeout. "
        "Returns stdout, stderr, and exit_code. On timeout, returns partial output, exit_code=null, "
        "and an error. Inspect stderr or partial output before retrying. Use read for files and "
        "write for file changes; run commands to verify the result."
    )
    arguments_type = BashArguments

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def execute(self, arguments: BashArguments) -> ToolOutput:
        try:
            result = subprocess.run(
                ["/bin/bash", "-c", arguments.command],
                cwd=self.workspace,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return ToolOutput(
                content=json.dumps(
                    {
                        "stdout": output_text(error.stdout),
                        "stderr": output_text(error.stderr),
                        "exit_code": None,
                        "error": f"Command timed out after {TIMEOUT_SECONDS} seconds. "
                        "Inspect partial output; retry a shorter command.",
                    }
                ),
                is_error=True,
            )
        return ToolOutput(
            content=json.dumps(
                {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                }
            ),
            is_error=result.returncode != 0,
        )
