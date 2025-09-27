from __future__ import annotations
import os
import json
from typing import Any, Dict

from .github_api import (create_branch, create_or_update_file, create_pr,
                         get_default_branch, get_file_text)

from .agent_llm import propose_new_file_content

TARGET_FILE = os.getenv("TICKETWATCHER_TARGET_FILE", "app.py")  # choose a real file in your repo


TRIGGER_LABELS = set(os.getenv("TICKETWATCHER_TRIGGER_LABELS", "agent-fix,auto-pr").split(","))
BRANCH_PREFIX = os.getenv("TICKETWATCHER_BRANCH_PREFIX", "agent-fix/")
PR_TITLE_PREFIX = os.getenv("TICKETWATCHER_PR_TITLE_PREFIX", "agent: auto-fix scaffold")

def _mk_branch(issue_number: int) -> str:
    return f"{BRANCH_PREFIX}{issue_number}"

def _placeholder_patch_text(event: Dict[str, Any]) -> str:
    return (
        "# Auto-generated placeholder change by ticketwatcher\n"
        "# Replace this with your MCP-driven patch logic.\n\n"
        f"Event summary:\n{json.dumps({'action': event.get('action'), 'sender': event.get('sender', {}).get('login')}, indent=2)}\n"
    )

def handle_issue_event(event: Dict[str, Any]) -> str | None:
    action = event.get("action")
    issue = event.get("issue") or {}
    number = issue.get("number")
    labels = {l["name"] for l in issue.get("labels", [])}

    # Trigger when opened or when a trigger label is present/added
    if action in {"opened","reopened"} or (labels & TRIGGER_LABELS) or action == "labeled":
            if action == "labeled":
                label = event.get("label", {}).get("name")
                if label and label not in TRIGGER_LABELS:
                    return None

            branch = _mk_branch(number)
            base = os.getenv("TICKETWATCHER_BASE_BRANCH") or get_default_branch()
            create_branch(branch)

            # --- AGENT STEP: generate and commit a real patch ---
            title = issue.get("title","")
            body  = issue.get("body","") or ""
            current = get_file_text(TARGET_FILE, base)
            updated = propose_new_file_content(title, body, TARGET_FILE, current)
            create_or_update_file(
                path=TARGET_FILE,
                content_text=updated,
                message=f"agent: {title[:72]}",
                branch=branch,
            )
            # ----------------------------------------------------

            pr_url = create_pr(
                title=f"agent: auto-fix for issue #{number}",
                head=branch, base=base,
                body="Draft PR seeded by TicketWatcher LLM agent.",
                draft=True
            )

            return pr_url
    return None

def handle_issue_comment_event(event: Dict[str, Any]) -> str | None:
    action = event.get("action")
    if action != "created":
        return None
    issue = event.get("issue") or {}
    number = issue.get("number")
    comment_body = (event.get("comment") or {}).get("body", "")
    if comment_body.strip().lower().startswith("/agent fix"):
        branch = _mk_branch(number)
        base = get_default_branch()
        create_branch(branch)
        create_or_update_file(
            path=".ticketwatcher/trigger.txt",
            content_text=_placeholder_patch_text(event),
            message=f"chore: seed PR from comment on #{number}",
            branch=branch,
        )
        pr_url = create_pr(
            title=f"{PR_TITLE_PREFIX}: issue #{number} (comment)",
            head=branch,
            base=base,
            body="Seeded from issue comment trigger.",
            draft=True
        )
        return pr_url
    return None
