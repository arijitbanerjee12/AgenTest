from typing import Any
from agentest.utils.llm.base import BaseLLMProvider
from agentest.utils.llm.openai import OpenAIProvider
from agentest.utils.llm.anthropic import AnthropicProvider
from agentest.utils.llm.groq import GroqProvider


class LLMRegistry:
    _providers: dict[str, type[BaseLLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[BaseLLMProvider]) -> None:
        cls._providers[name] = provider_cls

    @classmethod
    def get(cls, name: str, config: dict[str, Any]) -> BaseLLMProvider:
        provider_cls = cls._providers.get(name)
        if not provider_cls:
            raise ValueError(f"Unknown LLM provider: {name}. Available: {list(cls._providers.keys())}")
        return provider_cls(config)

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())


LLMRegistry.register("openai", OpenAIProvider)
LLMRegistry.register("anthropic", AnthropicProvider)
LLMRegistry.register("groq", GroqProvider)
