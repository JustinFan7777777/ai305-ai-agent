"""Exercise 2: Generate with Qwen3-0.6B using Transformers.

Run: uv run python lab2_generation.py
Download the model with the hf CLI; see the slides. Runs on CPU from cache.
Change PROMPT or SEED below and compare the outputs.
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen3-0.6B"
REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
PROMPT = "Give one short tip for learning Python."
SEED = 8


def select_token(logits: torch.Tensor, mode: str) -> int:
    """TODO: Choose one token ID from a 1-D vector of vocabulary logits.

    Greedy: logits.argmax().item().
    Sample: torch.softmax(logits / 0.7, dim=-1), then torch.multinomial(probs, 1).item().
    """
    raise NotImplementedError


@torch.inference_mode()
def generate(model, input_ids, eos_token_ids, mode, max_new_tokens=32):
    """TODO: Return (new_token_ids, finish), where finish is "eos" or "length".

    Call model(input_ids, use_cache=False).logits[0, -1] for next-token scores.
    Select a token; stop if it is in eos_token_ids (do not include EOS in the result).
    Otherwise append it with torch.cat([input_ids, input_ids.new_tensor([[token]])], dim=1).
    Repeat up to max_new_tokens. Do not call model.generate().
    """
    raise NotImplementedError


def main() -> None:
    print(f"Loading {MODEL_ID} on CPU...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=REVISION, dtype=torch.float32, local_files_only=True,
    ).eval()
    input_ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": PROMPT}],
        add_generation_prompt=True, enable_thinking=False, return_tensors="pt",
    )
    eos_ids = model.generation_config.eos_token_id
    if isinstance(eos_ids, int):
        eos_ids = [eos_ids]
    print(f"Prompt: {PROMPT}")
    for mode, limit in (("greedy", 32), ("sample", 32), ("greedy", 4)):
        torch.manual_seed(SEED)
        ids, finish = generate(model, input_ids, eos_ids, mode, limit)
        print(f"\n{mode}, output limit={limit} | Finish: {finish}")
        print("Token IDs:", ids)
        print("Text:", tokenizer.decode(ids, skip_special_tokens=True))


if __name__ == "__main__":
    main()
