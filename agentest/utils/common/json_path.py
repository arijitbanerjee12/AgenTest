import re
from typing import Any

_SEGMENT_RE = re.compile(r"([^.[\]]+)|\[(\d+)]")


def _parse_path(path: str) -> list[tuple[str, int | None]]:
    parts = []
    for match in _SEGMENT_RE.finditer(path):
        key = match.group(1)
        idx = int(match.group(2)) if match.group(2) is not None else None
        if idx is not None:
            parts.append((key, idx))
        elif key.isdigit():
            parts.append((key, int(key)))
        else:
            parts.append((key, None))
    return parts


def get_value(data: Any, path: str) -> Any:
    current = data
    for key, idx in _parse_path(path):
        if isinstance(current, dict):
            current = current[key]
        elif isinstance(current, list):
            if idx is not None:
                current = current[idx]
            else:
                current = current[int(key)]
        else:
            raise KeyError(f"Cannot traverse into {type(current).__name__} with key '{key}'")
    return current


def set_value(data: Any, path: str, value: Any) -> dict | list:
    parts = _parse_path(path)
    current = data

    for i, (key, idx) in enumerate(parts):
        is_last = i == len(parts) - 1
        next_key, next_idx = parts[i + 1] if not is_last else (None, None)

        if isinstance(current, list) and idx is not None:
            while idx >= len(current):
                if next_idx is not None and not is_last:
                    current.append([])
                else:
                    current.append({})
            if is_last:
                current[idx] = value
                return data
            next_container = current[idx]
            if next_container is None:
                next_container = [] if next_idx is not None else {}
                current[idx] = next_container
            current = next_container

        elif isinstance(current, dict):
            raw_key: str | int = idx if idx is not None else key
            if is_last:
                current[raw_key] = value
                return data
            next_container = current.get(raw_key) if isinstance(raw_key, str) else (
                current.get(raw_key) if raw_key in current else None
            )
            if next_container is None:
                if next_idx is not None:
                    current[raw_key] = []
                else:
                    current[raw_key] = {}
                next_container = current[raw_key]
            current = next_container
        else:
            raise KeyError(f"Cannot traverse into {type(current).__name__} at '{key}'")

    return data
