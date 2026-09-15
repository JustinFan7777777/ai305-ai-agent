"""Exercise 3: Stream local Qwen3 replies and measure time to first token.

Run: uv run python lab2_inference.py
Download the model with the hf CLI; see the slides. Shares Exercise 2's cache.
"""
import json
from pathlib import Path
from time import perf_counter

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

ROOT = Path(__file__).resolve().parent
MODEL_ID = "Qwen/Qwen3-0.6B"
REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"

FOLLOW_UP = "Summarize the topic of our conversation in one short English sentence."


class TimedStreamer(TextStreamer):
    """Provided: record generated-token arrivals and display the reply.

    Create streamer = TimedStreamer(tokenizer); pass streamer=streamer to model.generate.
    streamer.token_times stores each generated token's perf_counter() timestamp.
    """
    def __init__(self, tokenizer):
        super().__init__(tokenizer, skip_prompt=True, skip_special_tokens=True)
        self.token_times = []

    def put(self, value):
        if not self.next_tokens_are_prompt:
            self.token_times.append(perf_counter())
        super().put(value)


def run_inference(model, tokenizer, messages) -> dict:
    """TODO: Prepare input, stream one reply, and return text and timing metrics.

    Use the chat template with a generation prompt and thinking disabled.
    Implement generation here, then fill in the dictionary values below.
    pass a TimedStreamer object to streamer= in generate(), so you can record
    each token's arrival time
    """
    input_ids = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True,
        enable_thinking=False, return_tensors="pt",
    )
    # TODO: Implementation starts here
    # output_ids = model.generate ... 
    # output_text = tokenizer.decode ...

    return {
        "text": ...,           # str: decoded new tokens only.
        "input_tokens": ...,   # int: number of input tokens.
        "output_tokens": ...,  # int: number of new tokens, including EOS.
        "first_token_s": ...,  # float: first-token delay; None if no token arrived.
        "total_s": ...,        # float: total generation time in seconds.
    }


def main() -> None:
    print(f"Loading {MODEL_ID} on CPU...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=REVISION, dtype=torch.float32, local_files_only=True,
    ).eval()
    for size in ("short", "medium", "long"):
        path = ROOT / "data" / f"conversation_{size}.jsonl"
        with path.open(encoding="utf-8") as source:
            messages = [json.loads(line) for line in source if line.strip()]
        messages.append({"role": "user", "content": FOLLOW_UP})
        print(f"\n{path.name}")
        result = run_inference(model, tokenizer, messages)
        first_token_s = result["first_token_s"]
        first = f"{first_token_s:.3f} s" if first_token_s is not None else "not recorded"
        print(f"Input tokens: {result['input_tokens']}")
        print(f"First token: {first} | Total: {result['total_s']:.3f} s")
        print(f"Generated tokens (including EOS): {result['output_tokens']}")


if __name__ == "__main__":
    main()
