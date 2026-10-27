"""Shared model loop, project tools, and behavior checks for Lab 7."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from openai import OpenAI

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "workspace"
PROJECT = WORK / "project"
TASK = (
    "Add --status (open/done) and --priority (low/medium/high) filters to todo_cli.py. "
    "Allow both filters together. Keep the existing line format, task order, and no-argument output. "
    "Print 'No tasks.' when nothing matches. Invalid options must produce a readable error on "
    "stderr and exit nonzero without a traceback. Add select_tasks(tasks, status=None, priority=None) "
    "in task_store.py; it returns matching task dictionaries and raises ValueError for invalid filters."
)
CHANGE = (
    "By default, hide done tasks. Add --all to include both statuses. An explicit --status overrides "
    "the default; --all and --status together must produce a readable nonzero error. Priority filtering "
    "still applies. Extend select_tasks with include_done=False; True includes both statuses when "
    "status is omitted. Reject include_done=True combined with an explicit status. "
    "This replaces the old default of showing every task. Keep output format, order, and empty-result behavior."
)
RULES = (
    "Only modify task_store.py and todo_cli.py. Do not change tasks.json or files outside the project. "
    "Use the Python standard library; do not install packages or access the network. "
    "Read the current files before editing. Keep load_tasks() available."
)
USAGE = []


def connect() -> tuple[OpenAI, str]:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise SystemExit("Set DASHSCOPE_API_KEY before running this exercise.")
    return OpenAI(
        api_key=key,
        base_url=os.getenv(
            "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ),
        timeout=60.0,
        max_retries=0,
    ), os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash")


def show_usage() -> None:
    print("MODEL CALLS:", len(USAGE))
    if all(usage is not None for usage in USAGE):
        print("TOKENS:", sum(usage.total_tokens for usage in USAGE))


def prepare_project() -> Path:
    if not PROJECT.exists():
        WORK.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / "project", PROJECT)
    return PROJECT


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }


def run_python(root: Path, args: list[str]) -> dict:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DASHSCOPE_API_KEY", "OPENAI_API_KEY"}
    }
    try:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            env=environment,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "stdout": "", "stderr": "Check exceeded 10 seconds."}


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


READ_TOOLS = [
    tool("list_files", "List the project files.", {}, []),
    tool(
        "read_file",
        "Read a project file as UTF-8.",
        {"path": {"type": "string"}},
        ["path"],
    ),
]
WRITE_TOOLS = [
    tool(
        "write_file",
        "Replace task_store.py or todo_cli.py with complete Python source.",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        ["path", "content"],
    ),
    tool(
        "run_python",
        "Run Python in the project; return stdout, stderr, and exit_code. "
        "Use args like ['todo_cli.py', '--status', 'open'] or ['-c', 'Python code'].",
        {"args": {"type": "array", "items": {"type": "string"}}},
        ["args"],
    ),
]


def dispatch(name: str, arguments: dict, root: Path, mode: str) -> dict:
    allowed = {
        t["function"]["name"]
        for t in READ_TOOLS + (WRITE_TOOLS if mode == "execute" else [])
    }
    if name not in allowed:
        raise ValueError(f"{name} is not allowed in {mode} mode.")
    if name == "list_files":
        return {"files": sorted(p.name for p in root.iterdir() if p.is_file())}
    if name == "run_python":
        return run_python(root, arguments["args"])
    path = (root / arguments["path"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Use a path inside the project.")
    if name == "read_file":
        return {"content": path.read_text(encoding="utf-8")}
    if path not in {root.resolve() / "task_store.py", root.resolve() / "todo_cli.py"}:
        raise ValueError("Only task_store.py and todo_cli.py may be edited.")
    path.write_text(arguments["content"], encoding="utf-8")
    return {"written": path.name}


def run_agent(messages: list[dict], root: Path, tools: list[dict], mode: str) -> str:
    client, model = connect()
    offered = {t["function"]["name"] for t in tools}
    for _ in range(12):
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=4000,
            extra_body={"enable_thinking": False},
        )
        USAGE.append(completion.usage)
        choice = completion.choices[0]
        if choice.finish_reason not in {"stop", "tool_calls"}:
            raise RuntimeError(f"Incomplete response: {choice.finish_reason}")
        reply = choice.message.model_dump(
            include={"role", "content", "tool_calls"},
            exclude_none=True,
        )
        messages.append(reply)
        calls = reply.get("tool_calls", [])
        if not calls:
            if not reply.get("content", "").strip():
                raise RuntimeError("The model returned no plan or report.")
            return reply["content"]
        for call in calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"]["arguments"])
                if name not in offered:
                    raise ValueError("That tool was not offered in this request.")
                print("TOOL:", name, arguments.get("path", arguments.get("args", "")))
                result = dispatch(name, arguments, root, mode)
                if name == "run_python":
                    print(json.dumps(result, ensure_ascii=False))
            except (ValueError, OSError, KeyError, TypeError) as error:
                result = {"error": str(error)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    raise RuntimeError("Model-call limit reached; work is incomplete.")


def verify(root: Path, version: int) -> list[dict]:
    tasks = json.loads((ROOT / "project" / "tasks.json").read_text(encoding="utf-8"))
    results = []

    def record(name, expected, actual, passed):
        results.append(
            {"name": name, "expected": expected, "actual": actual, "passed": passed}
        )
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
        if not passed:
            print(json.dumps(results[-1], indent=2, ensure_ascii=False))

    cases = [
        ([], [1, 2, 3, 4, 5, 6] if version == 1 else [1, 3, 5]),
        (["--status", "done"], [2, 4, 6]),
        (["--status", "open"], [1, 3, 5]),
        (["--priority", "high"], [1, 2] if version == 1 else [1]),
        (["--priority", "medium"], [4, 5] if version == 1 else [5]),
        (["--priority", "low"], [3, 6] if version == 1 else [3]),
        (["--status", "done", "--priority", "high"], [2]),
        (["--priority", "low", "--status", "open"], [3]),
    ]
    invalid = [["--status", "unknown"], ["--priority", "urgent"], ["--unknown"]]
    if version == 2:
        cases += [
            (["--all"], [1, 2, 3, 4, 5, 6]),
            (["--all", "--priority", "high"], [1, 2]),
        ]
        invalid += [["--all", "--status", "done"], ["--status", "open", "--all"]]
    for args, ids in cases:
        output = "".join(
            f"{t['id']}: {t['title']} [{t['status']}, {t['priority']}]\n"
            for t in tasks
            if t["id"] in ids
        )
        expected = {"exit_code": 0, "stdout": output, "stderr": ""}
        actual = run_python(root, ["todo_cli.py", *args])
        record(
            "CLI " + " ".join(args or ["(default)"]),
            expected,
            actual,
            actual == expected,
        )
    for args in invalid:
        actual = run_python(root, ["todo_cli.py", *args])
        passed = (
            actual["exit_code"] not in (None, 0)
            and bool(actual["stderr"].strip())
            and "Traceback" not in actual["stderr"]
            and not actual["stdout"]
        )
        record(
            "CLI " + " ".join(args),
            "nonzero exit, readable stderr, no traceback",
            actual,
            passed,
        )

    api = """import json
