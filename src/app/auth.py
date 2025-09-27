from .user_repo import load_user
from .utils.stringy import sanitize_string

def get_user_profile(user_id: int | None):
    # BUG: no guard for None
    user = load_user(user_id)  # may return {} or None-ish fields
    
    if user is None:
        return {}  # Return an empty dict if user is None
    
    # BUG: no defaults; will KeyError or TypeError on missing keys/None
    name = sanitize_string(user["name"])
    email = sanitize_string(user["email"])
    return {"id": user_id, "name": name, "email": email}
    name = sanitize_string(user["name"])
    email = sanitize_string(user["email"])
    return {"id": user_id, "name": name, "email": email}