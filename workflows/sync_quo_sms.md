# Sync Quo SMS

## Objective
Pull SMS conversation and message data from Quo into Supabase for customer communication tracking.

## Tool
`python tools/sync_quo_sms.py --days-back [N]`

## Auth Setup (one-time)
1. Log into your Quo account → Settings → API or Developer section
2. Generate an API key
3. Note your Quo base URL (e.g., `https://api.quo.com` or your custom subdomain)
4. Set in `.env`: `QUO_API_KEY`, `QUO_BASE_URL`

**⚠️ API Availability Note:** If Quo does not have a developer API, use the CSV export fallback instead:
- Export conversations from Quo → save to `.tmp/quo_export.csv`
- Run: `python tools/load_quo_csv.py` (to be built when needed)
- This is a manual process but achieves the same result

## What Gets Synced

| Quo Object | Supabase Table | Conflict Key |
|---|---|---|
| Conversation | sms_conversations | external_id |
| Message | sms_messages | external_id |

## Customer Matching
Phone numbers from Quo are normalized to E.164 format (+1XXXXXXXXXX) and matched against `customers.phone`. If matched, `customer_id` is linked.

## API Response Assumptions
The tool assumes a standard REST API shape:
- `GET /v1/conversations` → `{ "conversations": [...], "next_page": ... }`
- `GET /v1/conversations/{id}/messages` → `{ "messages": [...] }`

**If Quo's API uses different field names**, update the field mappings in `sync_quo_sms.py`:
- Conversation phone field: `c.get("phone") or c.get("phone_number") or c.get("contact", {}).get("phone")`
- Message body field: `m.get("body") or m.get("text") or m.get("message", "")`

## Edge Cases

**Unknown phone numbers:** Conversations from unknown numbers (not in customers table) are stored with `customer_id=NULL`. They still appear in SMS data and can be matched manually later.

**Very large conversation histories:** The tool paginates through all messages per conversation. For conversations with 500+ messages, this may be slow. Consider setting a message lookback limit.

**API version differences:** Quo is not a major platform — if the API endpoint paths differ from what's in the tool, update the `get()` method paths in `QuoClient`.

**No API available:** If Quo confirms no API access, the fallback is CSV export. Contact Quo support about API access — it may be a plan feature.

## Verification
```bash
python tools/sync_quo_sms.py --days-back 7
```
Then check:
```sql
SELECT COUNT(*) AS conversations, SUM(message_count) AS messages,
       COUNT(customer_id) AS matched_to_customer
FROM sms_conversations
WHERE last_message_at > NOW() - INTERVAL '7 days';
```
