# Version 1: filter the task list

Add `--status` (`open` or `done`) and `--priority` (`low`, `medium`, or `high`)
to `todo_cli.py`. Allow both filters together. Without filters, list all tasks.
Keep the current output format, input order, and `load_tasks()` function.
Print `No tasks.` when no tasks match. Invalid arguments must exit nonzero with
a readable stderr message and no traceback.

Add `select_tasks(tasks, status=None, priority=None)` in `task_store.py`.
Return matching task dictionaries without mutating the input list or its rows.
Raise `ValueError` for invalid filter values. Handle an empty task list.

Assume task rows have the shown fields and valid field values. Additional row
schema validation and deep copies of unchanged dictionaries are not required.

Read the current project before planning. Only change `task_store.py` and
`todo_cli.py`; keep `tasks.json` unchanged. Use Python's standard library.
Propose checks, wait for user approval, then implement and verify the behavior.
