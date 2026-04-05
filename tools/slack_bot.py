"""
Slack bot — listens for questions in a designated channel and answers them
using the AI query engine. Also handles /sync slash commands.

Run:
    python tools/slack_bot.py

Requires in .env:
    SLACK_APP_TOKEN   (xapp-... Socket Mode app-level token)
    SLACK_BOT_TOKEN   (xoxb-... bot user OAuth token)
    SLACK_CHANNEL_ID  (channel to listen in, e.g. C0XXXXXXXXX)
"""

import os
import sys
import logging
import subprocess
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = App(token=os.environ["SLACK_BOT_TOKEN"])

CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))

# Valid sync sources for /sync command
SYNC_SOURCES = {
    "quickbooks": "sync_quickbooks.py",
    "jobber": "sync_jobber.py",
    "ads": "sync_facebook_ads.py",
    "facebook": "sync_facebook_ads.py",
    "google": "sync_google.py",
    "gmail": "sync_gmail.py",
    "quo": "sync_quo_sms.py",
    "sms": "sync_quo_sms.py",
    "leads": "sync_leads_sheet.py",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_response_blocks(question: str, result: dict) -> list:
    """Build Slack Block Kit blocks from a query_engine result."""
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "Business Intelligence Answer"}
    })

    # Answer text
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": result["answer"]}
    })

    # Data table (if rows exist, show top 10 formatted as code block)
    rows = result.get("data", [])
    if rows:
        blocks.append({"type": "divider"})
        table_lines = []
        top_rows = rows[:10]
        if top_rows:
            headers = list(top_rows[0].keys())
            table_lines.append("  ".join(str(h)[:15] for h in headers))
            table_lines.append("-" * 60)
            for row in top_rows:
                table_lines.append("  ".join(str(row.get(h, ""))[:15] for h in headers))
            if len(rows) > 10:
                table_lines.append(f"... and {len(rows) - 10} more rows")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```\n{chr(10).join(table_lines)}\n```"}
        })

    # Context footer
    sql_preview = (result.get("sql_used") or "")[:120]
    if len(result.get("sql_used") or "") > 120:
        sql_preview += "..."
    context_text = f"📊 {len(rows)} rows | Chart: {result.get('chart_hint', 'none')}"
    if sql_preview:
        context_text += f"\n`{sql_preview}`"
    if result.get("error"):
        context_text += f"\n⚠️ Error: {result['error']}"

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": context_text}]
    })

    return blocks


def run_sync(source: str, say) -> None:
    """Run a sync script as a subprocess and report results to Slack."""
    script = SYNC_SOURCES.get(source.lower())
    if not script:
        say(f"Unknown source `{source}`. Valid options: {', '.join(SYNC_SOURCES.keys())}")
        return

    say(f"⏳ Starting sync for *{source}*...")
    script_path = os.path.join(TOOLS_DIR, script)

    try:
        proc = subprocess.run(
            [sys.executable, script_path, "--mode", "incremental"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if proc.returncode == 0:
            say(f"✅ Sync complete for *{source}*")
        else:
            error_lines = (proc.stderr or proc.stdout or "Unknown error")[-500:]
            say(f"❌ Sync failed for *{source}*:\n```{error_lines}```")
    except subprocess.TimeoutExpired:
        say(f"⏱️ Sync for *{source}* timed out after 5 minutes")
    except Exception as exc:
        say(f"❌ Error running sync for *{source}*: {exc}")


# ── Message handler ───────────────────────────────────────────────────────────

@app.message("")
def handle_message(message, say, client):
    """Handle any message in the designated channel."""
    # Only process messages from the configured channel
    if message.get("channel") != CHANNEL_ID:
        return
    # Ignore bot messages
    if message.get("bot_id") or message.get("subtype"):
        return

    text = message.get("text", "").strip()
    if not text:
        return

    # Remove bot mention if present
    text = text.replace(f"<@{app.client.token[:10]}", "").strip()

    # Post thinking indicator
    thinking_msg = client.chat_postMessage(
        channel=CHANNEL_ID,
        text="🤔 _Thinking..._",
    )

    try:
        from query_engine import answer_question
        result = answer_question(text)
        blocks = build_response_blocks(text, result)

        # Delete thinking message and post answer
        client.chat_delete(channel=CHANNEL_ID, ts=thinking_msg["ts"])
        client.chat_postMessage(
            channel=CHANNEL_ID,
            text=result["answer"],  # fallback for notifications
            blocks=blocks,
        )
    except Exception as exc:
        logger.error("Query failed: %s", exc, exc_info=True)
        client.chat_delete(channel=CHANNEL_ID, ts=thinking_msg["ts"])
        say(f"❌ Sorry, something went wrong: {exc}")


# ── Slash command: /sync ──────────────────────────────────────────────────────

@app.command("/sync")
def handle_sync_command(ack, body, say):
    """Handle /sync [source|all] command."""
    ack()
    source = (body.get("text") or "all").strip().lower()

    if source == "all":
        say("⏳ Starting full sync for all sources...")
        for src in SYNC_SOURCES:
            if src in ("facebook", "sms"):  # skip aliases
                continue
            run_sync(src, say)
        say("✅ All syncs complete!")
    else:
        run_sync(source, say)


# ── App mention handler ───────────────────────────────────────────────────────

@app.event("app_mention")
def handle_mention(event, say):
    """Handle @mention of the bot."""
    text = event.get("text", "")
    # Strip the mention itself (format: <@BOTID> question)
    text = re.sub(r"<@\w+>", "", text).strip()
    if not text:
        say("Hey! Ask me anything about the business — revenue, jobs, ads, reviews, and more.")
        return

    from query_engine import answer_question
    result = answer_question(text)
    blocks = build_response_blocks(text, result)
    say(blocks=blocks, text=result["answer"])


import re  # needed for handle_mention


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("Starting Above AI Slack bot (Socket Mode)...")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()


if __name__ == "__main__":
    main()
