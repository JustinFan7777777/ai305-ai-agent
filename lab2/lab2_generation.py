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

    # use greedy decoding -> select the token with the highest logit
    if mode == "greedy":
        # argmax() returns the index of the maximum value in the logits tensor
        # then item() converts the tensor to a Python integer
        return int(logits.argmax().item())

    # use sampling decoding -> sample a token from the probability distribution
    if mode == "sample":
        # temperature scaling; divide logits by 0.7 -> emplify the differences between logits -> make the distribution sharper
        # another interpretation: lower temperature -> less active / creative -> more deterministic output
        scaled_logits = logits / 0.7

        # using softmax to convert: logits -> probabilities
        # softmax guarantees that the sum of all probabilities equals 1, and each is in the range [0, 1]
        # dim=-1: apply softmax along the last dimension of the logits tensor, which corresponds to the vocabulary dimension
        probabilities = torch.softmax(scaled_logits, dim=-1)

        # sample a token ID from the probablity distribution
        # 1 means we want to sample only one token ID
        # item() helps convert the tensor to a Python integer
        return int(torch.multinomial(probabilities, 1).item())

    raise ValueError(f"Unknown decoding mode: {mode}")

    


@torch.inference_mode()
def generate(model, input_ids, eos_token_ids, mode, max_new_tokens=32):
    """TODO: Return (new_token_ids, finish), where finish is "eos" or "length".

    Call model(input_ids, use_cache=False).logits[0, -1] for next-token scores.
    Select a token; stop if it is in eos_token_ids (do not include EOS in the result).
    Otherwise append it with torch.cat([input_ids, input_ids.new_tensor([[token]])], dim=1).
    Repeat up to max_new_tokens. Do not call model.generate().
    """

    # initialize the new token IDs list to store the generated token IDs
    new_token_ids = []

    # loop for generating new tokens up to the maximum limit
    for _ in range(max_new_tokens):
        # get the logits for the next token by calling the model with the current input_ids
        outputs = model(input_ids, use_cache=False)

        # get the logits for the last token in the sequence
        # [0, -1] selects the first batch (batch size = 1) and the last token in the sequence
        # next_token_logits is a 1-D tensor of shape (vocab_size,) containing the logits for each token in the vocabulary
        next_token_logits = outputs.logits[0, -1]

        # we have already defined two decoding modes: greedy & sample
        # select a token ID based on the specified decoding mode
        token = select_token(next_token_logits, mode)

        if token in eos_token_ids:
            # if the selected token is an EOS token, we stop generation and return the result
            # new_tensor creates a new tensor from the list of new token IDs
            return input_ids.new_tensor(new_token_ids), "eos"
        # if the selected token is not an EOS token, we continue generation

        # append the selected token to the list of new token IDs
        next_token = input_ids.new_tensor([[token]])

        # concatenate the new token to the existing input_ids tensor along the sequence dimension (dim=1)
        input_ids = torch.cat([input_ids, next_token], dim=1)

        # update the input_ids with the new token
        new_token_ids.append(token)

    # if we reach the maximum number of new tokens without encountering an EOS token
    # we return the generated token IDs and indicate that the generation stopped due to reaching the length limit
    return input_ids.new_tensor(new_token_ids), "length"



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
    # GenerationConfig is optional in the Transformers type definitions.
    generation_config = model.generation_config
    if generation_config is None:
        raise RuntimeError("The model does not have a generation config.")

    # EOS IDs tell the generation loop when the model has finished its reply.
    eos_ids = generation_config.eos_token_id
    if eos_ids is None:
        raise RuntimeError("The model does not define an EOS token ID.")
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
