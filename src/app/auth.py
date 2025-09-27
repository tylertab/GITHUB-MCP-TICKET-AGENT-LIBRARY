from .user_repo import load_user
from .utils.stringy import sanitize_string

def get_user_profile(user_id: int | None):
    """
def get_user_profile(user_id: int | None):
    """
    Bug #1: crashes when user_id is None (should return {}).
    Bug #2 (cross-file): depends on sanitize_string in another file.
    """
    if user_id is None:
        return {}
    
    # BUG: no guard for None
    user = load_user(user_id)  # may return {} or None-ish fields
    # BUG: no defaults; will KeyError or TypeError on missing keys/None
    name = sanitize_string(user["name"])
    email = sanitize_string(user["email"])
    return {"id": user_id, "name": name, "email": email}