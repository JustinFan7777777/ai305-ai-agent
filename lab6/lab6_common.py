"""Shared model connection and tool helpers for Lab 6."""

import json
import os
import subprocess
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parent


def connect() -> tuple[OpenAI, str]:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise SystemExit("Set DASHSCOPE_API_KEY before running this exercise.")
    client = OpenAI(
        api_key=key,
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=60.0, max_retries=0,
    )
    return client, os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash")


def call_model(client, model: str, messages: list[dict], tools: list[dict] | None = None) -> dict:
    request = {
        "model": model,
        "messages": messages,
        "max_tokens": 1200,
        "extra_body": {"enable_thinking": False},
    }
    if tools:
        request.update(tools=tools, tool_choice="auto")
    completion = client.chat.completions.create(**request)
    choice = completion.choices[0]
    if choice.finish_reason not in {"stop", "tool_calls"}:
        raise RuntimeError(f"Incomplete model response: {choice.finish_reason}")
    return choice.message.model_dump(include={"role", "content", "tool_calls"}, exclude_none=True)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a UTF-8 text file. Paths are relative to the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Run a shell command in the working directory."
                " Return stdout, stderr, and exit_code, or partial output on timeout."
            ),
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]



def read_file(path: str, root: Path) -> str:
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Read a file inside the working directory.")
    return target.read_text(encoding="utf-8")


def output_text(value: bytes | str | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def run_bash(command: str, root: Path) -> dict:
    windows = os.name == "nt"
    args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command] if windows else command
    try:
        result = subprocess.run(
            args, shell=not windows, cwd=root,
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "stdout": output_text(error.stdout),
            "stderr": output_text(error.stderr),
            "exit_code": None,
            "error": "Command timed out after 10 seconds. Inspect partial output before retrying.",
        }
    return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


def dispatch(call: dict, root: Path) -> dict:
    try:
        arguments = json.loads(call["function"]["arguments"])
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object.")
        name = call["function"]["name"]
        if name == "read" and isinstance(arguments.get("path"), str):
            print("READ:", arguments["path"])
            content = read_file(arguments["path"], root)
        elif name == "bash" and isinstance(arguments.get("command"), str):
            print("RUN:", arguments["command"])
            result = run_bash(arguments["command"], root)
            print(f"\nSCRIPT RESULT (exit_code={result['exit_code']}):")
            if result["stdout"]:
                print(result["stdout"].rstrip())
            if result["stderr"]:
                print("STDERR:", result["stderr"].rstrip())
            if result.get("error"):
                print("ERROR:", result["error"])
            content = json.dumps(result, ensure_ascii=False)
        else:
            raise ValueError("Use read with a path or bash with a command.")
    except (ValueError, OSError) as error:
        content = f"Tool failed: {error}"
        print("ERROR:", content)
    return {"role": "tool", "tool_call_id": call["id"], "content": content}


def run_check(client, model: str, messages: list[dict], root: Path) -> None:
    for _ in range(8):
        reply = call_model(client, model, messages, TOOLS)
        messages.append(reply)
        if not reply.get("tool_calls"):
            print("\nREPORT:\n" + (reply.get("content") or ""))
            return
        for call in reply["tool_calls"]:
            result = dispatch(call, root)
            messages.append(result)
    raise RuntimeError("Agent stopped at the model-call limit.")
