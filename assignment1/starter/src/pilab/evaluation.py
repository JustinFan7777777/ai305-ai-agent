"""Summarize tool use and independent checks for one budget task."""

import argparse
import json
from pathlib import Path


def evaluate_run(transcript: list[dict], check: dict) -> dict:
    """TODO: Count calls, validate their arguments, and summarize the outcome.

    Return tool_calls, valid_call_rate (None if there are no calls),
    execution_errors, output_correct, variants_correct, data_unchanged,
    and task_success. Reuse your tool argument models. Count execution
    errors only for schema-valid calls whose result has is_error=True.
    Task success requires all three independent checks to pass.
    """
    raise NotImplementedError("Implement Assignment 1 evaluation.")


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
