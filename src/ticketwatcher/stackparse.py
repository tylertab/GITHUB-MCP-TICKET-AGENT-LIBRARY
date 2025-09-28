"""Utilities for extracting useful paths from issue descriptions and traces."""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from .paths import is_path_allowed, to_repo_relative

_RE_PY_FILELINE = re.compile(r'File\s+"([^"]+)"\s*,\s*line\s+(\d+)\b')
_RE_GENERIC_PATHLINE = re.compile(r'([^\s\'",)\]]+):(\d+)\b')
_RE_TARGET = re.compile(r'^\s*Target:\s*(.+?)\s*$', re.MULTILINE)


def _sanitize_path_token(token: str) -> str:
    token = (token or "").strip()
    token = token.strip('`"\'')
    return re.sub(r'[\'"\s,)\]>]+$', "", token)


def parse_stack_text(
    text: str,
    *,
    repo_root: str,
    repo_name: str,
    allowed_prefixes: Iterable[str] | None = None,
    limit: int = 5,
) -> List[Tuple[str, int | None]]:
    """Return repo-relative path/line pairs extracted from stack-like text."""
    results: List[Tuple[str, int | None]] = []
    if not text:
        return results

    lines = text.splitlines()

    def _record(raw_path: str, line_no: int | None) -> None:
        path = to_repo_relative(raw_path, repo_root, repo_name)
        if path and is_path_allowed(path, allowed_prefixes):
            results.append((path, line_no))

    for line in lines:
        match = _RE_PY_FILELINE.search(line)
        if not match:
            continue
        _record(match.group(1), int(match.group(2)))

    for line in lines:
        for match in _RE_GENERIC_PATHLINE.finditer(line):
            _record(match.group(1), int(match.group(2)))

    for match in _RE_TARGET.finditer(text):
        raw_full = _sanitize_path_token(match.group(1))
        if ":" in raw_full and raw_full.rsplit(":", 1)[-1].isdigit():
            raw_path, raw_line = raw_full.rsplit(":", 1)
            line_no = int(raw_line)
        else:
            raw_path, line_no = raw_full, None
        _record(raw_path, line_no)

    deduped: List[Tuple[str, int | None]] = []
    seen: set[Tuple[str, int]] = set()
    for path, line_no in results:
        key = (path, line_no or 0)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((path, line_no))
        if len(deduped) >= max(1, limit):
            break

    return deduped

