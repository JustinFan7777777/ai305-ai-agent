import json
from pathlib import Path


def load_tasks():
    return json.loads(Path(__file__).with_name("tasks.json").read_text(encoding="utf-8"))


def select_tasks(tasks):
    return list(tasks)
