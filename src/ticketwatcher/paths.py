"""Shared helpers for working with repository paths and allowlists."""
from __future__ import annotations

import os
from typing import Iterable, List


def parse_allowed_paths_env(raw: str | None) -> List[str]:
    """Parse a comma-separated env string into normalized allowlist prefixes."""
    if raw is None:
        return ["src/"]

    raw_parts = [(part or "").strip() for part in raw.split(",")]
    parts = [p for p in raw_parts if p]
    allow_all = any(part == "" for part in raw_parts)

    normalized: List[str] = []
    for part in parts:
        normalized.append(_normalize_prefix(part))

    if not normalized:
        # Only treat it as "allow everything" when the env var is explicitly empty.
        return [""] if allow_all else ["src/"]

    if allow_all and "" not in normalized:
        normalized.append("")

    return normalized


def _normalize_prefix(prefix: str) -> str:
    """Ensure directory-like prefixes end with a slash for cheap prefix checks."""
    if not prefix:
        return ""
    if prefix.endswith("/"):
        return prefix
    # If the last path component looks like a filename (contains a dot), keep as-is.
    tail = prefix.split("/")[-1]
    return prefix if "." in tail else prefix + "/"


def allows_all_paths(prefixes: Iterable[str] | None) -> bool:
    """Return True when the allowlist permits touching any path."""
    if not prefixes:
        return True
    return any(prefix == "" for prefix in prefixes)


def is_path_allowed(path: str, prefixes: Iterable[str] | None) -> bool:
    """Simple prefix-based allowlist check for repo-relative paths."""
    if not path:
        return False
    if allows_all_paths(prefixes):
        return True
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes or [])


def to_repo_relative(path: str, repo_root: str, repo_name: str) -> str:
    """Convert an absolute path to repo-relative form when possible."""
    cleaned = (path or "").strip().replace("\\", "/")
    if not cleaned:
        return ""

    repo_token = f"/{repo_name}/" if repo_name else None
    if repo_token and repo_token in cleaned:
        cleaned = cleaned.split(repo_token, 1)[1]

    try:
        rel = os.path.relpath(cleaned, repo_root).replace("\\", "/")
    except Exception:
        rel = cleaned

    return rel.lstrip("./").lstrip("/")

