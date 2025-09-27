import os, sys, pathlib

# add src/ to sys.path so imports work
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ticketwatcher.handlers import handle_issue_event

event = {
    "action": "opened",
    "issue": {
        "number": 139,
        "title": "[agent-fix] None user in auth",
        "body": ("""Traceback (most recent call last):
File "/Users/tylertabarovsky/GITHUB-MCP-TICKET-AGENT-LIBRARY/test/test_auth_trims.py", line 4, in
from app.auth import get_user_profile
File "/Users/tylertabarovsky/GITHUB-MCP-TICKET-AGENT-LIBRARY/src/app/auth.py", line 2, in
from .utils.stringy import sanitize_string
ModuleNotFoundError: No module named 'app.utils.stringy'
"""
            
        ),
        "labels": [{"name": "agent-fix"}],
    },
    "sender": {"login": "live-tester"},
}

pr_url = handle_issue_event(event)
print("Draft PR created:", pr_url)
