"""Configuration loading for TicketWatcher."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Set

from .paths import parse_allowed_paths_env


@dataclass(frozen=True)
class TicketWatcherConfig:
    trigger_labels: Set[str]
    branch_prefix: str
    pr_title_prefix: str
    allowed_paths: List[str]
    max_files: int
    max_lines: int
    around_lines: int
    repo_root: str
    repo_name: str


DEFAULT_ALLOWED = "src/,app/"


def _resolve_repo_root() -> str:
    return os.getenv("GITHUB_WORKSPACE") or os.getcwd()


def _resolve_repo_name(repo_root: str) -> str:
    repo_env = os.getenv("GITHUB_REPOSITORY")
    if repo_env:
        return repo_env.split("/", 1)[-1]
    return os.path.basename(repo_root)


def load_config() -> TicketWatcherConfig:
    repo_root = _resolve_repo_root()
    return TicketWatcherConfig(
        trigger_labels=set(os.getenv("TICKETWATCHER_TRIGGER_LABELS", "agent-fix,auto-pr").split(",")),
        branch_prefix=os.getenv("TICKETWATCHER_BRANCH_PREFIX", "agent-fix/"),
        pr_title_prefix=os.getenv("TICKETWATCHER_PR_TITLE_PREFIX", "agent: auto-fix for issue"),
        allowed_paths=parse_allowed_paths_env(os.getenv("ALLOWED_PATHS", DEFAULT_ALLOWED)),
        max_files=int(os.getenv("MAX_FILES", "4")),
        max_lines=int(os.getenv("MAX_LINES", "200")),
        around_lines=int(os.getenv("DEFAULT_AROUND_LINES", "60")),
        repo_root=repo_root,
        repo_name=_resolve_repo_name(repo_root),
    )

