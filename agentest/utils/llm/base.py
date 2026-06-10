from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


class BaseLLMProvider(ABC):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        ...

    @abstractmethod
    def generate_messages(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
