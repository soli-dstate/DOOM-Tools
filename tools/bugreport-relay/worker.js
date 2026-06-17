const GIST_MAX_BYTES = 9 * 1024 * 1024;
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

function sanitizeFilename(name) {
  const cleaned = String(name || "session.log").replace(/[^A-Za-z0-9._-]/g, "_");
  return cleaned.slice(0, 100) || "session.log";
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (request.method !== "POST") {
      return json({ error: "POST only" }, 405);
    }
    if (!env.GITHUB_TOKEN || !env.GITHUB_REPO) {
      return json({ error: "relay not configured" }, 500);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "invalid JSON body" }, 400);
    }

    const name = String(body.name || "Anonymous").slice(0, 200);
    const description = String(body.description || "").trim();
    if (!description) {
      return json({ error: "description is required" }, 400);
    }
    const appVersion = String(body.app_version || "unknown").slice(0, 100);
    const platformInfo = String(body.platform || "unknown").slice(0, 200);
    let log = typeof body.log === "string" ? body.log : "";
    const logName = sanitizeFilename(body.log_filename);

    const ghHeaders = {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "doomtools-bugreport-relay",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    };

    let gistUrl = "";
    if (log.trim()) {
      if (log.length > GIST_MAX_BYTES) {
        log = "[... earlier log lines truncated by relay ...]\n" +
          log.slice(log.length - GIST_MAX_BYTES);
      }
      try {
        const gistResp = await fetch("https://api.github.com/gists", {
          method: "POST",
          headers: ghHeaders,
          body: JSON.stringify({
            description: `DOOM-Tools log from ${name} (v${appVersion})`,
            public: false,
            files: { [logName]: { content: log || "(empty)" } },
          }),
        });
        if (gistResp.ok) {
          const gist = await gistResp.json();
          gistUrl = gist.html_url || "";
        } else {
          console.log("Gist creation failed:", gistResp.status, await gistResp.text());
        }
      } catch (e) {
        console.log("Gist creation threw:", e);
      }
    }

    const firstLine = description.split("\n")[0].slice(0, 80).trim();
    const title = `[Bug] ${firstLine || "In-app bug report"}`;
    let issueBody =
      `**Reported by:** ${name}\n` +
      `**App version:** ${appVersion}\n` +
      `**Platform:** ${platformInfo}\n\n` +
      `## Description\n\n${description}\n`;
    if (gistUrl) {
      issueBody += `\n## Log\n\n[Full session log (private Gist)](${gistUrl})\n`;
    }

    const labels = ["bug", "in-app-report"];

    async function createIssue(withLabels) {
      const payload = { title, body: issueBody };
      if (withLabels) payload.labels = labels;
      return fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
        method: "POST",
        headers: ghHeaders,
        body: JSON.stringify(payload),
      });
    }

    let issueResp = await createIssue(true);
    
    if (issueResp.status === 422) {
      issueResp = await createIssue(false);
    }
    if (!issueResp.ok) {
      const detail = await issueResp.text();
      console.log("Issue creation failed:", issueResp.status, detail);
      return json({ error: "failed to create issue", detail: detail.slice(0, 500) }, 502);
    }

    const issue = await issueResp.json();
    return json({ ok: true, issue_url: issue.html_url, gist_url: gistUrl });
  },
};
