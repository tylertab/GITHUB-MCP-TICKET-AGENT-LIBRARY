"""
Goal: leading/trailing spaces in DB should be sanitized before returning.
"""
from app.auth import get_user_profile

def test_trims_name_and_email_whitespace():
    profile = get_user_profile(1)
    assert profile["name"] == "Alice"
    assert profile["email"] == "alice@example.com"
