from typing import Any
from anthropic import Anthropic
from agentest.llm.base import BaseLLMProvider, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._client = Anthropic(api_key=config.get("api_key"))
        self._model = config.get("model", "claude-sonnet-4-20250514")

    @property
    def name(self) -> str:
        return "anthropic"

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.generate_messages([{"role": "user", "content": prompt}], **kwargs)

    def generate_messages(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        system = None
        chat_messages = messages
        if messages and messages[0].get("role") == "system":
            system = messages[0]["content"]
            chat_messages = messages[1:]

        response = self._client.messages.create(
            model=kwargs.get("model", self._model),
            messages=chat_messages,
            system=system,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.7),
        )
        return LLMResponse(
            content=response.content[0].text if response.content else "",
            model=response.model,
            provider=self.name,
            usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
            if response.usage
            else {},
            raw=response,
        )
