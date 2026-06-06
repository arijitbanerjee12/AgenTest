import time
import json
import uuid
from pydantic import BaseModel
from typing import Any


class ChatMessage(BaseModel):
    role: str
    content: str | None = None


class FunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ToolDefinition(BaseModel):
    type: str
    function: FunctionDefinition | None = None


class ResponseFormat(BaseModel):
    type: str = "text"


class ChatCompletionRequest(BaseModel):
    model: str = "openai/gpt-oss-120b"
    messages: list[ChatMessage]
    temperature: float | None = 1.0
    max_completion_tokens: int | None = 8192
    top_p: float | None = 1.0
    reasoning_effort: str | None = None
    stream: bool = False
    response_format: ResponseFormat | None = None
    stop: str | list[str] | None = None
    tools: list[ToolDefinition] | None = None

    def has_tools(self) -> bool:
        return bool(self.tools)

    def wants_json(self) -> bool:
        return self.response_format is not None and self.response_format.type == "json_object"

    def last_user_message(self) -> str:
        for m in reversed(self.messages):
            if m.role == "user" and m.content:
                return m.content
        return ""


def _mock_content(req: ChatCompletionRequest) -> str:
    if req.wants_json():
        return json.dumps({
            "response": f"You asked: {req.last_user_message()[:50]}",
            "model": req.model,
            "mock": True,
        }, indent=2)
    return f"This is a mock response to: {req.last_user_message()}"


def _mock_tool_calls(req: ChatCompletionRequest) -> list[dict]:
    calls = []
    for i, tool in enumerate(req.tools or []):
        calls.append({
            "id": f"call_{uuid.uuid4().hex[:16]}",
            "type": tool.type,
            "function": {
                "name": tool.function.name if tool.function else tool.type,
                "arguments": json.dumps({"query": req.last_user_message()[:100]}),
            },
        })
    return calls


def mock_response(req: ChatCompletionRequest) -> dict[str, Any]:
    resp_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    content = _mock_content(req)
    message: dict[str, Any] = {"role": "assistant", "content": content}

    if req.has_tools():
        message["tool_calls"] = _mock_tool_calls(req)

    return {
        "id": resp_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if req.has_tools() else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": sum(len(m.content or "") for m in req.messages) // 4,
            "completion_tokens": len(content) // 4,
            "total_tokens": 42,
        },
    }


def mock_chunk(req: ChatCompletionRequest) -> list[dict[str, Any]]:
    """Return a list of streaming chunks."""
    resp_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    content = _mock_content(req)
    now = int(time.time())

    usage_chunk = {
        "id": resp_id,
        "object": "chat.completion.chunk",
        "created": now,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
        "x_groq": {"usage": {"queue_time": 0.001}},
    }

    content_words = content.split()
    if not content_words:
        return [usage_chunk]

    chunks = []
    for i, word in enumerate(content_words):
        delta: dict[str, Any] = {"role": "assistant", "content": word + " "}
        if i == 0 and req.has_tools():
            delta["tool_calls"] = _mock_tool_calls(req)
        chunks.append({
            "id": resp_id,
            "object": "chat.completion.chunk",
            "created": now,
            "model": req.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        })

    chunks.append(usage_chunk)
    return chunks
