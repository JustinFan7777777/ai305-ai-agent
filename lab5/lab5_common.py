"""Shared API, transcript, and grouping helpers for Lab 5."""

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parent
CONTEXT_LIMIT = 64_000
SAFETY_MARGIN = 512
MODEL_USAGE = []
TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_verification",
        "description": (
            "Read the recorded verification after another developer applied the repair. "
            "Returns program output, exit code, and whether items.json stayed unchanged. "
            "This reads a supplied report; it does not execute the program."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}]

def connect() -> tuple[OpenAI, str]:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise SystemExit("Set DASHSCOPE_API_KEY before running this exercise.")
    client = OpenAI(
        api_key=key,
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=60.0, max_retries=0,
    )
    return client, os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash")


def load_messages() -> list[dict]:
    return json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8"))


def interaction_groups(history: list[dict]) -> list[list[dict]]:
    """Group each assistant call with all following tool results.

    The supplied history has complete tool batches and no later user updates.
    A previous assistant summary, if present, forms its own group.
    """
    groups = []
    for message in history:
        if message["role"] == "tool":
            groups[-1].append(message)
        else:
            groups.append([message])
    return groups



def split_history(history: list[dict], keep_groups: int) -> tuple[list[dict], list[dict]]:
    groups = interaction_groups(history)
    older = [message for group in groups[:-keep_groups] for message in group]
    recent = [message for group in groups[-keep_groups:] for message in group]
    return older, recent


def record_usage(completion, purpose: str) -> None:
    usage = completion.usage
    MODEL_USAGE.append((purpose, usage))
    if usage is None:
        print(f"{purpose}: API token usage unavailable")
    else:
        print(f"{purpose}: input={usage.prompt_tokens}, output={usage.completion_tokens} tokens")


def show_usage() -> None:
    for purposes, label in [
        ({"Count"}, "Counting probes"),
        ({"Summary", "Agent"}, "Summary + agent"),
        ({"Count", "Summary", "Agent"}, "Whole run"),
    ]:
        records = [usage for purpose, usage in MODEL_USAGE if purpose in purposes]
        if any(usage is None for usage in records):
            print(f"{label}: token usage unavailable")
            continue
        inputs = sum(usage.prompt_tokens for usage in records)
        outputs = sum(usage.completion_tokens for usage in records)
        print(f"{label}: calls={len(records)}, input={inputs}, output={outputs}, total={inputs + outputs}")


def agent_request(model: str, messages: list[dict], report_read: bool = False) -> dict:
    return {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "none" if report_read else {
            "type": "function", "function": {"name": "read_verification"},
        },
        "max_tokens": 700,
        "extra_body": {"enable_thinking": False},
    }


def budget_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-limit", type=int, default=CONTEXT_LIMIT,
                        help="Application token ceiling, including input and reserved output.")
    parser.add_argument("--compact-at", type=int, default=None,
                        help="Earlier input-token trigger, e.g. 1200 for this small transcript.")
    return parser
