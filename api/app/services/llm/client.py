import json
from typing import Any

from openai import OpenAI, OpenAIError


class AIClientError(Exception):
    pass


def call_chat_completion_content(
    model_config: dict,
    messages: list[dict[str, str]],
    *,
    timeout: int,
    temperature: float,
    response_format: dict[str, str] | None = None,
) -> str:
    client = OpenAI(
        api_key=str(model_config["apiKey"]),
        base_url=str(model_config["baseUrl"]).rstrip("/"),
        timeout=timeout,
    )
    payload: dict[str, Any] = {
        "model": model_config["model"],
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        response = client.chat.completions.create(**payload)
    except OpenAIError as exc:
        raise AIClientError(f"AI 模型调用失败：{exc}") from exc
    except Exception as exc:
        raise AIClientError(f"AI 模型调用异常：{exc}") from exc

    if not response.choices:
        raise AIClientError("AI 模型没有返回内容。")

    content = response.choices[0].message.content
    if not content:
        raise AIClientError("AI 模型没有返回内容。")
    return content


def call_chat_completion_json(
    model_config: dict,
    messages: list[dict[str, str]],
    *,
    timeout: int,
    temperature: float,
) -> dict:
    content = call_chat_completion_content(
        model_config,
        messages,
        timeout=timeout,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIClientError("AI 返回内容不是合法 JSON。") from exc
    if not isinstance(parsed, dict):
        raise AIClientError("AI 返回内容结构无效。")
    return parsed
