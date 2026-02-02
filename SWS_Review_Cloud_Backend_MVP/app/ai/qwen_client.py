import json
import httpx
from ..settings import settings

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def chat_completion(messages: list[dict], model: str | None = None, response_format: dict | None = None) -> str:
    """Call Qwen chat API. Returns content string."""
    if not settings.QWEN_API_KEY:
        raise ValueError("QWEN_API_KEY not set")
    model = model or settings.QWEN_MODEL
    body = {"model": model, "messages": messages}
    if response_format:
        body["response_format"] = response_format
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{DASHSCOPE_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {settings.QWEN_API_KEY}"},
            json=body,
        )
        r.raise_for_status()
        data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content


def chat_json(messages: list[dict], model: str | None = None) -> dict:
    """Call Qwen and parse response as JSON. Retries once on parse error."""
    content = chat_completion(messages, model=model, response_format={"type": "json_object"})
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        content2 = chat_completion(messages, model=model)
        return json.loads(content2)
