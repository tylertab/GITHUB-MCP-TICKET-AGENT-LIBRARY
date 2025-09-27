from __future__ import annotations
import os
import re
import json
from typing import Any, Dict, List, Tuple

from .github_api import (
    get_default_branch,
    create_branch,
    create_or_update_file,
    create_pr,
    get_file_text,
    file_exists,              # add this small helper in github_api if you don’t have it yet
    add_issue_comment,         # optional but nice to have
)

from .agent_llm import TicketWatcherAgent  # the class we just finished


# --------- config knobs (can be env driven) ---------
TRIGGER_LABELS = set(os.getenv("TICKETWATCHER_TRIGGER_LABELS", "agent-fix,auto-pr").split(","))
BRANCH_PREFIX  = os.getenv("TICKETWATCHER_BRANCH_PREFIX", "agent-fix/")
PR_TITLE_PREF  = os.getenv("TICKETWATCHER_PR_TITLE_PREFIX", "agent: auto-fix for issue")
ALLOWED_PATHS  = [p.strip() for p in os.getenv("ALLOWED_PATHS", "src/,app/").split(",") if p.strip()]
MAX_FILES      = int(os.getenv("MAX_FILES", "4"))
MAX_LINES      = int(os.getenv("MAX_LINES", "200"))
AROUND_LINES   = int(os.getenv("DEFAULT_AROUND_LINES", "60"))

# ----------------------------------------------------


def _mk_branch(issue_number: int) -> str:
    return f"{BRANCH_PREFIX}{issue_number}"


# ---------- seed parsing & snippet fetch ----------

_TRACE_RE_1 = re.compile(r'File\s+"([^"]+\.py)"\s*,\s*line\s+(\d+)')
_TRACE_RE_2 = re.compile(r'((?:src|app)/[^\s:]+\.py):(\d+)')
_TARGET_HINT_RE = re.compile(r'^Target:\s*(\S+\.py)\s*$', re.MULTILINE)

def _paths_from_issue_text(text: str) -> List[Tuple[str, int | None]]:
    """Return list of (path, line_or_None) parsed from issue body."""
    out: List[Tuple[str, int | None]] = []
    if not text:
        return out
    for m in _TRACE_RE_1.finditer(text):
        out.append((m.group(1), int(m.group(2))))
    for m in _TRACE_RE_2.finditer(text):
        out.append((m.group(1), int(m.group(2))))
    m = _TARGET_HINT_RE.search(text)
    if m:
        out.append((m.group(1), None))
    # de-dupe, keep order
    seen = set()
    uniq = []
    for p, ln in out:
        key = (p, ln or 0)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((p, ln))
    return uniq[:5]  # bound the seed list


def _path_allowed(path: str) -> bool:
    return any(path.startswith(pfx if pfx.endswith("/") else pfx + "/") or path.startswith(pfx) for pfx in ALLOWED_PATHS)


def _fetch_slice(path: str, base: str, center_line: int | None, around: int) -> Dict[str, Any] | None:
    """Fetch ±around lines for a file (centered at center_line if given)."""
    if not _path_allowed(path) or not file_exists(path, base):
        return None
    content = get_file_text(path, base)
    lines = content.splitlines()
    n = len(lines)
    if center_line is None or center_line < 1 or center_line > n:
        # whole file is too big; return head slice
        start = 1
        end = min(n, 2 * around)
    else:
        start = max(1, center_line - around)
        end = min(n, center_line + around)
    code = "\n".join(lines[start - 1 : end])
    return {"path": path, "start_line": start, "end_line": end, "code": code}


def _fetch_symbol_slice(path: str, base: str, symbol: str, around: int) -> Dict[str, Any] | None:
    """Naive symbol search to find a 'def <symbol>' or occurrence and slice around it."""
    if not _path_allowed(path)or not file_exists(path, base):
        return None
    content = get_file_text(path, base)
    lines = content.splitlines()
    # Look for a definition first
    def_pat = re.compile(rf'^\s*(def|class)\s+{re.escape(symbol)}\b')
    idx = None
    for i, line in enumerate(lines, start=1):
        if def_pat.search(line):
            idx = i
            break
    if idx is None:
        # fallback: first occurrence
        for i, line in enumerate(lines, start=1):
            if symbol in line:
                idx = i
                break
    if idx is None:
        return None
    start = max(1, idx - around)
    end = min(len(lines), idx + around)
    code = "\n".join(lines[start - 1 : end])
    return {"path": path, "start_line": start, "end_line": end, "code": code}


