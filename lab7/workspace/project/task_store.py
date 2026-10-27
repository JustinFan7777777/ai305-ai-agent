import json
from pathlib import Path

VALID_STATUSES = {"open", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}


def load_tasks():
    return json.loads(
        Path(__file__).with_name("tasks.json").read_text(encoding="utf-8")
    )


def select_tasks(tasks, status=None, priority=None, include_done=False):
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status!r}. Must be one of: "
            + ", ".join(sorted(VALID_STATUSES))
        )
    if priority is not None and priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority: {priority!r}. Must be one of: "
            + ", ".join(sorted(VALID_PRIORITIES))
        )
    if include_done and status is not None:
        raise ValueError(
            "Cannot combine include_done=True with an explicit status filter."
        )

    matches = []
    for task in tasks:
        task_status = task.get("status")
        if status is not None:
            # Explicit status filter overrides defaults.
            if task_status != status:
                continue
        elif not include_done:
            # Default: hide done tasks.
            if task_status != "open":
                continue
        # include_done=True with no status: include both statuses.
        if priority is not None and task.get("priority") != priority:
            continue
        matches.append(task)
    return matches
