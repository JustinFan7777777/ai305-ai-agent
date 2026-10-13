"""Run: uv run python lab5_budget.py [--context-limit 64000] [--compact-at 1200]

Complete inspect_budget. Set DASHSCOPE_API_KEY; counting uses paid API calls.
Try the default ceiling, then --compact-at 1200 to observe an early warning.
"""

from lab5_common import (
    SAFETY_MARGIN, agent_request, budget_parser, connect,
    interaction_groups, load_messages, record_usage, show_usage,
)


def inspect_budget(client, request: dict, context_limit: int, compact_at: int | None = None) -> dict:
    """TODO: Measure the request through the API and return its budget status.

    input_budget = context_limit - request["max_tokens"] - SAFETY_MARGIN.
    Use compact_at as the trigger, or input_budget when it is None.
    Require 0 < trigger <= input_budget; otherwise raise ValueError.

    Copy request with dict(request), change only max_tokens to 1, then call
    client.chat.completions.create(**probe). Keep messages, tools, and tool_choice.
    Call record_usage(completion, "Count"), then read completion.usage.prompt_tokens.
    Raise RuntimeError if usage is missing. Discard the reply; never execute it.

    Return input_tokens, input_budget, compact_at, needs_compact (used >= trigger),
    and fits (used <= input_budget). Do not mutate request.
    This paid probe must itself fit the provider's real window; API errors stop
    the run. It is not a separate tokenizer endpoint.
    """

    # max_tokens = number of tokens the model can generate in response
    # context_limit contains the total number of tokens allowed in the model's context window
    input_budget = context_limit - request["max_tokens"] - SAFETY_MARGIN

    # determine the trigger value based on compact_at or input_budget
    trigger = input_budget if compact_at is None else compact_at

    # if trigger > input_budget,
    # it means the user wants to compact at a value that is larger than the available budget,
    # which is invalid
    if not 0 < trigger <= input_budget:
        raise ValueError(
            "compact_at must satisfy: 0 < compact_at <= input_budget"
        )

    probe = dict(request) # create a copy of the request to avoid mutating the original
    probe["max_tokens"] = 1 # set max_tokens to 1 for the probe
    # why setting max_tokens to 1?
    # Because we only want to measure the input tokens used,
    # not generate a full response.

    # call the API to get the completion
    completion = client.chat.completions.create(**probe)
    record_usage(completion, "Count") # record the usage for counting

    if completion.usage is None:
        raise RuntimeError("API did not return token usage information.")

    # get the number of input tokens used from the completion usage.
    input_tokens = completion.usage.prompt_tokens

    return {
        # the number of tokens used in the input messages,
        "input_tokens": input_tokens,

        # the maximum number of tokens that can be used in the input messages
        "input_budget": input_budget,

        # the threshold for when to compact the context
        "compact_at": trigger,

        # whether the input tokens used exceeds the trigger value,
        # if it does, we need to compact the context before continuing
        "needs_compact": input_tokens >= trigger,

        # whether the input tokens used fits within the available budget.
        "fits": input_tokens <= input_budget,
    }


def main() -> None:
    args = budget_parser().parse_args()
    client, model = connect()
    messages = load_messages()
    context = messages[:2]
    for number, group in enumerate(interaction_groups(messages[2:]), 1):
        context = context + group
        status = inspect_budget(client, agent_request(model, context),
                                args.context_limit, args.compact_at)
        print(f"After group {number}: {status}")
        if status["needs_compact"]:
            print("COMPACT NEEDED before continuing the task.")
    show_usage()


if __name__ == "__main__":
    main()
