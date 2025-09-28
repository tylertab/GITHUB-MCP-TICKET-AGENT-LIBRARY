import pytest

from ticketwatcher.config import load_config


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, [""]),

        ("", [""]),
        ("   ", [""]),
        ("src/,app/,", ["src/", "app/"]),
        ("src/app.py,lib", ["src/app.py", "lib/"]),
        ("src/,src/", ["src/"]),

    ],
)
def test_parse_allowed_paths_env(raw, expected, monkeypatch):
    # Ensure environment has no influence; the helper only uses the provided raw string.
    monkeypatch.delenv("ALLOWED_PATHS", raising=False)
    assert parse_allowed_paths_env(raw) == expected


def test_empty_entries_only_allow_all():
    assert parse_allowed_paths_env(",,,") == [""]


def test_config_defaults_to_allow_all(monkeypatch):
    monkeypatch.delenv("ALLOWED_PATHS", raising=False)
    monkeypatch.delenv("GITHUB_WORKSPACE", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    cfg = load_config()
    assert cfg.allowed_paths == [""]

