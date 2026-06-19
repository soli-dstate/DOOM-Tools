const ASSIGNEE = "soli-dstate";
// GitHub issue bodies cap at 65536 chars; leave margin for header + markdown.
const ISSUE_BODY_LIMIT = 65000;
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

// Best-effort AI title. Returns null on any failure so the caller falls
// back to the plain first-line title.
async function generateTitleWithAI(description, env) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    const resp = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "nvidia/nemotron-3-super-120b-a12b:free",
        messages: [{
          role: "user",
          content:
            "Write a short, specific GitHub issue title (under 80 characters) for this bug report. " +
            "Reply with only the title, no quotes, no prefix, nothing else.\n\n" +
            `Bug report:\n${description.slice(0, 4000)}`,
        }],
      }),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!resp.ok) return null;
    const data = await resp.json();
    const text = (data?.choices?.[0]?.message?.content || "").trim();
    return text ? text.replace(/^["']|["']$/g, "").slice(0, 100) : null;
  } catch {
    return null;
  }
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
    const stepsToReproduce = typeof body.steps_to_reproduce === "string" ? body.steps_to_reproduce.trim() : "";

    const ghHeaders = {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "doomtools-bugreport-relay",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    };

    const aiTitle = env.OPENROUTER_API_KEY ? await generateTitleWithAI(description, env) : null;

    const firstLine = description.split("\n")[0].slice(0, 80).trim();
    const title = `[Bug] ${aiTitle || firstLine || "In-app bug report"}`;
    let issueBody =
      `**Reported by:** ${name}\n` +
      `**App version:** ${appVersion}\n` +
      `**Platform:** ${platformInfo}\n\n` +
      `## Description\n\n${description}\n`;

    if (stepsToReproduce) {
      issueBody += `\n## Steps to Reproduce\n\n${stepsToReproduce}\n`;
    }

    // Embed the log inline. If it would blow the body limit, keep the TAIL
    // (most recent lines, the important ones) and drop the oldest.
    if (log.trim()) {
      const open = `\n## Log (${logName})\n\n<details><summary>Session log (most recent lines)</summary>\n\n\`\`\`\n`;
      const close = "\n```\n</details>\n";
      const note = "[... earlier lines truncated; showing most recent ...]\n";
      let body = log.replace(/```/g, "`​``"); // neutralize code fences
      const budget = ISSUE_BODY_LIMIT - issueBody.length - open.length - close.length;
      if (body.length > budget) {
        body = note + body.slice(body.length - Math.max(budget - note.length, 0));
      }
      issueBody += open + body + close;
    }

    const labels = ["bug", "in-app-report"];
    if (body.automatic) labels.push("automatic report");

    async function createIssue(withLabels) {
      const payload = { title, body: issueBody, assignees: [ASSIGNEE] };
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
    return json({ ok: true, issue_url: issue.html_url });
  },
};
