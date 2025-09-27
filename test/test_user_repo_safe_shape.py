"""
Goal: load_user should return a dict with safe defaults for missing users.
"""
from app.user_repo import load_user

def test_load_user_returns_safe_shape_for_unknown_user():
    u = load_user(3)  # not in fake DB
    assert isinstance(u, dict)
    assert u.get("name", "") == ""
    assert u.get("email", "") == ""