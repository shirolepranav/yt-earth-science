/**
 * The bridge between Telegram and GitHub Actions.
 *
 * Telegram needs somewhere always-awake to deliver your messages to. GitHub
 * Actions can't be that - it only wakes up when something pokes it. This
 * Worker is the thing in between, and it does exactly three jobs:
 *
 *   1. Check the message really came from Telegram, and really came from you.
 *   2. Answer "/status" on the spot by reading the run's state file from the
 *      repo, so the most common question doesn't cost a 60-second job boot.
 *   3. Forward everything else to GitHub as a `repository_dispatch` event,
 *      which starts .github/workflows/chat.yml.
 *
 * It holds no state of its own. The run folder in the repo is the only state
 * there is, which means the Worker can be redeployed or deleted at any time
 * without losing a run.
 *
 * Free tier: 100,000 requests a day. A busy week here is maybe 200.
 *
 * Deploy: see bot/README.md - about ten minutes, no credit card.
 *
 * Secrets it needs (set with `wrangler secret put <NAME>`):
 *   TELEGRAM_BOT_TOKEN     from @BotFather
 *   TELEGRAM_CHAT_ID       your own chat id - the only one it will talk to
 *   TELEGRAM_WEBHOOK_SECRET  a random string, also given to setWebhook
 *   GITHUB_TOKEN           a fine-grained PAT with Contents: read/write
 *   GITHUB_REPO            "owner/repo"
 */

export default {
  async fetch(request, env) {
    // Telegram only ever POSTs. Anything else is a scanner or a browser.
    if (request.method !== "POST") {
      return new Response("This endpoint only accepts Telegram webhooks.", { status: 405 });
    }

    // Telegram echoes this header back on every delivery. If it doesn't match,
    // someone found the URL and is guessing - drop it silently.
    const token = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (token !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("no", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return ok(); // Malformed body. Never make Telegram retry.
    }

    // A message you typed, or a button you tapped - handled the same way.
    const message = update.message || update.edited_message;
    const callback = update.callback_query;
    const chatId = String(message?.chat?.id ?? callback?.message?.chat?.id ?? "");
    const text = (callback?.data ?? message?.text ?? "").trim();

    // The single most important line in this file: the bot answers to you and
    // to nobody else. Without it, anyone who finds the bot can spend your API
    // budget and publish to your channel.
    if (chatId !== String(env.TELEGRAM_CHAT_ID)) {
      return ok();
    }
    if (!text) return ok();

    // Stop the button showing a spinner forever.
    if (callback) {
      await telegram(env, "answerCallbackQuery", { callback_query_id: callback.id });
    }

    try {
      if (text === "/status" || text === "cmd:status") {
        await sendStatus(env);
      } else {
        await dispatch(env, text);
        await telegram(env, "sendMessage", {
          chat_id: chatId,
          text: "⏳ On it…",
        });
      }
    } catch (error) {
      await telegram(env, "sendMessage", {
        chat_id: chatId,
        text: `❌ Couldn't reach GitHub: ${error.message}`,
      });
    }

    return ok();
  },
};

/** Telegram retries anything that isn't a 200, so always return one. */
function ok() {
  return new Response("ok", { status: 200 });
}

/** Call a Telegram Bot API method. */
async function telegram(env, method, body) {
  const response = await fetch(
    `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return response.json();
}

/**
 * Start the chat workflow, handing it the message you sent.
 *
 * `repository_dispatch` is GitHub's "run this workflow now, with this data"
 * endpoint. The payload arrives in the workflow as
 * `github.event.client_payload`.
 */
async function dispatch(env, text) {
  const response = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "deepearth-chat-bridge",
      },
      body: JSON.stringify({
        event_type: "chat",
        // GitHub caps client_payload at 64KB; a pasted script fits easily.
        client_payload: { text: text.slice(0, 60000) },
      }),
    },
  );

  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
}

/**
 * Answer "/status" without starting a job.
 *
 * Reads runs/<latest>/state.json straight out of the repo. It's the question
 * you'll ask most often and the answer is already sitting in a file, so paying
 * a minute of Actions boot time for it would be silly.
 */
async function sendStatus(env) {
  const headers = {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "deepearth-chat-bridge",
  };

  const listing = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/contents/runs`,
    { headers },
  );

  // A rejected request and an empty repo are completely different problems, and
  // reporting both as "no runs yet" hides a broken token behind a healthy-looking
  // answer - you'd only find out when a real command quietly did nothing.
  if (!listing.ok) {
    const reason = {
      401: "GITHUB_TOKEN is wrong or expired.",
      403: "GITHUB_TOKEN lacks Contents access to this repo.",
      404: `Can't see ${env.GITHUB_REPO} — check GITHUB_REPO is "owner/repo", and that the token covers it.`,
    }[listing.status];

    // 404 with no runs/ folder yet is the one benign case: the repo is fine,
    // it just has not produced a run. Tell them apart by asking for the repo.
    if (listing.status === 404) {
      const repo = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}`, { headers });
      if (repo.ok) {
        return telegram(env, "sendMessage", {
          chat_id: env.TELEGRAM_CHAT_ID,
          text: "No runs yet. Send “new video” to start one.",
        });
      }
    }

    return telegram(env, "sendMessage", {
      chat_id: env.TELEGRAM_CHAT_ID,
      text: `⚠️ GitHub returned ${listing.status}.\n\n${reason || "Unexpected response."}\n\nFix it with: wrangler secret put <NAME>`,
    });
  }

  // Run ids look like "2026-09-20-1432" and sort chronologically, so the last
  // one alphabetically is the newest. The shape check excludes fixed-name
  // folders like "selftest", which would otherwise sort last and win forever.
  const folders = (await listing.json())
    .filter((entry) => entry.type === "dir" && /^\d{4}-\d{2}-\d{2}-\d{4}$/.test(entry.name))
    .map((entry) => entry.name)
    .sort();
  const latest = folders[folders.length - 1];

  if (!latest) {
    return telegram(env, "sendMessage", {
      chat_id: env.TELEGRAM_CHAT_ID,
      text: "No runs yet. Send “new video” to start one.",
    });
  }

  const stateFile = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/contents/runs/${latest}/state.json`,
    { headers: { ...headers, Accept: "application/vnd.github.raw" } },
  );
  const state = stateFile.ok ? await stateFile.json() : {};

  const lines = [
    `📊 Run ${latest}`,
    `Stage: ${state.chat_stage || "unknown"}`,
    `Finished: ${(state.stages_done || []).join(", ") || "nothing yet"}`,
  ];
  if (state.video_url) lines.push(`Video: ${state.video_url} (${state.video_privacy || "private"})`);

  return telegram(env, "sendMessage", {
    chat_id: env.TELEGRAM_CHAT_ID,
    text: lines.join("\n"),
  });
}