# ---------- unified diff parsing / application ----------

_HUNK_RE = re.compile(r'^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@')

def _parse_unified_diff(diff_text: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse a unified diff into a dict: { path: [ {old_start, old_len, new_start, new_len, lines: [...]}, ... ] }
    Supports multi-file diffs for typical small patches.
    """
    files: Dict[str, List[Dict[str, Any]]] = {}
    cur_file = None
    cur_hunk = None
    lines = diff_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('--- a/'):
            # next line should be +++ b/<path>
            if i + 1 < len(lines) and lines[i + 1].startswith('+++ b/'):
                path = lines[i + 1][6:]
                cur_file = path
                files.setdefault(cur_file, [])
                i += 2
                continue
        m = _HUNK_RE.match(line)
        if m and cur_file:
            old_start = int(m.group(1))
            old_len   = int(m.group(2) or "1")
            new_start = int(m.group(3))
            new_len   = int(m.group(4) or "1")
            cur_hunk = {"old_start": old_start, "old_len": old_len, "new_start": new_start, "new_len": new_len, "lines": []}
            files[cur_file].append(cur_hunk)
            i += 1
            # collect hunk lines until next header/file
            while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('--- a/'):
                cur_hunk["lines"].append(lines[i])
                i += 1
            continue
        i += 1
    return files


def _apply_hunks_to_text(orig_text: str, hunks: List[Dict[str, Any]]) -> str:
    """
    Very small, forgiving hunk applier for typical patches produced by the agent.
    Assumes hunks are in ascending order and apply cleanly.
    """
    src = orig_text.splitlines()
    dst = []
    cursor = 1  # 1-based
    for h in hunks:
        old_start = h["old_start"]
        # copy unchanged lines up to the hunk
        while cursor < old_start:
            dst.append(src[cursor - 1])
            cursor += 1
        # consume old_len lines from src while reading hunk ops
        # build replacement block
        for ln in h["lines"]:
            if ln.startswith(' '):
                # context line: must match src
                dst.append(ln[1:])
                cursor += 1
            elif ln.startswith('-'):
                # deletion: skip in dst, advance src
                cursor += 1
            elif ln.startswith('+'):
                # addition: add to dst, do not advance src
                dst.append(ln[1:])
            else:
                # unknown marker, treat as context
                dst.append(ln)
                cursor += 1
    # copy the rest
    while cursor <= len(src):
        dst.append(src[cursor - 1])
        cursor += 1
    return "\n".join(dst)


def _apply_unified_diff(base_ref: str, diff_text: str) -> Dict[str, str]:
    """
    Fetch current file contents from base_ref, apply hunks, return {path: updated_text}.
    Rejects paths outside ALLOWED_PATHS.
    """
    parsed = _parse_unified_diff(diff_text)
    updated: Dict[str, str] = {}
    for path, hunks in parsed.items():
        if not _path_allowed(path):
            raise ValueError(f"Path not allowed: {path}")
        # if not file_exists(path, base_ref):
        #     raise ValueError(f"File does not exist on base: {path}")
        current = get_file_text(path, base_ref)
        new_text = _apply_hunks_to_text(current, hunks)
        updated[path] = new_text
    return updated


def _diff_stats(diff_text: str) -> Tuple[int, int]:
    """Return (files_touched, changed_lines)."""
    files = set()
    changes = 0
    for ln in diff_text.splitlines():
        if ln.startswith('--- a/'):
            pass
        elif ln.startswith('+++ b/'):
            files.add(ln[6:])
        elif ln.startswith('+') and not ln.startswith('+++'):
            changes += 1
        elif ln.startswith('-') and not ln.startswith('---'):
            changes += 1
    return (len(files), changes)


# ---------- main handlers ----------

def handle_issue_event(event: Dict[str, Any]) -> str | None:
    action = event.get("action")
    issue  = event.get("issue") or {}
    number = issue.get("number")
    labels = {l["name"] for l in issue.get("labels", [])}

    # Trigger only for relevant events/labels
    if not (action in {"opened", "reopened"} or action == "labeled" or (labels & TRIGGER_LABELS)):
        return None
    if action == "labeled":
        lab = (event.get("label") or {}).get("name")
        if lab and lab not in TRIGGER_LABELS:
            return None

    title = issue.get("title", "")
    body  = issue.get("body", "") or ""
    base  = os.getenv("TICKETWATCHER_BASE_BRANCH") or get_default_branch()

    # 1) Build seed snippets from traceback/target hints
    seed_specs = _paths_from_issue_text(body)
    seed_snips: List[Dict[str, Any]] = []
    for path, line in seed_specs:
        snip = _fetch_slice(path, base, line, AROUND_LINES)
        if snip:
            seed_snips.append(snip)

    # 2) Call agent (two-round loop)
    agent = TicketWatcherAgent(
        allowed_paths=ALLOWED_PATHS,
        max_files=MAX_FILES,
        max_total_lines=MAX_LINES,
        default_around_lines=AROUND_LINES,
    )

    def _fetch_callback(needs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for n in needs:
            path = n.get("path", "")
            line = n.get("line")
            symbol = n.get("symbol")
            around = int(n.get("around_lines") or AROUND_LINES)
            if symbol:
                sn = _fetch_symbol_slice(path, base, symbol, around)
            else:
                sn = _fetch_slice(path, base, line, around)
            if sn:
                results.append(sn)
        return results

    result = agent.run_two_rounds(title, body, seed_snips, fetch_callback=_fetch_callback)

    # 3) If the agent asked for more (again), give guidance and stop
    if result.get("action") == "request_context":
        add_issue_comment(number,
            "⚠️ I need more context to propose a safe fix. "
            "Please include a traceback (`File \"src/...\", line N`) or add `Target: <path.py>`."
        )
        return None

    # 4) Validate diff against budgets/paths
    diff = result.get("diff", "")
    files_touched, changed_lines = _diff_stats(diff)
    if files_touched > MAX_FILES or changed_lines > MAX_LINES:
        add_issue_comment(number,
            f"⚠️ Proposed change exceeds budgets (files={files_touched}, lines={changed_lines}). "
            "Escalating to human review or try narrowing the scope."
        )
        return None

    # 5) Apply diff -> updated file texts
    try:
        updated_files = _apply_unified_diff(base, diff)
    except Exception as e:
        add_issue_comment(number, f"❌ Could not apply patch: {e}")
        return None

    # 6) Create branch, commit updates, open DRAFT PR
    branch = _mk_branch(number)
    create_branch(branch, base)
    for path, text in updated_files.items():
        create_or_update_file(
            path=path,
            content_text=text,
            message=f"agent: {title[:72]}",
            branch=branch,
        )

    pr_url, pr_number = create_pr(
        title=f"{PR_TITLE_PREF} #{number}",
        head=branch,
        base=base,
        body=f"Draft PR by TicketWatcher (route=llm)\n\nFiles: {files_touched} • Lines: {changed_lines}",
        draft=True,
    )

     # Comment summary back on the PR (use PR number for /issues/{number}/comments)
    notes = result.get("notes", "")
    pr_comment = (
        f"✅ Draft PR opened: {pr_url}\n\n"
        f"**Branch:** `{branch}`  •  **Base:** `{base}`\n"
        f"**Files touched:** {files_touched}  •  **Changed lines:** {changed_lines}\n\n"
        f"{('Notes: ' + notes) if notes else ''}"
    )
    add_issue_comment(pr_number, pr_comment)

    # (Optional) also notify the original issue if you want
    try:
        add_issue_comment(number, f"Draft PR opened: {pr_url}")
    except Exception as e:
        print(f"[warn] could not comment on issue #{number}: {e}")

    return pr_url

def handle_issue_comment_event(event: Dict[str, Any]) -> str | None:
    """
    Optional: keep your '/agent fix' comment trigger. It now just runs the same agent path,
    using the comment body as extra ticket context.
    """
    action = event.get("action")
    if action != "created":
        return None

    issue = event.get("issue") or {}
    number = issue.get("number")
    comment_body = (event.get("comment") or {}).get("body", "")

    if not comment_body.strip().lower().startswith("/agent fix"):
        return None

    # Reuse the main flow by pretending the comment text is appended to the body
    issue_copy = dict(issue)
    issue_copy["body"] = (issue.get("body") or "") + "\n\n" + comment_body
    fake_event = dict(event)
    fake_event["issue"] = issue_copy
    return handle_issue_event(fake_event)
