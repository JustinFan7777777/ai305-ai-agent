"""Exercise 3: Run a ReAct loop to find a suitable train.

Run: uv run python lab3_react.py
Complete Exercises 1-2 first; reuse Exercise 2's API setup.
Change max_calls in main from 6 to 1 and compare messages and stop reasons.
"""

import json
import os

from lab3_call import SYSTEM_PROMPT, create_client, request
from lab3_tools import dispatch

TASK = (
    "帮我找明天上午深圳北到广州南的高铁，二等座有票，100 元以内。"
    "查好出发时间、票价和余票后推荐一趟，并说明原因。只查询，不买票。"
)


def run_agent(client, model: str, task: str, max_calls: int = 6) -> dict:
    """TODO: Run up to max_calls model requests and fill in the result dictionary.

    Call request with tool_choice="auto" and append each reply to messages.
    Dispatch all tool_calls and append matching tool messages, as in Exercise 2.
    With no tool_calls, return the answer with reason="final".
    At the limit, return text=None and reason="max_calls".
    Count model requests, not tool calls; one reply may request several tools.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    model_calls = 0 # count of model requests made

    for _ in range(max_calls):
        reply = request(
            client,
            messages,
            model,
            tool_choice="auto",
        )

        model_calls += 1

        messages.append(reply)

        tool_calls = reply.get("tool_calls", [])

        if not tool_calls:
            return {
                "messages": messages,
                "text": reply.get("content"),
                "reason": "final",
                "model_calls": model_calls,
            }

        for call in tool_calls:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": dispatch(call),
                }
            )

    # TODO: Implement the loop; return early when the model answers.
    return {
        "messages": messages,     # list[dict]: full message history, including tool results.
        "text": None,         # str | None: final answer, or None at the call limit.
        "reason": "max_calls",       # str: "final" or "max_calls".
        "model_calls": model_calls,  # int: number of model requests made.
    }


def main() -> None:
    result = run_agent(
        create_client(), os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash"),
        TASK, max_calls=6,
    )
    print("Run result:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
