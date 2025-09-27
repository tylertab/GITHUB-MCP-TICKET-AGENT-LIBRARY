import os
import json
import sys
from .handlers import handle_issue_event, handle_issue_comment_event

def main(argv=None):
    argv = argv or sys.argv[1:]
    event_file = None
    # Allow passing `--event-file` manually; otherwise use Actions env
    for i, a in enumerate(argv):
        if a == "--event-file" and i + 1 < len(argv):
            event_file = argv[i + 1]
    if not event_file:
        event_file = os.getenv("GITHUB_EVENT_PATH")  # set by GitHub Actions

    if not event_file or not os.path.exists(event_file):
        print("No event file found. Provide --event-file or run in GitHub Actions.", file=sys.stderr)
        sys.exit(1)

    with open(event_file, "r", encoding="utf-8") as f:
        event = json.load(f)

    name = os.getenv("GITHUB_EVENT_NAME")  # e.g., issues, issue_comment
    pr_url = None

    if name == "issues":
        pr_url = handle_issue_event(event)
    elif name == "issue_comment":
        pr_url = handle_issue_comment_event(event)
    else:
        print(f"Event {name} not handled; exiting.")
        sys.exit(0)

    if pr_url:
        print(f"PR_URL={pr_url}")
    else:
        print("No action taken.")

if __name__ == "__main__":
    main()
