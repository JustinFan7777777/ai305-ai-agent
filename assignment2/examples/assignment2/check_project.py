"""Run: python examples/assignment2/check_project.py WORKSPACE --version 1"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE = Path(__file__).resolve().parent / "workspace"


def run_python(root, arguments):
    try:
        result = subprocess.run(
            [sys.executable, *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit_code": None, "stdout": "", "stderr": str(error)}


def check_project(root, version):
    root = Path(root).resolve()
    rows = json.loads((BASELINE / "tasks.json").read_text(encoding="utf-8"))
    results = []

    def record(name, expected, actual, passed):
        results.append({"name": name, "expected": expected, "actual": actual, "passed": passed})

    cases = [([], [1, 2, 3, 4, 5, 6] if version == 1 else [1, 3, 5])]
    for status in ("open", "done"):
        cases.append((["--status", status], [t["id"] for t in rows if t["status"] == status]))
    for priority in ("low", "medium", "high"):
        cases.append(
            (
                ["--priority", priority],
                [
                    t["id"]
                    for t in rows
                    if t["priority"] == priority and (version == 1 or t["status"] == "open")
                ],
            )
        )
        for status in ("open", "done"):
            cases.append(
                (
                    ["--status", status, "--priority", priority],
                    [t["id"] for t in rows if t["priority"] == priority and t["status"] == status],
                )
            )
    invalid = [["--status", "unknown"], ["--priority", "urgent"]]
    if version == 2:
        cases.extend(
            [
                (["--all"], [1, 2, 3, 4, 5, 6]),
                (["--all", "--priority", "high"], [1, 2]),
            ]
        )
        invalid.append(["--all", "--status", "open"])
    for arguments, ids in cases:
        output = (
            "".join(
                f"{t['id']}: {t['title']} [{t['status']}, {t['priority']}]\n" for t in rows if t["id"] in ids
            )
            or "No tasks.\n"
        )
        expected = {"exit_code": 0, "stdout": output, "stderr": ""}
        actual = run_python(root, ["todo_cli.py", *arguments])
        record("CLI " + " ".join(arguments or ["(default)"]), expected, actual, actual == expected)
    for arguments in invalid:
        actual = run_python(root, ["todo_cli.py", *arguments])
        passed = actual["exit_code"] not in {None, 0} and bool(actual["stderr"].strip())
        passed = passed and not actual["stdout"] and "Traceback" not in actual["stderr"]
        record("CLI " + " ".join(arguments), "readable nonzero error without traceback", actual, passed)

    options = [
        {},
        {"status": "done"},
        {"priority": "high"},
        {"status": "open", "priority": "high"},
        {"status": "bad"},
        {"priority": "bad"},
    ]
    expected_ids = [
        [11, 12] if version == 1 else [12],
        [11],
        [11] if version == 1 else [],
        [],
        "ValueError",
        "ValueError",
    ]
    if version == 2:
        options += [{"include_done": True}, {"include_done": True, "status": "done"}]
        expected_ids += [[11, 12], "ValueError"]
    code = (
        "import json\nfrom task_store import select_tasks\n"
        "rows = [dict(id=11,title='A',status='done',priority='high'),"
        "dict(id=12,title='B',status='open',priority='low')]\n"
        "before = json.dumps(rows)\nresults = []\n"
        f"for options in {options!r}:\n"
        "    try: results.append([t['id'] for t in select_tasks(rows, **options)])\n"
        "    except ValueError: results.append('ValueError')\n"
        "assert json.dumps(rows) == before\n"
        "assert select_tasks([], status='open') == []\n"
        "print(json.dumps(results))\n"
    )
    actual = run_python(root, ["-c", code])
    expected = {"exit_code": 0, "stdout": json.dumps(expected_ids) + "\n", "stderr": ""}
    record("Independent function inputs and input preservation", expected, actual, actual == expected)

    with tempfile.TemporaryDirectory(prefix="a2-empty-") as directory:
        copy = Path(directory)
        for name in ("task_store.py", "todo_cli.py"):
            shutil.copy2(root / name, copy / name)
        (copy / "tasks.json").write_text("[]\n", encoding="utf-8")
        actual = run_python(copy, ["todo_cli.py"])
        expected = {"exit_code": 0, "stdout": "No tasks.\n", "stderr": ""}
        record("Empty CLI input", expected, actual, actual == expected)
        (copy / "tasks.json").write_text(json.dumps([rows[0]]) + "\n", encoding="utf-8")
        actual = run_python(copy, ["todo_cli.py", "--status", "done", "--priority", "low"])
        expected = {"exit_code": 0, "stdout": "No tasks.\n", "stderr": ""}
        record("CLI no match on independent nonempty data", expected, actual, actual == expected)
    unchanged = (root / "tasks.json").read_bytes() == (BASELINE / "tasks.json").read_bytes()
    record("tasks.json unchanged", True, unchanged, unchanged)
    return results


def main():
    parser = argparse.ArgumentParser(description="Check task-list behavior independently of the Agent.")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--version", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    try:
        results = check_project(args.workspace, args.version)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot check project: {error}\n")
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if results and all(result["passed"] for result in results) else 1)


if __name__ == "__main__":
    main()
