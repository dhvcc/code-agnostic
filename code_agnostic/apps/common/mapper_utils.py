"""Shared coercion helpers for MCP mappers.

Editors whose MCP config uses the same shapes share these instead of
re-implementing them per mapper. Editors with genuinely different semantics
(e.g. Copilot's float/negative timeout handling, Codex's seconds-based timeout)
keep their own local helpers.
"""

from typing import Any


def as_command_list(value: Any) -> list[str]:
    """A command/args value that may be a list or a single string."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def as_str_dict(value: Any) -> dict[str, str]:
    """A string-to-string mapping (env/headers), or empty if not a dict."""
    return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else {}


def coerce_int_timeout_ms(value: Any) -> int | None:
    """A plain integer millisecond timeout; rejects bools and non-ints."""
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    return None
