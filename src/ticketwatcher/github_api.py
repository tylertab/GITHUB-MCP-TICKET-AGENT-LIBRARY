import os
import base64
import json
import requests
from typing import Optional, Dict, Any

GITHUB_API = os.getenv("GITHUB_API", "https://api.github.com")
# In GitHub Actions, this token is auto-injected with repo-scoped perms.
TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
REPO = os.getenv("GITHUB_REPOSITORY") or os.getenv("GITHUB_REPO")  # e.g. "owner/name"

if not REPO:
    raise RuntimeError("GITHUB_REPOSITORY or GITHUB_REPO not set")

OWNER, NAME = REPO.split("/", 1)

def _session() -> requests.Session:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN/GH_TOKEN not set")
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ticketwatcher/0.1",
    })
    return s

def get_repo() -> Dict[str, Any]:
    with _session() as s:
        r = s.get(f"{GITHUB_API}/repos/{OWNER}/{NAME}")
        r.raise_for_status()
        return r.json()

def get_default_branch() -> str:
    return get_repo()["default_branch"]

def get_head_sha(branch: str) -> str:
    with _session() as s:
        r = s.get(f"{GITHUB_API}/repos/{OWNER}/{NAME}/git/ref/heads/{branch}")
        r.raise_for_status()
        return r.json()["object"]["sha"]

# --- CHANGED: allow passing a base branch OR a specific SHA ---
def create_branch(branch: str, base: Optional[str] = None, from_sha: Optional[str] = None) -> None:
    """
    Create 'branch' from either:
      - from_sha (exact SHA), or
      - base (branch name), or
      - the repo's default branch if neither provided.

    Back-compat: handlers can call create_branch(branch, base).
    """
    if from_sha is None:
        if base:
            from_sha = get_head_sha(base)
        else:
            from_sha = get_head_sha(get_default_branch())

    with _session() as s:
        r = s.post(f"{GITHUB_API}/repos/{OWNER}/{NAME}/git/refs", json={
            "ref": f"refs/heads/{branch}",
            "sha": from_sha
        })
        if r.status_code == 422 and "Reference already exists" in r.text:
            return
        r.raise_for_status()

def create_or_update_file(path: str, content_text: str, message: str, branch: str) -> None:
    content_b64 = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    with _session() as s:
        # check if file exists to include sha
        get = s.get(f"{GITHUB_API}/repos/{OWNER}/{NAME}/contents/{path}", params={"ref": branch})
        sha = get.json().get("sha") if get.status_code == 200 else None

        payload = {
            "message": message,
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        put = s.put(f"{GITHUB_API}/repos/{OWNER}/{NAME}/contents/{path}", json=payload)
        put.raise_for_status()

def create_pr(title: str, head: str, base: Optional[str] = None, body: str = "", draft: bool = True) -> str:
    if base is None:
        base = get_default_branch()
    with _session() as s:
        r = s.post(f"{GITHUB_API}/repos/{OWNER}/{NAME}/pulls", json={
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft
        })
        r.raise_for_status()
        data = r.json()
        return data["html_url"], data["number"]

def add_issue_comment(issue_number: int, body: str) -> None:
    with _session() as s:
        r = s.post(f"{GITHUB_API}/repos/{OWNER}/{NAME}/issues/{issue_number}/comments", json={"body": body})
        r.raise_for_status()

def add_labels(issue_number: int, labels: list[str]) -> None:
    with _session() as s:
        r = s.post(f"{GITHUB_API}/repos/{OWNER}/{NAME}/issues/{issue_number}/labels", json={"labels": labels})
        r.raise_for_status()

# --- NEW: used by handlers to validate a target file on a given ref ---
def file_exists(path: str, ref: str) -> bool:
    with _session() as s:
        r = s.get(f"{GITHUB_API}/repos/{OWNER}/{NAME}/contents/{path}", params={"ref": ref})
        if r.status_code == 200:
            return True
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return False  # unreachable

# (optional hardening) returns "" for empty files, handles missing 'content'

def get_file_text(path: str, ref: str) -> str:
    with _session() as s:
        r = s.get(f"{GITHUB_API}/repos/{OWNER}/{NAME}/contents/{path}", params={"ref": ref})
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        data = r.json()
        
        # Handle case where API returns a list (directory) instead of a file
        if isinstance(data, list):
            return ""  # It's a directory, not a file
            
        # Handle case where data is not a dict
        if not isinstance(data, dict):
            return ""
            
        content = data.get("content")
        if content is None:
            return ""
        return base64.b64decode(content).decode("utf-8")
