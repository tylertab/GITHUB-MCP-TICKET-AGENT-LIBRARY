def handle_issue_event(event: Dict[str, Any]) -> str | None:
    action = event.get("action")
    issue = event.get("issue") or {}
    number = issue.get("number")
    labels = {l["name"] for l in issue.get("labels", [])}

    # Trigger when opened or when a trigger label is present/added
    if action in {"opened","reopened"} or (labels & TRIGGER_LABELS) or action == "labeled":
            if action == "labeled":
                label = event.get("label", {}).get("name")
                if label and label not in TRIGGER_LABELS:
                    return None

            branch = _mk_branch(number)
            base = os.getenv("TICKETWATCHER_BASE_BRANCH") or get_default_branch()
            create_branch(branch)

            # --- AGENT STEP: generate and commit a real patch ---
            title = issue.get("title","")
            body  = issue.get("body","") or ""
            current = get_file_text(TARGET_FILE, base)
