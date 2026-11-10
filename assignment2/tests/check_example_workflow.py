"""Exercise the supplied example using deterministic responses, not a live LLM."""

import json
import shlex
import shutil
import subprocess
import sys

from check_agent import ROOT, ScriptedBackend, answer, calls

from pilab.core.agent import Agent
from pilab.tools import BashTool, ReadTool, WriteTool

WORKSPACE = ROOT / "output/assignment2-workspace"
SESSION = ROOT / "output/a2-offline-session.jsonl"


class WorkflowBackend(ScriptedBackend):
    def complete(self, messages, tools, system_prompt):
        if system_prompt.startswith("Summarize the supplied conversation records"):
            # Fixture summary: this validates the compaction plumbing, not summary quality.
            return answer(
                "Offline fixture workflow. Preserve tasks.json, order, format, and standard library. "
                "Use the current task and reviewed plan; old check results are historical. "
                "Version 1 lists all tasks; version 2 shows open tasks by default and adds --all."
            )
        return super().complete(messages, tools, system_prompt)


def sources(version):
    original = (ROOT / "examples/assignment2/workspace/task_store.py").read_text()
    prefix = original[: original.index("def select_tasks")]
    signature = "def select_tasks(tasks, status=None, priority=None"
    signature += ", include_done=False):\n" if version == 2 else "):\n"
    function = """    if status not in (None, "open", "done"):
        raise ValueError("Invalid status; choose open or done.")
    if priority not in (None, "low", "medium", "high"):
        raise ValueError("Invalid priority; choose low, medium, or high.")
"""
    if version == 2:
        function += """    if include_done and status is not None:
        raise ValueError("include_done cannot be combined with status.")
    if status is None and not include_done:
        status = "open"
"""
    function += """    return [
        task for task in tasks
        if (status is None or task["status"] == status)
        and (priority is None or task["priority"] == priority)
    ]
"""
    cli = """import argparse

from task_store import load_tasks, select_tasks


def main():
    parser = argparse.ArgumentParser(description="List tasks.")
"""
    if version == 2:
        cli += """    status_options = parser.add_mutually_exclusive_group()
    status_options.add_argument("--status", choices=("open", "done"))
    status_options.add_argument("--all", action="store_true", dest="include_done")
"""
    else:
        cli += '    parser.add_argument("--status", choices=("open", "done"))\n'
    cli += """    parser.add_argument("--priority", choices=("low", "medium", "high"))
    args = parser.parse_args()
"""
    cli += "    tasks = select_tasks(load_tasks(), status=args.status, priority=args.priority"
    cli += ", include_done=args.include_done)\n" if version == 2 else ")\n"
    cli += """    for task in tasks:
        print(f"{task['id']}: {task['title']} [{task['status']}, {task['priority']}]")
    if not tasks:
        print("No tasks.")


if __name__ == "__main__":
    main()
"""
    return prefix + signature + function, cli


def main():
    if WORKSPACE.exists() or SESSION.exists():
        raise SystemExit(
            "Use a fresh offline workspace and session; refusing to overwrite previous evidence."
        )
    shutil.copytree(ROOT / "examples/assignment2/workspace", WORKSPACE)
    data = (WORKSPACE / "tasks.json").read_bytes()
    backend = WorkflowBackend()
    agent = Agent(
        backend,
        workspace=WORKSPACE,
        session=SESSION,
        skills=["todo-check"],
        tools=[ReadTool(WORKSPACE), WriteTool(WORKSPACE), BashTool(WORKSPACE)],
    )
    summary = {
        "mode": "offline scripted backend; not a real-model task-performance evaluation",
        "versions": [],
    }
    for version in (1, 2):
        store, cli = sources(version)
        prefix = f"v{version}"
        backend.replies += [
            calls(
                (prefix + "-read-store", "read", {"path": "task_store.py"}),
                (prefix + "-read-cli", "read", {"path": "todo_cli.py"}),
            ),
            answer(
                "Goal: implement the current task-list requirement. "
                "Edits: add validated nonmutating filters in task_store.py "
                "and argparse options in todo_cli.py. "
                f"Checks: version {version} filters, invalid options, empty and independent rows; "
                "preserve tasks.json. "
                "Read current files again before editing. Await explicit approval."
            ),
        ]
        command = (
            "/plan examples/assignment2/task.md" if version == 1 else "/revise examples/assignment2/change.md"
        )
        result = agent.run(command)
        assert result.status == "complete", result
        before = [(WORKSPACE / name).read_bytes() for name in ("task_store.py", "todo_cli.py")]
        refusal = agent.run("/execute")
        assert refusal.model_calls == 0
        assert before == [(WORKSPACE / name).read_bytes() for name in ("task_store.py", "todo_cli.py")]
        expected_count = 6 if version == 1 else 3
        check = (
            "from task_store import load_tasks,select_tasks; "
            f"assert len(select_tasks(load_tasks())) == {expected_count}; "
            'assert select_tasks([], status="open") == []; '
            f'print("Focused v{version} function checks passed")'
        )
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(check)}"
        backend.replies += [
            calls(
                (prefix + "-execute-read-store", "read", {"path": "task_store.py"}),
                (prefix + "-execute-read-cli", "read", {"path": "todo_cli.py"}),
            ),
            calls(
                (prefix + "-write-store", "write", {"path": "task_store.py", "content": store}),
                (prefix + "-write-cli", "write", {"path": "todo_cli.py", "content": cli}),
            ),
            calls((prefix + "-check", "bash", {"command": command})),
            answer(
                "The scripted fixture submitted two source writes and a focused function check. "
                "Actual results are in the tool transcript. Independent checker follows."
            ),
        ]
        record_start = len(agent.records)
        result = agent.run("/execute --approve")
        assert result.status == "complete", result
        assert agent.mode == "read-only"
        assert not any(getattr(m, "is_error", False) for m in agent.records[record_start:])
        completed = subprocess.run(
            [
                sys.executable,
                "examples/assignment2/check_project.py",
                str(WORKSPACE),
                "--version",
                str(version),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        (ROOT / f"output/check-v{version}.json").write_text(completed.stdout)
        assert completed.returncode == 0, completed.stderr + completed.stdout
        checks = json.loads(completed.stdout)
        summary["versions"].append(
            {
                "version": version,
                "passed": sum(c["passed"] for c in checks),
                "total": len(checks),
                "execution_model_calls": result.model_calls,
            }
        )
        assert (WORKSPACE / "tasks.json").read_bytes() == data
    (ROOT / "output/example-offline-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
