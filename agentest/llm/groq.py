from typing import Any
from groq import Groq
from agentest.llm.base import BaseLLMProvider, LLMResponse


class GroqProvider(BaseLLMProvider):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._client = Groq(api_key=config.get("api_key"))
        self._model = config.get("model", "mixtral-8x7b-32768")

    @property
    def name(self) -> str:
        return "groq"

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.generate_messages([{"role": "user", "content": prompt}], **kwargs)

    def generate_messages(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=kwargs.get("model", self._model),
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
            if response.usage
            else {},
            raw=response,
        )
