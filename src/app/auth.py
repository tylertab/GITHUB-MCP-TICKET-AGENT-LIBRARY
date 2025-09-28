"""Authentication helpers."""

from __future__ import annotations

from typing import Any, Dict

from .user_repo import load_user
from .utils.stringy import sanitize_string


def _normalize_user(record: Dict[str, Any] | None) -> Dict[str, Any]:
    if not record:
        return {"name": "", "email": ""}
    return {"name": record.get("name", ""), "email": record.get("email", "")}


def get_user_profile(user_id: int | None) -> Dict[str, str]:
    """Return a sanitized profile dictionary or ``{}`` when unavailable."""
    if user_id is None:
        return {}

    user = _normalize_user(load_user(user_id))
    name = sanitize_string(user["name"])
    email = sanitize_string(user["email"])

    if not name and not email:
        return {}

    return {"id": user_id, "name": name, "email": email}
