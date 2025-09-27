```python
def get_user_profile(user):
    if user is None:
        return {}
    name = sanitize_string(user["name"])
    return {"name": name}
```