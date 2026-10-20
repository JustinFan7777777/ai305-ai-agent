"""Save announcement facts in a conversation and restore it after restarting.
Change only the venue after resuming, then ask for an announcement.
Check that the new venue replaces the old one while the other facts remain.

Set DASHSCOPE_API_KEY. Run these commands in separate processes:
python lab6_resume.py new session.jsonl
python lab6_resume.py resume session.jsonl
Enter /exit to stop. Use a new file path for each new conversation.
"""

import argparse
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from lab6_common import call_model, connect

SYSTEM = (
    "You help draft a short course announcement using facts supplied in the conversation."
    " Follow the user's current request: organize facts first, and draft only when asked."
    " When a fact changes, use its latest value and retain the other supplied facts."
    " Do not invent details or publish the announcement. Keep replies concise."
)


class SessionHeader(BaseModel):
    type: Literal["session"] = "session"
    version: Literal[1] = 1
    cwd: str


class MessageEntry(BaseModel):
    type: Literal["message"] = "message"
    message: dict[str, Any]


def append_message(path: Path, message: dict[str, Any]) -> None:
    # 包装为带有 type 标记的记录，方便恢复时区分消息记录。
    entry = MessageEntry(message=message)

    # 使用追加模式，确保不会覆盖已有会话内容。
    with path.open("a", encoding="utf-8") as file:
        file.write(entry.model_dump_json() + "\n")


def load_session(path: Path) -> tuple[SessionHeader, list[dict[str, Any]]]:
    # 只读取并校验 JSONL；恢复历史本身不应该调用模型。
    lines = path.read_text(encoding="utf-8").splitlines()

    if not lines:
        raise ValueError("Session file is empty.")

    # 第一行是会话头，后续各行是消息记录。
    header = SessionHeader.model_validate_json(lines[0])

    messages: list[dict[str, Any]] = []

    for line in lines[1:]:
        if not line.strip():
            continue

        entry = MessageEntry.model_validate_json(line)
        messages.append(entry.message)

    return header, messages


def continue_session(client, model: str, path: Path, history: list[dict], request: str) -> list[dict]:
    # system 只用于本次模型调用，不保存进可恢复的消息历史。
    user = {"role": "user", "content": request}
    append_message(path, user)

    messages = [
        {"role": "system", "content": SYSTEM},
        *history,
        user,
    ]

    reply = call_model(client, model, messages)
    append_message(path, reply)
    print("ASSISTANT:", reply.get("content") or "")

    return [*history, user, reply]


def main() -> None:
    # Expect 2 saved messages before exit, 2 restored messages, and 4 after the next reply.
    # Loading history alone must not call the model; only a new user message does.
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["new", "resume"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    client, model = connect()
    if args.command == "new":
        with args.path.open("x", encoding="utf-8") as file:
            file.write(SessionHeader(cwd=str(Path.cwd())).model_dump_json() + "\n")
        history = []
        print("NEW SESSION:", args.path.resolve())
        print("请在下方输入：周六 14:00–16:00，A201，Python 工作坊，20 个名额，自带电脑。请先整理这些信息，不要写公告。")
        print("收到回复后，输入 /exit 退出，再运行以下命令恢复会话：")
        print(f'python lab6_resume.py resume "{args.path}"')
    else:
        _, history = load_session(args.path)
        print(f"RESTORED: {len(history)} messages")
        print("请在下方输入：地点改为 B305。请根据前面的信息写一则简短公告。")
        print("检查公告是否使用 B305，并保留周六 14:00–16:00、Python 工作坊、20 个名额和自带电脑。")
    print("每次输入消息会调用一次模型，消息和回复会自动保存；输入 /exit 退出。")
    while True:
        try:
            request = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if request == "/exit":
            break
        if not request:
            continue
        history = continue_session(client, model, args.path, history, request)
        saved_lines = len(args.path.read_text(encoding="utf-8").splitlines()) - 1
        print(f"SAVED: {saved_lines} messages -> {args.path}")


if __name__ == "__main__":
    try:
        main()
    except NotImplementedError as error:
        raise SystemExit(f"INCOMPLETE: implement {error} before running this exercise.")
