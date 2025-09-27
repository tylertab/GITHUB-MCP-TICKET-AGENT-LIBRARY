from fastapi import FastAPI, Request
from ticketwatcher.github_api import GITHUB_API
import uvicorn

app = FastAPI()

@app.post("/github-webhook")
async def github_webhook(request: Request):
    payload = await request.json()

    # You can inspect what Github sends in the payload
    event = request.headers.get("x-gitHub-Event")

    # Example: handle "issues" events
    if event == "issues" and payload.get("action") == "opened":
        issue = payload["issue"]
        repo = payload["repository"]["full_name"]
        # Call into your agent logic
        # e.g., create a PR suggestion
        print(f"New issue in {repo}: {issue['title']}")

    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)