"""Frontend environment parsing helpers."""

from __future__ import annotations

import os

_FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(name: str, default: bool) -> bool:
    """Parse bool env with permissive false tokens."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _FALSE_VALUES


def env_int(name: str, default: int, minimum: int = 0) -> int:
    """Parse int env with fallback and lower bound."""
    raw = os.environ.get(name)
    if raw is None:
        return max(default, minimum)
    try:
        return max(int(raw), minimum)
    except ValueError:
        return max(default, minimum)


def env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse comma-separated env value into non-empty trimmed tokens."""
    raw = os.environ.get(name)
    if raw is None:
        return default

    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    return items or default
