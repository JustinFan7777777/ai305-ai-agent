"""Run: uv run python lab4_agent.py

Complete Exercises 1–2, then implement dispatch.
Set DASHSCOPE_API_KEY before running; this exercise uses a real model and API credit.
DASHSCOPE_BASE_URL and DASHSCOPE_MODEL override the Lab 3 defaults.
Observe the tool calls and check for Total: CNY 290.
The task starts with a missing file. Find the read error in the output,
then observe how the model locates the actual file and continues.
The live run uses a fresh temporary project and returns small outputs in full.
"""

import json
import os
from pathlib import Path
import subprocess

from openai import OpenAI

from lab4_bash import project_copy, run_bash
from lab4_schema import build_tools, read_file, write_file, validate_call

SYSTEM_PROMPT = (
    "You work on a small Python project using bash, read, and write. "
    "Use read to inspect README.md, source, and data; follow next_offset until you have the complete file. "
    "Use write with the complete new source to change files; keep items.json unchanged. "
    "After editing, run the program and compare its output with the expected result. "
    "Base your answer on the returned tool results. A command returning exit_code=0 "
    "alone does not prove the calculation is correct. Answer briefly in English."
)
TASK = (
    "活动预算程序算出来的总价不对。请先用 read 尝试读取 expense.py。"
    "如果文件不存在，根据工具返回的错误，用 bash 列出文件，找到实际程序。"
    "然后阅读项目说明、源码和数据，修复计算，并运行程序检查结果。"
)


def dispatch(call: dict, root: Path) -> dict:
    """TODO: Execute one tool call and return its result or error.

    Map bash/read/write to the imported run_bash/read_file/write_file.
    First call validate_call(call) from Exercise 2. Use call["function"]["name"]
    to select the function, then call function(root=root, **arguments).
    Return the tool's result dict unchanged, including nonzero bash exits.
    Catch ValueError (including Pydantic ValidationError), OSError, and
    subprocess.SubprocessError; return {"error": str(error)}.
    """

    try:
        arguments = validate_call(call)

        name = call["function"]["name"]

        if name == "bash":
            return run_bash(root=root, **arguments)

        if name == "read":
            return read_file(root=root, **arguments)

        if name == "write":
            return write_file(root=root, **arguments)

        raise ValueError(f"Unknown tool: {name}")

    # ValueError includes Pydantic ValidationError
    # OSError includes FileNotFoundError, PermissionError, etc.
    # subprocess.SubprocessError includes TimeoutExpired, CalledProcessError, etc.
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        return {"error": str(error)}


def run_agent(client, model: str, root: Path, max_calls: int = 8) -> dict:
    tools = build_tools()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TASK},
    ]
    trace = []
    for count in range(1, max_calls + 1):
        completion = client.chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice="auto",
            max_tokens=1024, extra_body={"enable_thinking": False},
        )
        choice = completion.choices[0]
        if choice.finish_reason not in {"stop", "tool_calls"}:
            return {"trace": trace, "text": None, "reason": choice.finish_reason, "model_calls": count}
        reply = choice.message.model_dump(
            include={"role", "content", "tool_calls"}, exclude_none=True,
        )
        messages.append(reply)
        if not reply.get("tool_calls"):
            return {"trace": trace, "text": reply.get("content"), "reason": "final", "model_calls": count}
        for call in reply["tool_calls"]:
            result = dispatch(call, root)
            step = {"name": call["function"]["name"], "arguments": call["function"]["arguments"], "result": result}
            trace.append(step)
            print(json.dumps(step, ensure_ascii=False, indent=2))
            messages.append({
                "role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })
    return {"trace": trace, "text": None, "reason": "max_calls", "model_calls": max_calls}


def main() -> None:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise SystemExit("Set DASHSCOPE_API_KEY before running this exercise.")
    client = OpenAI(
        api_key=key,
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=30.0, max_retries=0,
    )
    with project_copy() as root:
        original_data = (root / "items.json").read_bytes()
        result = run_agent(client, os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash"), root)
        check = run_bash("python budget.py", root)
        unchanged = (root / "items.json").read_bytes() == original_data
        print("Independent program run:")
        print(json.dumps(check, indent=2))
        print("Final answer:", result["text"])
        print("Stop reason:", result["reason"])
        print("Input data unchanged:", unchanged)


if __name__ == "__main__":
    main()
