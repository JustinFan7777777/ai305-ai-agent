"""Summarize tool use and independent checks for one budget task."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from pilab.core.agent import TOOL_ARGUMENT_MODELS


def _valid_tool_call(call: dict) -> bool:
    """Return whether one serialized tool call passes the live tool schema."""

    name = call.get("name")
    arguments = call.get("arguments")
    if not isinstance(name, str):
        return False
    model = TOOL_ARGUMENT_MODELS.get(name)
    if model is None or not isinstance(arguments, dict):
        return False
    try:
        model.model_validate(arguments)
    except ValidationError:
        return False
    return True


def evaluate_run(transcript: list[dict], check: dict) -> dict:
    """Count validated calls, execution errors, and independent check results.

    The transcript is the source of truth for tool activity. The separate
    checker is the source of truth for task correctness; an assistant's final
    prose is intentionally not treated as evidence of success.
    """

    calls: list[dict] = []
    results_by_id: dict[str, list[dict]] = {}

    for message in transcript:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "assistant":
            raw_calls = message.get("tool_calls", [])
            if isinstance(raw_calls, list):
                calls.extend(call for call in raw_calls if isinstance(call, dict))
        elif message.get("role") == "tool":
            tool_call_id = message.get("tool_call_id")
            if isinstance(tool_call_id, str):
                results_by_id.setdefault(tool_call_id, []).append(message)

    valid_calls = [call for call in calls if _valid_tool_call(call)]
    execution_errors = 0
    for call in valid_calls:
        call_id = call.get("id")
        if not isinstance(call_id, str):
            continue
        execution_errors += sum(
            result.get("is_error") is True
            for result in results_by_id.get(call_id, [])
        )

    output_correct = check.get("output_correct") is True
    variants_correct = check.get("variants_correct") is True
    data_unchanged = check.get("data_unchanged") is True

    return {
        "tool_calls": len(calls),
        "valid_call_rate": len(valid_calls) / len(calls) if calls else None,
        "execution_errors": execution_errors,
        "output_correct": output_correct,
        "variants_correct": variants_correct,
        "data_unchanged": data_unchanged,
        "task_success": output_correct and variants_correct and data_unchanged,
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
