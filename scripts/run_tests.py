# scripts/run_tests.py
import os, sys

# Make src/ importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import the function under test
from app.user_repo import load_user

def test_load_user_returns_safe_shape_for_unknown_user():
    u = load_user(3)  # not in fake DB
    assert isinstance(u, dict)
    assert u.get("name", "") == ""
    assert u.get("email", "") == ""

from app.auth import get_user_profile

def test_trims_name_and_email_whitespace():
    profile = get_user_profile(1)
    assert profile["name"] == "Alice"
    assert profile["email"] == "alice@example.com"

if __name__ == "__main__":
    try:
        test_load_user_returns_safe_shape_for_unknown_user()
        print("✅ test_load_user_returns_safe_shape_for_unknown_user: PASSED")
    except AssertionError as e:
        print("❌ test_load_user_returns_safe_shape_for_unknown_user: FAILED")
        raise