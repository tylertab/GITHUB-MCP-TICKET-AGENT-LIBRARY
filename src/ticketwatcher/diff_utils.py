"""Lightweight helpers for diff parsing and application."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from .github_api import get_file_text
from .paths import is_path_allowed

_HUNK_RE = re.compile(r'^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@')


def parse_unified_diff(diff_text: str) -> Dict[str, List[Dict[str, Any]]]:
    files: Dict[str, List[Dict[str, Any]]] = {}
    lines = diff_text.splitlines()
    index = 0
    current_file: str | None = None

    while index < len(lines):
        line = lines[index]
        if line.startswith('--- a/'):
            if index + 1 < len(lines) and lines[index + 1].startswith('+++ b/'):
                current_file = lines[index + 1][6:]
                files.setdefault(current_file, [])
                index += 2
                continue

        match = _HUNK_RE.match(line)
        if match and current_file:
            old_start = int(match.group(1))
            old_len = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_len = int(match.group(4) or "1")
            hunk: Dict[str, Any] = {
                "old_start": old_start,
                "old_len": old_len,
                "new_start": new_start,
                "new_len": new_len,
                "lines": [],
            }
            files[current_file].append(hunk)
            index += 1
            while index < len(lines) and not lines[index].startswith('@@') and not lines[index].startswith('--- a/'):
                hunk["lines"].append(lines[index])
                index += 1
            continue

        index += 1

    return files


def apply_hunks_to_text(original: str, hunks: List[Dict[str, Any]]) -> str:
    source = original.splitlines()
    output: List[str] = []
    cursor = 1

    for hunk in hunks:
        old_start = hunk["old_start"]
        while cursor < old_start:
            output.append(source[cursor - 1])
            cursor += 1

        for line in hunk["lines"]:
            if line.startswith(' '):
                output.append(line[1:])
                cursor += 1
            elif line.startswith('-'):
                cursor += 1
            elif line.startswith('+'):
                output.append(line[1:])
            else:
                output.append(line)
                cursor += 1

    while cursor <= len(source):
        output.append(source[cursor - 1])
        cursor += 1

    return "\n".join(output)


def apply_unified_diff(
    *,
    base_ref: str,
    diff_text: str,
    allowed_prefixes: Iterable[str] | None,
) -> Dict[str, str]:
    parsed = parse_unified_diff(diff_text)
    updated: Dict[str, str] = {}

    for path, hunks in parsed.items():
        if not is_path_allowed(path, allowed_prefixes):
            raise ValueError(f"Path not allowed: {path}")
        current = get_file_text(path, base_ref)
        updated[path] = apply_hunks_to_text(current, hunks)

    return updated


def diff_stats(diff_text: str) -> Tuple[int, int]:
    files: set[str] = set()
    changes = 0
    for line in diff_text.splitlines():
        if line.startswith('+++ b/'):
            files.add(line[6:])
        elif line.startswith('+') and not line.startswith('+++'):
            changes += 1
        elif line.startswith('-') and not line.startswith('---'):
            changes += 1
    return len(files), changes

