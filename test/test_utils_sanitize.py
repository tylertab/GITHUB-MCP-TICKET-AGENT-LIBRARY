"""
Goal: sanitize_string(None) should not crash; return empty string.
"""
from app.utils.stringy import sanitize_string

def test_sanitize_handles_none():
    assert sanitize_string(None) == ""

def test_sanitize_trims_whitespace():
    assert sanitize_string("  hello  ") == "hello"
