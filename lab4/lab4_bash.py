"""Run: uv run python lab4_bash.py

Each run uses a fresh temporary copy of data/project/.
Run only trusted commands: setting cwd is not a sandbox.
Compare stdout and exit_code for the two commands.
"""

from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
if ROOT.name == "answers":
    ROOT = ROOT.parent
PROJECT = ROOT / "data" / "project"
TIMEOUT_SECONDS = 10


@contextmanager
def project_copy():
    """Yield a fresh project directory and remove it after the with block."""
    with TemporaryDirectory(prefix="lab4-") as directory:
        root = Path(directory) / "project"
        shutil.copytree(PROJECT, root)
        yield root


def output_text(value: bytes | str | None) -> str:
    """TimeoutExpired may contain bytes even with text=True, or None if empty.

    Normalize partial output to a string so it can be returned as JSON.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def run_bash(command: str, root: Path) -> dict:
    """TODO: Execute command, preserving normal output and timeout feedback.

    Use subprocess.run with shell=True, cwd=root, capture_output=True,
    text=True, timeout=TIMEOUT_SECONDS. Keep check=False so nonzero exits
    return stdout, stderr, and exit_code=result.returncode.
    Catch subprocess.TimeoutExpired. Return stdout=output_text(error.stdout),
    stderr=output_text(error.stderr), exit_code=None, and an error explaining
    the timeout and suggesting inspection of partial output before retrying.
    """

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired as error:
        return {
            "stdout": output_text(error.stdout),
            "stderr": output_text(error.stderr),
            "exit_code": None,
            "error": (
                f"Command timed out after {TIMEOUT_SECONDS} seconds. "
                "Inspect partial output before retrying.",
            ),
        }


def main() -> None:
    with project_copy() as root:
        for command in ("python budget.py", "python missing.py"):
            print(f"Command: {command}")
            print(json.dumps(run_bash(command, root), indent=2))


if __name__ == "__main__":
    main()
