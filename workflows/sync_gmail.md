# Sync Gmail

## Objective
Pull email thread metadata and snippets into Supabase for customer communication tracking.
Stores snippets only (200 chars max) — full email bodies are never stored.

## Tool
`python tools/sync_gmail.py --days-back [N]`

## Auth Setup (one-time)
1. Uses the same Google OAuth app as `sync_google.py`
2. Add additional scope: `https://www.googleapis.com/auth/gmail.readonly`
3. Re-run the OAuth flow to get a refresh token with both scopes
4. Set in `.env`: `GOOGLE_REFRESH_TOKEN` (same key, updated with new scope), `GMAIL_ADDRESS` (your business Gmail address)

**GMAIL_ADDRESS** is used to classify emails as inbound vs outbound. Set it to your exact Gmail address.

## What Gets Synced

| Gmail Object | Supabase Table | Conflict Key |
|---|---|---|
| Thread | email_threads | thread_id |
| Message metadata | email_messages | external_id (message ID) |

## Privacy Design
- **No full bodies stored** — only the Gmail `snippet` field (first ~200 chars)
- Participant email addresses are stored for customer matching
- This keeps the database lean and avoids storing sensitive customer communications

## Customer Matching
The tool attempts to match email threads to customers by comparing participant email addresses against `customers.email`. If matched, `customer_id` is populated on both the thread and individual messages.

## Edge Cases

**High thread volume:** If your Gmail has thousands of threads, the `--days-back` filter keeps sync manageable. Start with 30 days for initial load.

**Label filtering:** The tool filters out custom label IDs (Label_XXXXXX format) and keeps only system labels (INBOX, SENT, IMPORTANT, etc.).

**OAuth scope conflict:** If the Google refresh token was generated for only the Business Profile API scope, it won't work for Gmail. You need to re-run the OAuth flow with both scopes combined. The refresh token will cover both.

**Thread grows after sync:** Email threads are upserted on `thread_id`. When a thread gets new replies, the next sync updates `message_count` and `last_message_at`.

**Spam/marketing emails:** No filtering is applied — all threads in the lookback window are synced. If volume is too high, add label filters in the `query` variable inside `sync_threads()`.

## Verification
```bash
python tools/sync_gmail.py --days-back 7
```
Then check:
```sql
SELECT COUNT(*) AS threads, SUM(message_count) AS messages,
       COUNT(customer_id) AS matched_to_customer
FROM email_threads
WHERE last_message_at > NOW() - INTERVAL '7 days';
```
