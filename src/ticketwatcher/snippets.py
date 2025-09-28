"""Helpers for fetching contextual code snippets from the repository."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from .github_api import file_exists, get_file_text
from .paths import is_path_allowed


def fetch_slice(
    path: str,
    *,
    base_ref: str,
    center_line: int | None,
    around_lines: int,
    allowed_prefixes: Iterable[str] | None,
) -> Dict[str, Any] | None:
    if not is_path_allowed(path, allowed_prefixes) or not file_exists(path, base_ref):
        return None

    content = get_file_text(path, base_ref)
    lines = content.splitlines()
    total = len(lines)

    if center_line is None or center_line < 1 or center_line > total:
        start = 1
        end = min(total, 2 * around_lines)
    else:
        start = max(1, center_line - around_lines)
        end = min(total, center_line + around_lines)

    return {
        "path": path,
        "start_line": start,
        "end_line": end,
        "code": "\n".join(lines[start - 1 : end]),
    }


def fetch_symbol_slice(
    path: str,
    *,
    base_ref: str,
    symbol: str,
    around_lines: int,
    allowed_prefixes: Iterable[str] | None,
) -> Dict[str, Any] | None:
    if not symbol:
        return None
    if not is_path_allowed(path, allowed_prefixes) or not file_exists(path, base_ref):
        return None

    content = get_file_text(path, base_ref)
    lines = content.splitlines()
    definition_pattern = re.compile(rf'^\s*(def|class)\s+{re.escape(symbol)}\b')

    target_line = None
    for index, line in enumerate(lines, start=1):
        if definition_pattern.search(line):
            target_line = index
            break

    if target_line is None:
        for index, line in enumerate(lines, start=1):
            if symbol in line:
                target_line = index
                break

    if target_line is None:
        return None

    start = max(1, target_line - around_lines)
    end = min(len(lines), target_line + around_lines)
    return {
        "path": path,
        "start_line": start,
        "end_line": end,
        "code": "\n".join(lines[start - 1 : end]),
    }

