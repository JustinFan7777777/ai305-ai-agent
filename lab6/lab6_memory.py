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
    # AGENTS.md 是外部记忆文件；每次运行时重新读取最新内容。
    return path.read_text(encoding="utf-8")


def write_announcement(client, model: str, request: str, memory: str) -> dict:
    # SYSTEM 定义总体职责，memory 提供项目级写作规则。
    system_message = (
        f"{SYSTEM}\n\n"
        "PROJECT WRITING RULES:\n"
        f"{memory}"
    )

    # 每次调用都是新会话，不复用之前的对话历史。
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": request},
    ]

    return call_model(client, model, messages)


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
