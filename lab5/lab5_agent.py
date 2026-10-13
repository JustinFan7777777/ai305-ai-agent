"""Run: uv run python lab5_agent.py --context compact --compact-at 1200

Complete Exercises 1-2, then prepare_context. Set DASHSCOPE_API_KEY.
Compare --context full, window, compact with the same --compact-at value.
All policies respect --context-limit (default 64000), output reserve, and margin.
Compare final evidence, peak task-input tokens, and totals including counting probes.
"""

import json

from lab5_budget import inspect_budget
from lab5_compact import compact_history
from lab5_common import (
    CONTEXT_LIMIT, MODEL_USAGE, ROOT, agent_request, budget_parser, connect,
    load_messages, record_usage, show_usage, split_history,
)


def prepare_context(client, model: str, messages: list[dict], policy: str = "compact",
                    context_limit: int = CONTEXT_LIMIT, compact_at: int | None = None,
                    report_read: bool = False) -> tuple[list[dict], dict]:
    """TODO: Apply a policy, then check the actual next request before sending.

    Build agent_request(model, messages, report_read) and call inspect_budget
    with context_limit and compact_at. This reuses Exercise 1.
    full: retain all messages.
    window: retain messages[:2] and the last two complete groups from split_history.
    compact: when needs_compact is true, call compact_history from Exercise 2.
    If context changed, rebuild agent_request and inspect its budget again.
    All policies must fit the input budget, or raise ValueError.
    If compact was triggered, require a smaller input below compact_at, or stop.
    Print before/after input tokens. Return (context, budget_status).
    Do not modify messages; counting replies never enter the task history.
    """

    # three policies: full, window and compact
    if policy not in {"full", "window", "compact"}:
        raise ValueError(f"Unknown context policy: {policy}")

    # build the initial request and inspect its budget
    original_request = agent_request(model, messages, report_read)
    original_status = inspect_budget(
        client,
        original_request,
        context_limit,
        compact_at,
    )

    context = list(messages)
    changed = False
    compacted = False

    # full -> retain all messages
    if policy == "full":
        context = list(messages)

    # window -> keep the first two messages and the last two complete groups from split_history
    elif policy == "window":
        # keep the first two messages:
        # 1. system: contains the task instructions and context
        # 2. user: contains the initial user input
        # then keep the last two complete groups of messages from split_history
        _, recent = split_history(messages[2:], keep_groups=2)
        context = list(messages[:2]) + recent
        changed = context != messages

    # compact -> generate a summary of the older messages
    elif policy == "compact":
        if original_status["needs_compact"]:
            context = compact_history(
                client,
                model,
                messages,
                context_limit,
            )
            changed = context != messages
            compacted = True

    # if context changed, rebuild the request and inspect its budget again
    # if not changed, use the original request and status
    if changed:
        final_request = agent_request(model, context, report_read)
        final_status = inspect_budget(
            client,
            final_request,
            context_limit,
            compact_at,
        )

        # print the before/after input tokens
        print(
            "Agent input tokens:",
            original_status["input_tokens"],
            "->",
            final_status["input_tokens"],
        )
    else:
        # if context did not change, use the original request and status
        final_status = original_status
        print(
            "Agent input tokens:",
            final_status["input_tokens"],
        )

    # if the final status does not fit the input budget, raise a ValueError
    if not final_status["fits"]:
        raise ValueError(
            f"Context policy {policy!r} still exceeds the input budget: "
            f"{final_status['input_tokens']} > {final_status['input_budget']}"
        )

    # if compacted and the final input tokens exceed the compact_at trigger, raise a ValueError
    if compacted and final_status["input_tokens"] >= final_status["compact_at"]:
        raise ValueError(
            "Compaction did not reduce the rebuilt context below the trigger: "
            f"{final_status['input_tokens']} >= {final_status['compact_at']}"
        )

    # The returned status describes the exact request that the caller will
    # send. Probe completions never become part of the task history.
    return context, final_status


def read_verification() -> dict:
    return json.loads((ROOT / "data" / "verification.json").read_text(encoding="utf-8"))


def dispatch(call: dict) -> dict:
    try:
        arguments = json.loads(call["function"]["arguments"])
        if call["function"]["name"] != "read_verification" or arguments != {}:
            raise ValueError("Use read_verification with empty arguments.")
        return read_verification()
    except (ValueError, OSError) as error:
        return {"error": str(error)}



def run_agent(client, model: str, context_policy: str = "compact",
              context_limit: int = CONTEXT_LIMIT, compact_at: int | None = None,
              max_calls: int = 4) -> None:
    MODEL_USAGE.clear()
    context = load_messages()
    full_record = list(context)
    report_read = False
    peak_tokens = 0
    tool_calls = 0
    print(f"Context policy: {context_policy}; application ceiling: {context_limit} tokens")
    for number in range(1, max_calls + 1):
        context, status = prepare_context(
            client, model, context, context_policy, context_limit, compact_at, report_read,
        )
        peak_tokens = max(peak_tokens, status["input_tokens"])
        print(f"Call {number}: input budget={status['input_budget']}, compact at={status['compact_at']}")
        completion = client.chat.completions.create(**agent_request(model, context, report_read))
        record_usage(completion, "Agent")
        choice = completion.choices[0]
        if choice.finish_reason not in {"stop", "tool_calls"}:
            raise RuntimeError(f"Agent response incomplete: {choice.finish_reason}")
        reply = choice.message.model_dump(
            include={"role", "content", "tool_calls"}, exclude_none=True,
        )
        context.append(reply)
        full_record.append(reply)
        if not reply.get("tool_calls"):
            if not report_read:
                raise RuntimeError("The agent answered without reading verification.")
            print("Final answer:", reply.get("content"))
            print(f"Messages: context={len(context)}, full record={len(full_record)}")
            print(f"Peak task-input tokens: {peak_tokens}; tool calls: {tool_calls}")
            show_usage()
            print("Check: cause, original 160, expected/verified 290, and unchanged items.json.")
            print("A window may lose the cause or expected-value evidence; identify what needs rereading.")
            print("This loop reads a teaching report; it does not run a repair or provide a reread tool.")
            return
        for call in reply["tool_calls"]:
            tool_calls += 1
            result = dispatch(call)
            report_read = report_read or "stdout" in result
            print("Tool:", call["function"]["name"], json.dumps(result))
            message = {
                "role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            }
            context.append(message)
            full_record.append(message)
    raise RuntimeError("Agent stopped at the model-call limit.")


def main() -> None:
    parser = budget_parser()
    parser.add_argument("--context", choices=("full", "window", "compact"), default="compact")
    args = parser.parse_args()
    client, model = connect()
    run_agent(client, model, args.context, args.context_limit, args.compact_at)


if __name__ == "__main__":
    main()
