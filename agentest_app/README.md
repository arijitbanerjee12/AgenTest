# AgenTest — Dummy Applications

Each subfolder is a standalone dummy application you can test with the AgenTest framework.

| App | Description | Port |
|---|---|---|
| [groq_api_mock](./groq_api_mock) | Mock Groq LLM API — no API key needed, returns canned responses | 8001 |
| _(more coming)_ | | |

## How to use

1. Start the app you want to test (see its README)
2. Run tests from the project root:
   ```bash
   uv run pytest tests/test_runner.py -k "<app>" -v
   ```
