import importlib
import sys
from pathlib import Path
from types import ModuleType


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))


def test_handlers_import_without_repo_env(monkeypatch):
    """Ensure handlers module loads without GitHub repo env vars."""

    monkeypatch.delenv("GITHUB_WORKSPACE", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    sys.modules.pop("ticketwatcher.handlers", None)

    stub_github_api = ModuleType("ticketwatcher.github_api")
    stub_github_api.get_default_branch = lambda: "main"
    stub_github_api.create_branch = lambda *a, **k: None
    stub_github_api.create_or_update_file = lambda *a, **k: None
    stub_github_api.create_pr = lambda *a, **k: ("https://example.com", 1)
    stub_github_api.get_file_text = lambda *a, **k: ""
    stub_github_api.file_exists = lambda *a, **k: False
    stub_github_api.add_issue_comment = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "ticketwatcher.github_api", stub_github_api)

    stub_agent_llm = ModuleType("ticketwatcher.agent_llm")

    class _DummyAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run_two_rounds(self, *args, **kwargs):
            return {"action": "request_context", "needs": [], "notes": ""}

    stub_agent_llm.TicketWatcherAgent = _DummyAgent
    monkeypatch.setitem(sys.modules, "ticketwatcher.agent_llm", stub_agent_llm)

    module = importlib.import_module("ticketwatcher.handlers")

    assert hasattr(module, "REPO_ROOT")
    assert hasattr(module, "REPO_NAME")
