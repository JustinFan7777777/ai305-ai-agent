# Version 2: show open tasks by default

Revise the implementation: hide done tasks by default. Add `--all` to include
both statuses. An explicit `--status` overrides the default. Reject `--all`
combined with `--status`. Priority filtering still applies. Keep output format,
input order, empty-result behavior, and readable errors.

Extend the function to
`select_tasks(tasks, status=None, priority=None, include_done=False)`.
When status is omitted, `include_done=True` includes both statuses.
Raise `ValueError` when it is combined with an explicit status or when a filter
value is invalid. Never mutate the input list or its rows.

Assume task rows satisfy the given field contract and `include_done` is a boolean.
No additional input-type or row-schema validation is required.

This replaces version 1's default of showing every task. Read current files
and old results, produce a revised plan, and wait for fresh approval before
editing. Only change `task_store.py` and `todo_cli.py`. Keep `tasks.json` unchanged
and use the standard library. Run new checks; old results are historical evidence.
