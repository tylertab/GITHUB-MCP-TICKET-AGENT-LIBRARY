from __future__ import annotations

from typing import Any


def sanitize_string(value: Any) -> str:
    """Trim whitespace from strings while tolerating ``None`` and non-strings."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()
