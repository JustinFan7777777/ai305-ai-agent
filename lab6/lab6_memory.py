"""Load writing rules from a project file and include them in a model request.
Generate an event announcement, then change the rules and compare the output.
Each run starts without conversation history.

Run: python lab6_memory.py. Set DASHSCOPE_API_KEY (same setup as Lab 5).
Edit the word limit in data/writing/AGENTS.md from 120 words to 60 words and rerun.
"""

from pathlib import Path

from lab6_common import ROOT, call_model, connect

SYSTEM = (
    "You draft announcements using the supplied facts and writing rules."
    " Do not invent event details or send the announcement."
)
MEMORY_PATH = ROOT / "data/writing/AGENTS.md"


def load_memory(path: Path) -> str:
    # TODO: Read the project rules as UTF-8 and return the text.
    raise NotImplementedError("load_memory")


def write_announcement(client, model: str, request: str, memory: str) -> dict:
    # TODO: Build a system message with SYSTEM and the loaded memory.
    # Add the user request and call call_model(client, model, messages).
    # Return its assistant-message dict. Each run starts with no conversation history.
    raise NotImplementedError("write_announcement")


def main() -> None:
    # Compare the loaded rules and announcement after changing only the word limit.
    client, model = connect()
    memory = load_memory(MEMORY_PATH)
    print("LOADED RULES:\n" + memory)
    request = (
        "Write an announcement for a free Python workshop on Saturday, 14:00-16:00,"
        " in Room A201. There are 20 places; participants should bring a laptop."
        " RSVP to workshop@example.test. These are fictional event details."
    )
    reply = write_announcement(client, model, request, memory)
    print("\nANNOUNCEMENT:\n" + (reply.get("content") or ""))
    print("WORD COUNT (whitespace-separated):", len((reply.get("content") or "").split()))


if __name__ == "__main__":
    try:
        main()
    except NotImplementedError as error:
        raise SystemExit(f"INCOMPLETE: implement {error} before running this exercise.")