from task_store import select_tasks
rows = [
    {"id": 11, "title": "A", "status": "done", "priority": "high"},
    {"id": 12, "title": "B", "status": "open", "priority": "low"},
]
before = json.dumps(rows)
results = []
for kwargs in KWARGS:
    try:
        results.append([t['id'] for t in select_tasks(rows, **kwargs)])
    except ValueError:
        results.append('ValueError')
assert json.dumps(rows) == before
assert select_tasks([], status='open') == []
print(json.dumps(results))
"""
    kwargs = [
        {},
        {"status": "done"},
        {"priority": "high"},
        {"status": "open", "priority": "high"},
        {"status": "unknown"},
        {"priority": "urgent"},
    ]
    expected_api = [
        [11, 12] if version == 1 else [12],
        [11],
        [11] if version == 1 else [],
        [],
        "ValueError",
        "ValueError",
    ]
    if version == 2:
        kwargs += [{"include_done": True}, {"include_done": True, "status": "done"}]
        expected_api += [[11, 12], "ValueError"]
    actual = run_python(root, ["-c", "KWARGS = " + repr(kwargs) + "\n" + api])
    expected = {"exit_code": 0, "stdout": json.dumps(expected_api) + "\n", "stderr": ""}
    record(
        "API filters, invalid options, empty result, input unchanged",
        expected,
        actual,
        actual == expected,
    )

    # Use a separate copy to check empty CLI output without changing the student's data.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="lab7-empty-") as folder:
        copy = Path(folder) / "project"
        shutil.copytree(root, copy, ignore=shutil.ignore_patterns("__pycache__"))
        (copy / "tasks.json").write_text("[]\n", encoding="utf-8")
        actual = run_python(copy, ["todo_cli.py"])
        expected = {"exit_code": 0, "stdout": "No tasks.\n", "stderr": ""}
        record("CLI empty task list", expected, actual, actual == expected)
    unchanged = (root / "tasks.json").read_bytes() == (
        ROOT / "project" / "tasks.json"
    ).read_bytes()
    record("tasks.json unchanged", True, unchanged, unchanged)
    return results


def save_results(results: list[dict], version: int) -> None:
    (WORK / f"results_v{version}.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )


def all_passed(results: list[dict]) -> bool:
    return bool(results) and all(result["passed"] for result in results)
