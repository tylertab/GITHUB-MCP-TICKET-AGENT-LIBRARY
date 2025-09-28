_FAKE_DB = {
    1: {"name": "  Alice  ", "email": "alice@example.com "},
    2: {"name": None, "email": "bob@example.com"},

}

def load_user(user_id: int | None):
    if user_id not in _FAKE_DB:
        return {}  
    return _FAKE_DB[user_id]
