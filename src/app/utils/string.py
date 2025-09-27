def sanitize_string(s):
    """
    Bug #4: crashes on None; should return "" (empty) for None.
    """
    # BUG: assumes s is str
    return s.strip()
