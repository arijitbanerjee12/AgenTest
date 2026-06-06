from agentest.config import Settings
from agentest.llm import LLMRegistry


class AgenTestEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            provider_cfg = getattr(self.settings.llm, self.settings.llm.default_provider)
            self._llm = LLMRegistry.get(
                self.settings.llm.default_provider,
                provider_cfg.model_dump(),
            )
        return self._llm

    def run(self) -> None:
        ...
