import os
from openai import OpenAI

MODEL = os.getenv("TICKETWATCHER_MODEL", "gpt-4o-mini")

def propose_new_file_content(issue_title: str, issue_body: str, file_path: str, current_text: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    sys = ("You are a helpful code editor. Given an issue and the current file, "
           "return ONLY the full updated file contents. Make the smallest safe change.")
    user = (f"Issue title: {issue_title}\nIssue body:\n{issue_body}\n\n"
            f"Target file: {file_path}\nCurrent file:\n```text\n{current_text}\n```")
    resp = client.chat.completions.create(model=MODEL, messages=[{"role":"system","content":sys},
                                                                 {"role":"user","content":user}])
    return resp.choices[0].message.content.strip()

