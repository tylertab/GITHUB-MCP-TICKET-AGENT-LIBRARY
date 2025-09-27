import os
import sys
import pathlib
import requests
import time

# Make 'src' importable
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import ticketwatcher.handlers as H  # your real handler (no mocks)


def test_live_issue_to_pr_integration():
    """
    LIVE test: hits GitHub for real.
    Requirements:
      - GITHUB_TOKEN env (PAT with repo perms)
      - GITHUB_REPOSITORY env 'owner/name'
      - Repo contains 'src/app/auth.py' with buggy code
    This will create a real Issue and a real DRAFT PR in your repo.
    """
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY") or os.getenv("GITHUB_REPO")
    assert token, "Set GITHUB_TOKEN"
    assert repo, "Set GITHUB_REPOSITORY (e.g. owner/name)"
    owner, name = repo.split("/", 1)

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ticketwatcher-integration-test/0.1",
    })

    # 1) Create a real issue (the handler will read its number to comment back)
    title = "[agent-fix] None user in auth (live integration)"
    body = (
        "Traceback (most recent call last):\n"
        '  File "src/app/auth.py", line 2, in get_user_profile\n'
        '    name = user["name"]\n'
        "KeyError: 'name'\n"
    )
    issue_resp = session.post(f"https://api.github.com/repos/{owner}/{name}/issues",
                              json={"title": title, "body": body, "labels": ["agent-fix"]})
    assert issue_resp.ok, f"Issue create failed: {issue_resp.status_code} {issue_resp.text}"
    issue = issue_resp.json()
    issue_number = issue["number"]

    # 2) Build the GitHub event payload (what Actions would pass via GITHUB_EVENT_PATH)
    event = {
        "action": "opened",
        "issue": {
            "number": issue_number,
            "title": title,
            "body": body,
            "labels": [{"name": "agent-fix"}],
        },
        "sender": {"login": "integration-test"},
    }

    # 3) Call your real handler (this will create a branch + open a DRAFT PR for real)
    pr_url = H.handle_issue_event(event)
    assert pr_url, "Handler did not return a PR URL"
    print(f"\nDraft PR created: {pr_url}\n")

    # 4) Quick sanity check the PR exists
    #    (convert URL to API endpoint to fetch JSON)
    #    e.g. https://github.com/owner/name/pull/123 -> number 123
    assert "/pull/" in pr_url
    pr_number = int(pr_url.rsplit("/", 1)[-1])
    pr_api = session.get(f"https://api.github.com/repos/{owner}/{name}/pulls/{pr_number}")
    assert pr_api.ok, f"PR fetch failed: {pr_api.status_code} {pr_api.text}"

    # Optional: ensure it's a draft
    assert pr_api.json().get("draft") is True

    # (Optional) Close the issue to keep the repo tidy (leave the draft PR for review)
    # session.patch(f"https://api.github.com/repos/{owner}/{name}/issues/{issue_number}",
    #               json={"state": "closed"})
