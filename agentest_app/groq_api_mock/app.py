import asyncio
import time
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from schemas.chat import (
    ChatCompletionRequest,
    mock_response,
    mock_chunk,
)

app = FastAPI(title="Groq API Mock", version="0.1.0", description="Mock Groq server for testing — no API key required")

DELAY_ENABLED = True
DELAY_SECONDS = 0.05


@app.post("/v1/chat/completions")
def create_chat_completion(req: ChatCompletionRequest):
    if DELAY_ENABLED:
        time.sleep(DELAY_SECONDS)
    return mock_response(req)


@app.post("/v1/chat/completions/stream")
async def create_chat_completion_stream(req: ChatCompletionRequest):
    chunks = mock_chunk(req)

    async def generate():
        for chunk in chunks:
            yield chunk["choices"][0]["delta"].get("content", "") or "\n"
            await asyncio.sleep(DELAY_SECONDS)
        # final usage chunk
        yield "\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "openai/gpt-oss-120b", "object": "model", "created": 1700000000},
            {"id": "llama-3.3-70b-versatile", "object": "model", "created": 1700000001},
            {"id": "mixtral-8x7b-32768", "object": "model", "created": 1700000002},
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}
