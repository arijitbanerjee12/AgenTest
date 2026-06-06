from pathlib import Path
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource, PydanticBaseSettingsSource


class LLMProviderConfig(BaseSettings):
    api_key: str = ""
    model: str = ""
    base_url: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3


class LLMConfig(BaseSettings):
    default_provider: Literal["openai", "anthropic", "groq", "azure", "bedrock", "ollama", "vllm"] = "groq"
    openai: LLMProviderConfig = LLMProviderConfig(api_key="${OPENAI_API_KEY}", model="gpt-4o")
    anthropic: LLMProviderConfig = LLMProviderConfig(api_key="${ANTHROPIC_API_KEY}", model="claude-sonnet-4-20250514")
    groq: LLMProviderConfig = LLMProviderConfig(api_key="${GROQ_API_KEY}", model="mixtral-8x7b-32768")
    azure: LLMProviderConfig = LLMProviderConfig(model="gpt-4o")
    bedrock: LLMProviderConfig = LLMProviderConfig(model="anthropic.claude-sonnet-4")
    ollama: LLMProviderConfig = LLMProviderConfig(base_url="http://localhost:11434", model="llama3")
    vllm: LLMProviderConfig = LLMProviderConfig(base_url="http://localhost:8000", model="meta-llama/Llama-3.1-8B")


class AgentConfig(BaseSettings):
    coordinator_model: str = "gpt-4o"
    writer_model: str = "gpt-4o-mini"
    executor_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o"


class PromptsConfig(BaseSettings):
    validation_dir: list[str] = [
        "agentest/artifacts/prompts/validation",
        "tests/prompts/validation",
    ]


class StorageConfig(BaseSettings):
    results_backend: Literal["sqlite", "postgresql"] = "sqlite"
    sqlite_path: str = "~/.agentest/results.db"
    postgres_dsn: Optional[str] = None
    artifact_store: Literal["local", "s3"] = "local"
    artifact_path: str = "~/.agentest/artifacts"
    s3_bucket: Optional[str] = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTEST_",
        env_nested_delimiter="__",
        yaml_file="agentest.config.yaml",
        secrets_dir="~/.agentest/secrets",
        extra="ignore",
    )

    project_name: str = "AgenTest"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    llm: LLMConfig = LLMConfig()
    agents: AgentConfig = AgentConfig()
    prompts: PromptsConfig = PromptsConfig()
    storage: StorageConfig = StorageConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_source = YamlConfigSettingsSource(settings_cls)
        return (yaml_source, init_settings, env_settings, file_secret_settings)


def load_config(path: str | Path = "agentest.config.yaml") -> Settings:
    path = Path(path).expanduser().resolve()
    if path.exists():
        return Settings(_yaml_file=str(path))
    return Settings()
