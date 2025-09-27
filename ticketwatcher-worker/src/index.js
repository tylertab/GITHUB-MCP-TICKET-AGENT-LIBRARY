export default {
  async fetch(request, env) {
    if (request.method === "GET") {
      return new Response("Worker is live ✅", { status: 200 });
    }
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    try {
      const body = await request.json().catch(() => ({}));
      const eventType = request.headers.get("x-github-event");

      if (eventType === "ping") {
        return new Response("Ping received ✅", { status: 200 });
      }

      if (eventType === "create_issue") {
        const repoFullName = body.repository_full_name || env.REPO_FULL_NAME;
        const issueTitle   = body.title || "Default Issue Title";
        const issueBody    = body.text  || "Default issue body.";

        if (!repoFullName) {
          return new Response("Missing repository_full_name / REPO_FULL_NAME", { status: 400 });
        }
        if (!env.GITHUB_TOKEN) {
          return new Response("Missing GITHUB_TOKEN binding", { status: 500 });
        }

        const ghResp = await fetch(`https://api.github.com/repos/${repoFullName}/issues`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
            "Accept": "application/vnd.github+json",
            "User-Agent": "wrangler-worker",
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ title: issueTitle, body: issueBody })
        });

        // Try JSON first; fall back to text if not JSON
        let payload;
        const ct = ghResp.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          payload = await ghResp.json();
        } else {
          payload = { message: await ghResp.text() };
        }

        if (ghResp.ok) {
          const url = payload.html_url || "(no url)";
          return new Response(`Issue created: ${url}`, { status: 201 });
        } else {
          const msg = payload.message || `HTTP ${ghResp.status}`;
          return new Response(`Failed to create issue: ${msg}`, { status: ghResp.status || 400 });
        }
      }

      return new Response("Webhook processed ✅", { status: 200 });
    } catch (err) {
      // Cloudflare Workers: Error may not be fully serializable; stringify best effort
      return new Response(`Internal Server Error: ${String(err)}`, { status: 500 });
    }
  },
};
