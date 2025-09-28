"""Event handlers orchestrating the TicketWatcher workflow."""
from __future__ import annotations

import os
from typing import Any, Dict, List

from .agent_llm import TicketWatcherAgent
from .config import load_config
from .diff_utils import apply_unified_diff, diff_stats
from .github_api import (
    add_issue_comment,
    create_branch,
    create_or_update_file,
    create_pr,
    get_default_branch,
)
from .snippets import fetch_slice, fetch_symbol_slice
from .stackparse import parse_stack_text


CONFIG = load_config()
TRIGGER_LABELS = CONFIG.trigger_labels
BRANCH_PREFIX = CONFIG.branch_prefix
PR_TITLE_PREF = CONFIG.pr_title_prefix
ALLOWED_PATHS = CONFIG.allowed_paths
MAX_FILES = CONFIG.max_files
MAX_LINES = CONFIG.max_lines
AROUND_LINES = CONFIG.around_lines
REPO_ROOT = CONFIG.repo_root
REPO_NAME = CONFIG.repo_name


def _mk_branch(issue_number: int) -> str:
    return f"{BRANCH_PREFIX}{issue_number}"


def _gather_seed_snippets(ticket_body: str, base_ref: str) -> List[Dict[str, Any]]:
    seeds: List[Dict[str, Any]] = []
    specs = parse_stack_text(
        ticket_body,
        repo_root=REPO_ROOT,
        repo_name=REPO_NAME,
        allowed_prefixes=ALLOWED_PATHS,
        limit=5,
    )
    for path, line in specs:
        snippet = fetch_slice(
            path,
            base_ref=base_ref,
            center_line=line,
            around_lines=AROUND_LINES,
            allowed_prefixes=ALLOWED_PATHS,
        )
        if snippet:
            seeds.append(snippet)
    return seeds


def _build_fetch_callback(base_ref: str):
    def _fetch(needs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        snippets: List[Dict[str, Any]] = []
        for need in needs:
            path = need.get("path", "")
            around = int(need.get("around_lines") or AROUND_LINES)
            if need.get("symbol"):
                snippet = fetch_symbol_slice(
                    path,
                    base_ref=base_ref,
                    symbol=need["symbol"],
                    around_lines=around,
                    allowed_prefixes=ALLOWED_PATHS,
                )
            else:
                snippet = fetch_slice(
                    path,
                    base_ref=base_ref,
                    center_line=need.get("line"),
                    around_lines=around,
                    allowed_prefixes=ALLOWED_PATHS,
                )
            if snippet:
                snippets.append(snippet)
        return snippets

    return _fetch


def handle_issue_event(event: Dict[str, Any]) -> str | None:
    action = event.get("action")
    issue = event.get("issue") or {}
    number = issue.get("number")
    labels = {label["name"] for label in issue.get("labels", [])}

    if not (action in {"opened", "reopened"} or action == "labeled" or (labels & TRIGGER_LABELS)):
        return None

    if action == "labeled":
        label_name = (event.get("label") or {}).get("name")
        if label_name and label_name not in TRIGGER_LABELS:
            return None

    title = issue.get("title", "")
    body = issue.get("body", "") or ""
    base = os.getenv("TICKETWATCHER_BASE_BRANCH") or get_default_branch()

    seed_snippets = _gather_seed_snippets(body, base)

    agent = TicketWatcherAgent(
        allowed_paths=ALLOWED_PATHS,
        max_files=MAX_FILES,
        max_total_lines=MAX_LINES,
        default_around_lines=AROUND_LINES,
    )

    fetch_callback = _build_fetch_callback(base)
    result = agent.run_two_rounds(title, body, seed_snippets, fetch_callback=fetch_callback)

    if result.get("action") == "request_context":
        add_issue_comment(
            number,
            "⚠️ I need more context to propose a safe fix. "
            "Please include a traceback (`File \"src/...\", line N`) or add `Target: <path.py>`.",
        )
        return None

    diff = result.get("diff", "")
    files_touched, changed_lines = diff_stats(diff)
    if files_touched > MAX_FILES or changed_lines > MAX_LINES:
        add_issue_comment(
            number,
            f"⚠️ Proposed change exceeds budgets (files={files_touched}, lines={changed_lines}). "
            "Escalating to human review or try narrowing the scope.",
        )
        return None

    try:
        updated_files = apply_unified_diff(
            base_ref=base,
            diff_text=diff,
            allowed_prefixes=ALLOWED_PATHS,
        )
    except Exception as exc:  # pylint: disable=broad-except
        add_issue_comment(number, f"❌ Could not apply patch: {exc}")
        return None

    branch = _mk_branch(number)
    create_branch(branch, base)
    for path, content in updated_files.items():
        create_or_update_file(
            path=path,
            content_text=content,
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

    notes = result.get("notes", "")
    pr_comment = (
        f"✅ Draft PR opened: {pr_url}\n\n"
        f"**Branch:** `{branch}`  •  **Base:** `{base}`\n"
        f"**Files touched:** {files_touched}  •  **Changed lines:** {changed_lines}\n\n"
        f"{('Notes: ' + notes) if notes else ''}"
    )
    add_issue_comment(pr_number, pr_comment)

    try:
        add_issue_comment(number, f"Draft PR opened: {pr_url}")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[warn] could not comment on issue #{number}: {exc}")

    return pr_url


def handle_issue_comment_event(event: Dict[str, Any]) -> str | None:
    action = event.get("action")
    if action != "created":
        return None

    issue = event.get("issue") or {}
    number = issue.get("number")
    comment_body = (event.get("comment") or {}).get("body", "")

    if not comment_body.strip().lower().startswith("/agent fix"):
        return None

    issue_copy = dict(issue)
    issue_copy["body"] = (issue.get("body") or "") + "\n\n" + comment_body
    synthetic_event = dict(event)
    synthetic_event["issue"] = issue_copy
    return handle_issue_event(synthetic_event)

