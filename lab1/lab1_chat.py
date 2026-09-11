"""练习三：在终端聊天程序中维护对话历史。

先完成练习二，并在当前终端中配置 DASHSCOPE_* 环境变量。
在解压后的 lab1/code/ 目录中运行 `uv run python lab1_chat.py`。
连续提问两次，观察第二次请求的 messages 中是否包含第一次的问题和回复。
输入 `exit` 结束对话。
"""

import json
import os

# 复用练习二的代码
from lab1_call import SYSTEM_PROMPT, call_once, create_client


def chat_turn(client, history: list[dict[str, str]], user_text: str,
              model: str) -> dict:
    """TODO：准备消息，调用一次模型，并保存成功完成的对话。

    将已有 history 和本次用户消息一起发送。
    调用成功后，原地更新 history，保存发送的消息及模型的 assistant 回复。
    如果 API 调用失败，不要修改 history。
    返回 call_once 生成的调用记录。
    """

    messages = history + [{"role": "user", "content": user_text}]
    # existing history + current user message = messages to send

    trace = call_once(client, messages, model)
    # call_once returns a dict with model, messages, reply, finish_reason, and usage

    history.extend([
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": trace["reply"]},
    ])
    # update history with the user message and assistant reply

    return trace


def chat_loop(client, model: str, read=input, write=print) -> None:
    """TODO：循环读取用户输入，并调用 chat_turn。

    初始历史只包含一条 system 消息，忽略空白输入。
    收到 'exit' 或 EOF（输入结束）时退出，不再发送请求。
    将每次调用记录打印为 JSON，其中应包含实际发送的消息。
    """

    # start with a history containing only the system message
    history: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        try:
            user_text = read()
        except EOFError:
            write()
            break
        if user_text is None: 
            break
        user_text = user_text.strip()
        if not user_text: # ignore blank / whitespace-only input
            continue
        if user_text == "exit":
            break
        trace = chat_turn(client, history, user_text, model) # call chat_turn to handle the conversation
        write(json.dumps(trace, ensure_ascii=False, indent=2)) # print the trace as JSON with proper formatting

def main() -> None:
    client = create_client()
    chat_loop(client, os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash"))


if __name__ == "__main__":
    main()
