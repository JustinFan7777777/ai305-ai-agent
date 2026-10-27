Plan

Goal
Add `--status` (open/done) and `--priority` (low/medium/high) filters to the todo CLI. Both filters may be combined (logical AND). Preserve the existing output line format, task order, no-argument behavior, and keep `load_tasks()` available. Invalid filter values must print a readable error on stderr and exit nonzero without a traceback. Core filtering logic lives in a new `select_tasks(tasks, status=None, priority=None)` in `task_store.py`.

Files to change
- `task_store.py`
- `todo_cli.py`
(No changes to `tasks.json` or any other file.)

Ordered edits

1. `task_store.py` — replace the placeholder `select_tasks` with the filtered version:
   - Signature: `def select_tasks(tasks, status=None, priority=None):`
   - Define valid values: `VALID_STATUSES = {"open", "done"}`, `VALID_PRIORITIES = {"low", "medium", "high"}` (module-level constants are fine).
   - Validation first, before iterating:
     - If `status is not None` and `status not in VALID_STATUSES`, raise `ValueError(f"Invalid status: {status!r}. Must be one of: done, open")` (or similar readable message).
     - Same pattern for `priority` with `low, medium, high`.
   - Filtering: iterate `tasks` in order; include a task only when (`status is None` or `task.get("status") == status`) AND (`priority is None` or `task.get("priority") == priority`). Return matching task dictionaries as a list (return the original dicts, not copies, so callers get task dictionaries unchanged).
   - Keep `import json`, `from pathlib import Path`, and `load_tasks()` exactly as they are.

2. `todo_cli.py` — add argparse options and wire them through:
   - Add arguments to the existing parser:
     - `parser.add_argument("--status", choices=["open", "done"], help="Filter by status")`
     - `parser.add_argument("--priority", choices=["low", "medium", "high"], help="Filter by priority")`
   - Using `choices=` gives argparse's built-in behavior: a readable usage-style error on **stderr** and exit code **2**, with no traceback — this satisfies the invalid-option requirement automatically.
   - Change the call to `tasks = select_tasks(load_tasks(), status=args.status, priority=args.priority)`. When flags are omitted, `args.status`/`args.priority` are `None`, so no filtering occurs.
   - Keep the print loop and line format identical: `f"{task['id']}: {task['title']} [{task['status']}, {task['priority']}]"` and the `if not tasks: print("No tasks.")` branch. Optionally update the parser `description` to mention filtering (cosmetic, allowed).

3. Defensive handling (belt-and-suspenders in `todo_cli.py` main):
   - Wrap the `select_tasks(...)` call in `try/except ValueError as exc:` and do `raise SystemExit(f"error: {exc}")` — `SystemExit` with a string prints to stderr and exits nonzero without a traceback. This covers programmatic misuse even though argparse `choices` should prevent it from the CLI.

Checks with expected results (manual, via `python todo_cli.py ...` from the project root)

1. No arguments: `python todo_cli.py`
   - Prints all 6 tasks in id order 1–6, same line format as before. Exit 0.
2. Status filter: `python todo_cli.py --status open`
   - Prints ids 1, 3, 5 in that order. Exit 0.
3. Priority filter: `python todo_cli.py --priority high`
   - Prints ids 1, 2 in that order. Exit 0.
4. Both filters: `python todo_cli.py --status open --priority low`
   - Prints only id 3 (`Review notes`). Exit 0.
5. Empty result: `python todo_cli.py --status done --priority high` combined check plus a guaranteed-empty case like `--status open --priority high` → prints id 1 (not empty); use `--status done --priority medium` → prints id 4. For a true empty match test at store level: `select_tasks(load_tasks(), status="open", priority="bogus")` raises `ValueError` (invalid), so an empty-but-valid case is e.g. calling `select_tasks([], status="open")` → `[]`; via CLI, empty output triggers `No tasks.` (verify by temporarily reasoning over data: no CLI combination of valid filters yields empty on current data, so confirm the `No tasks.` branch by unit-checking `select_tasks` with an empty list and confirming the CLI prints `No tasks.` when given it).
6. Invalid status: `python todo_cli.py --status pending`
   - Argparse writes `argument --status: invalid choice: 'pending' (choose from 'open', 'done')` to stderr, exit code 2, no traceback.
7. Invalid priority: `python todo_cli.py --priority urgent`
   - Readable stderr error listing `low, medium, high`, exit 2, no traceback.
8. Store-level validation: in a Python REPL, `select_tasks(load_tasks(), status="nope")` and `select_tasks(load_tasks(), priority="nope")` each raise `ValueError` with a readable message.
9. Regression: `from task_store import load_tasks` still works and returns the 6 raw task dicts unchanged; `tasks.json` is untouched; returned tasks are the same dictionaries (same key set: id, title, status, priority).

Out of scope / constraints honored
- Standard library only (`argparse`, `json`, `pathlib`); no packages, no network.
- Only `task_store.py` and `todo_cli.py` modified.
- Existing line format, ordering, and default (unfiltered) output preserved.
