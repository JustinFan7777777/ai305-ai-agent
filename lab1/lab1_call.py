"""练习二：观察一次真实 Chat Completions 调用的请求与回复。"""

import json
import os

SYSTEM_PROMPT = "你是一个 AI305 课程助教，请简洁回答。"


def build_messages(user_text: str) -> list[dict[str, str]]:
    """TODO：返回消息列表，先放 system 指令，再放用户的消息。"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text}
    ]


def call_once(client, messages: list[dict[str, str]], model: str) -> dict:
    """TODO：调用一次 Chat Completions，将输出上限设为 256 token。

    返回包含 model、messages、reply、finish_reason 和 usage 的字典。
    messages 保存本次发送的消息副本，避免后续修改历史时改变这条记录。
    使用 completion.usage.model_dump() 将用量信息转换为字典。
    finish_reason 表示结束原因："stop" 表示正常结束；"length" 表示
    达到输出 token 上限，回复可能尚未写完。
    usage 中，prompt_tokens 是输入 token 数，completion_tokens 是输出
    token 数，total_tokens 是两者之和。token 数不等于字数或单词数。
    本练习传入 extra_body={"enable_thinking": False}，关闭 Qwen 的思考模式。
    调用记录中不要包含 API Key 或 HTTP 请求头。
    """

    completion = client.chat.completions.create(
        model=model, # e.g. qwen3.8-flash
        messages=messages, # conversation script
        max_tokens=256, # reply length <= 256 tokens
        extra_body={"enable_thinking": False}, # turn off Qwen's thinking mode
    )

    choice = completion.choices[0]
    # take the first one if API return several candidate replies

    return {
        "model": model, # model name
        "messages": [dict(m) for m in messages], # copy of the messages
        "reply": choice.message.content, # model's text answer
        "finish_reason": choice.finish_reason, # "stop" or "length"
        "usage": completion.usage.model_dump(), # token counts as a plain dict
    }


def create_client():
    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url=os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        timeout=30.0,
        max_retries=0,
    )


def main() -> None:
    client = create_client()
    model = os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash")
    messages = build_messages("什么是终端？")
    print("Request messages:")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    trace = call_once(client, messages, model)
    print(json.dumps(trace, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
