"""Exercise 1: Count tokens in the three bundled JSONL conversations.

Run: uv run python lab2_tokens.py
Download the model with the hf CLI; see the slides. Loads cached files only.
"""
import json
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent
MODEL_ID = "Qwen/Qwen3-0.6B"
REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


def count_conversation(tokenizer, messages: list[dict]) -> int:
    """TODO: Apply the chat template, then encode the result and count token IDs.

    Use tokenize=False, add_generation_prompt=False, enable_thinking=False.
    tokenizer.encode(text, add_special_tokens=False) returns a list of IDs.
    """

    # count the number of tokens in the conversation
    # by applying the chat template ad encoding the result with the tokenizer
    text = tokenizer.apply_chat_template(
        messages, # list of messages
        tokenize=False, # do not tokenize the result
        add_generation_prompt=False, # do not add generation prompt
        enable_thinking=False, # do not enable thinking
    )

    # encode the text and count the number of token IDs
    token_ids = tokenizer.encode(
        text, # text to encode
        add_special_tokens=False, # do not add special tokens
    )

    return len(token_ids) # return the number of token IDs


def main() -> None:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, local_files_only=True)
    for size in ("short", "medium", "long"):
        path = ROOT / "data" / f"conversation_{size}.jsonl"
        with path.open(encoding="utf-8") as source:
            messages = [json.loads(line) for line in source if line.strip()]
        total = count_conversation(tokenizer, messages)
        print(f"{path.name} | Messages: {len(messages)} | Tokens: {total}")


if __name__ == "__main__":
    main()
