from pathlib import Path
from typing import Any
from agentest.config.settings import load_config


def resolve_prompt(name: str) -> str | None:
    config = load_config()
    for d in config.prompts.validation_dir:
        base = Path(d).expanduser().resolve()
        for ext in ["", ".txt", ".j2", ".jinja", ".prompt"]:
            if ext:
                candidate = base / f"{name}{ext}"
            else:
                candidate = base / name
            if candidate.exists() and candidate.is_file():
                return candidate.read_text(encoding="utf-8")
    return None


def _format_values(*values: Any) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return str(values[0])
    return "\n".join(f"Value {i+1}:\n{v}" for i, v in enumerate(values))


def _load_direct_path(path_str: str) -> str | None:
    p = Path(path_str).expanduser().resolve()
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return None


def build_llm_prompt(instruction: str, *values: Any) -> str:
    formatted = _format_values(*values)
    content = _load_direct_path(instruction) or resolve_prompt(instruction)
    if content is not None:
        if "{values}" in content:
            return content.replace("{values}", formatted).replace("{instruction}", "").strip()
        if "{instruction}" in content:
            return content.replace("{instruction}", instruction).replace("{values}", formatted).strip()
        return f"{content}\n\n{formatted}".strip()
    return f"{instruction}\n\n{formatted}".strip()
