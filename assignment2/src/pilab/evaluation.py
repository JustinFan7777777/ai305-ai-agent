"""Summarize tool use and independent checks for one budget task."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from pilab.tools.filesystem import ReadArguments, WriteArguments
from pilab.tools.shell import BashArguments


def evaluate_run(transcript: list[dict], check: dict) -> dict:
    models = {"read": ReadArguments, "write": WriteArguments, "bash": BashArguments}
    calls = [
        call
        for message in transcript
        if message["role"] == "assistant"
        for call in message.get("tool_calls", [])
    ]
    results = {m["tool_call_id"]: m for m in transcript if m["role"] == "tool"}
    valid = execution_errors = 0
    for call in calls:
        model = models.get(call["name"])
        if model is None:
            continue
        try:
            model.model_validate(call["arguments"])
        except ValidationError:
            continue
        valid += 1
        if results.get(call["id"], {}).get("is_error", False):
            execution_errors += 1
    outcomes = {
        field: check.get(field) is True for field in ("output_correct", "variants_correct", "data_unchanged")
    }
    return {
        "tool_calls": len(calls),
        "valid_call_rate": valid / len(calls) if calls else None,
        "execution_errors": execution_errors,
        **outcomes,
        "task_success": all(outcomes.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one recorded budget task")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--check", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.run.read_text().splitlines() if line.strip()]
    if len(rows) != 1:
        parser.error("--run must contain exactly one JSONL result")
    check = json.loads(args.check.read_text())
    report = evaluate_run(rows[0]["transcript"], check)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
