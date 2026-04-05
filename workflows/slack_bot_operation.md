# Slack Bot Operation

## Objective
Run the Slack bot as a persistent listener that routes business questions to the AI query engine and provides `/sync` command functionality.

## Tool
```bash
python tools/slack_bot.py
```

## Slack App Setup (one-time)
1. Go to api.slack.com/apps → Create New App → From scratch
2. **Enable Socket Mode** (Settings → Socket Mode → Enable → Generate App-Level Token with `connections:write` scope)
3. **OAuth & Permissions** → Bot Token Scopes:
   - `chat:write` — post messages
   - `chat:write.public` — post to channels without joining
   - `app_mentions:read` — receive @mentions
   - `channels:history` — read messages in channels
   - `commands` — handle slash commands
4. **Slash Commands** → Create `/sync` command (Request URL can be anything in Socket Mode)
5. **Event Subscriptions** → Enable → Subscribe to bot events: `message.channels`, `app_mention`
6. Install to workspace → Copy tokens to `.env`:
   - `SLACK_APP_TOKEN` = xapp-... (app-level token from step 2)
   - `SLACK_BOT_TOKEN` = xoxb-... (bot user OAuth token from step 5)
7. **Add the bot to your channel** → `SLACK_CHANNEL_ID` = C... (right-click channel → View channel details → channel ID at bottom)

## How to Use

**Ask a business question:**
- Just type in the designated channel: `What was my revenue last month?`
- Or @mention the bot anywhere: `@AboveAI which ads are performing best?`

**Sync commands (Slack slash command):**
- `/sync all` — sync all sources
- `/sync quickbooks` — sync QB only
- `/sync jobber` — sync Jobber only
- `/sync ads` or `/sync facebook` — sync Meta Ads
- `/sync google` — sync Google reviews
- `/sync gmail` — sync Gmail
- `/sync quo` or `/sync sms` — sync Quo SMS

## Response Format
Responses use Slack Block Kit:
1. **Header** — "Business Intelligence Answer"
2. **Answer** — Claude's synthesized plain-English answer
3. **Data table** — top 10 rows formatted as a code block (if data was returned)
4. **Context footer** — row count, chart hint, SQL preview

## Running in Production
To keep the bot running persistently, use one of:

**Option A — macOS launchd (runs on login):**
Create a `~/Library/LaunchAgents/com.aboveai.slackbot.plist` file pointing to `python tools/slack_bot.py`

**Option B — simple nohup:**
```bash
nohup python tools/slack_bot.py > .tmp/slack_bot.log 2>&1 &
```

**Option C — run bot + scheduler together:**
```bash
# Terminal 1
python tools/slack_bot.py

# Terminal 2
python tools/scheduler.py
```

## Edge Cases

**Slack 3-second timeout:** Socket Mode doesn't have a hard 3-second timeout like webhooks, but complex queries can be slow. The bot posts a "🤔 Thinking..." message immediately while the query runs, then deletes it and posts the real answer.

**Bot token expiry:** Bot tokens don't expire unless revoked. App-level tokens (xapp-) expire if Socket Mode is disabled and re-enabled. Regenerate from api.slack.com if you see auth errors.

**Rate limits:** Slack Tier 1: 1 message/second. The bot doesn't spam, so this is rarely an issue.

**Bot in wrong channel:** The message handler only processes messages from `SLACK_CHANNEL_ID`. Messages in other channels are silently ignored unless the bot is @mentioned.

**Query times out:** If the `query_engine` takes more than 30 seconds (rare), the bot will post an error. Check `sync_logs` to ensure data is populated.

## Verification
1. Start bot: `python tools/slack_bot.py` — should log "Starting Above AI Slack bot (Socket Mode)..."
2. Post in channel: `How many jobs did we complete this month?`
3. Should see "🤔 Thinking..." then a Block Kit response with answer + data
4. Run: `/sync jobber` — should post "Starting sync..." then "✅ Sync complete"
