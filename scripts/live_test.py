import os, sys, pathlib

# add src/ to sys.path so imports work
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ticketwatcher.handlers import handle_issue_event

event = {
    "action": "opened",
    "issue": {
        "number": 99,
        "title": "[agent-fix] None user in auth",
        "body": (
            "Traceback (most recent call last):\n"
            '  File "src/app/auth.py", line 2, in get_user_profile\n'
            '    name = user["name"]\n'
            "KeyError: 'name'\n"
        ),
        "labels": [{"name": "agent-fix"}],
    },
    "sender": {"login": "live-tester"},
}

pr_url = handle_issue_event(event)
print("Draft PR created:", pr_url)
