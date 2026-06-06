# Groq API Mock Server

A lightweight FastAPI mock that mimics the Groq chat completions API. No API key, no real LLM calls — returns canned responses instantly.

## Quick Start

```bash
cd agentest_app/groq_api_mock
pip install fastapi uvicorn pydantic
uvicorn groq_api_mock.app:app --port 8001 --reload

# Health check
curl http://localhost:8001/health

# Chat completion
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'

# Streaming
curl -X POST http://localhost:8001/v1/chat/completions/stream \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hi"}],"stream":true}'
```

## Supported Features

| Feature | Endpoint | Notes |
|---|---|---|
| Chat completion | `POST /v1/chat/completions` | Returns mock response instantly |
| Streaming | `POST /v1/chat/completions/stream` | Word-by-word SSE stream |
| Tool calls | `POST /v1/chat/completions` | Include `tools` array → mock `tool_calls` in response |
| JSON mode | `POST /v1/chat/completions` | Set `response_format.type: json_object` → JSON content |
| Model listing | `GET /v1/models` | Returns 3 mock models |
| Health | `GET /health` | Always `{"status": "ok"}` |

## Config

Set env vars to tune behavior:

- `MOCK_DELAY_SECONDS` — simulated latency (default: `0.05`)
- `MOCK_DELAY_ENABLED` — set to `false` to disable artificial delay

## Port

Runs on **8001** by default to avoid conflict with the real proxy on 8000.
