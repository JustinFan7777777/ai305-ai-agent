import argparse
from task_store import load_tasks, select_tasks


def main():
    parser = argparse.ArgumentParser(description="List tasks.")
    parser.parse_args()
    tasks = select_tasks(load_tasks())
    for task in tasks:
        print(f"{task['id']}: {task['title']} [{task['status']}, {task['priority']}]")
    if not tasks:
        print("No tasks.")


if __name__ == "__main__":
    main()
