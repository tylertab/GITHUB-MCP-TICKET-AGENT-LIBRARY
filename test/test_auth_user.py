"""
Goal: get_user_profile(None) should not crash and should return {}.
"""
from app.auth import get_user_profile

def test_none_user_returns_empty_dict():
    assert get_user_profile(None) == {}
