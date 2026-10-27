import argparse
from task_store import load_tasks, select_tasks


def main():
    parser = argparse.ArgumentParser(description="List tasks with optional filters.")
    parser.add_argument(
        "--status",
        choices=["open", "done"],
        help="Filter by status (overrides the default of hiding done tasks)",
    )
    parser.add_argument(
        "--priority",
        choices=["low", "medium", "high"],
        help="Filter by priority",
    )
    parser.add_argument(
        "--all",
        dest="all_tasks",
        action="store_true",
        help="Include both open and done tasks (default hides done tasks)",
    )
    args = parser.parse_args()

    if args.all_tasks and args.status is not None:
        raise SystemExit("error: --all cannot be combined with --status")

    try:
        tasks = select_tasks(
            load_tasks(),
            status=args.status,
            priority=args.priority,
            include_done=args.all_tasks,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")
    for task in tasks:
        print(f"{task['id']}: {task['title']} [{task['status']}, {task['priority']}]")
    if not tasks:
        print("No tasks.")


if __name__ == "__main__":
    main()
