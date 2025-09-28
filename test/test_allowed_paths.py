import importlib
import os
import pathlib
import sys
import types

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("GITHUB_WORKSPACE", str(_PROJECT_ROOT))
os.environ.setdefault("GITHUB_REPOSITORY", "example/repo")

import pytest

from ticketwatcher import agent_llm
from ticketwatcher.agent_llm import TicketWatcherAgent
from ticketwatcher import handlers


class _DummyCompletions:
    @staticmethod
    def create(*args, **kwargs):
        class _DummyResponse:
            choices = [
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content="{\"action\": \"request_context\"}")
                )
            ]

        return _DummyResponse()


class _DummyOpenAI:
    def __init__(self, *args, **kwargs):
        self.chat = types.SimpleNamespace(completions=_DummyCompletions())


@pytest.fixture(autouse=True)
def stub_openai(monkeypatch):
    monkeypatch.setattr(agent_llm, "OpenAI", _DummyOpenAI)


def test_parse_allowed_paths_env_recognizes_allow_all():
    assert TicketWatcherAgent._parse_allowed_paths_env("") == [""]
    assert TicketWatcherAgent._parse_allowed_paths_env(",") == [""]
    assert TicketWatcherAgent._parse_allowed_paths_env("src/,") == ["src/"]


def test_agent_sanitizes_needs_outside_src_when_unrestricted():
    agent = TicketWatcherAgent(allowed_paths=[])
    needs = [
        {"path": "ticketwatcher-worker/src/index.ts", "line": 42, "around_lines": 120},
        {"path": "test/support/sample_test.py", "line": 8, "around_lines": 15},
    ]
    cleaned = agent._sanitize_needs(needs)
    assert [n["path"] for n in cleaned] == [
        "ticketwatcher-worker/src/index.ts",
        "test/support/sample_test.py",
    ]
    # around_lines should be clamped to the agent default (60)
    assert cleaned[0]["around_lines"] == agent.default_around_lines


def test_parse_stack_text_accepts_non_src_paths_when_allow_all(monkeypatch):
    monkeypatch.setattr(handlers, "ALLOWED_PATHS", [])
    sample = (
        'Traceback (most recent call last):\n'
        '  File "test/helpers/example_test.py", line 15, in test_case\n'
        "ticketwatcher-worker/src/index.ts:123\n"
    )
    results = handlers.parse_stack_text(sample, allowed_prefixes=handlers.ALLOWED_PATHS, limit=5)
    assert ("test/helpers/example_test.py", 15) in results
    assert ("ticketwatcher-worker/src/index.ts", 123) in results


def test_handlers_load_allowed_paths_preserves_allow_all(monkeypatch):
    previous = os.environ.get("ALLOWED_PATHS")
    monkeypatch.setenv("ALLOWED_PATHS", "")
    module = importlib.reload(handlers)
    try:
        assert module.ALLOWED_PATHS == [""]
    finally:
        if previous is None:
            monkeypatch.delenv("ALLOWED_PATHS", raising=False)
        else:
            monkeypatch.setenv("ALLOWED_PATHS", previous)
        importlib.reload(handlers)
