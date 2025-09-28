import pytest

from ticketwatcher.paths import parse_allowed_paths_env


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, ["src/"]),
        ("", [""]),
        ("   ", [""]),
        ("src/,app/,", ["src/", "app/"]),
        ("src/app.py,lib", ["src/app.py", "lib/"]),
    ],
)
def test_parse_allowed_paths_env(raw, expected, monkeypatch):
    # Ensure environment has no influence; the helper only uses the provided raw string.
    monkeypatch.delenv("ALLOWED_PATHS", raising=False)
    assert parse_allowed_paths_env(raw) == expected


def test_empty_entries_only_allow_all():
    assert parse_allowed_paths_env(",,,") == [""]
