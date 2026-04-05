# Sync Jobber

## Objective
Pull clients, jobs, quotes, and invoice data from Jobber via its GraphQL API into Supabase.

## Tool
`python tools/sync_jobber.py --mode [full|incremental] --days-back [N]`

## Auth Setup (one-time)
1. Go to developer.getjobber.com → create an app
2. Scopes needed: `READ_CLIENTS`, `READ_JOBS`, `READ_QUOTES`, `READ_INVOICES`
3. Complete OAuth 2.0 flow to get access + refresh tokens
4. Set in `.env`: `JOBBER_CLIENT_ID`, `JOBBER_CLIENT_SECRET`, `JOBBER_ACCESS_TOKEN`, `JOBBER_REFRESH_TOKEN`

## What Gets Synced

| Jobber Object | Supabase Table | Notes |
|---|---|---|
| Client | customers | external_id = `jobber_{ID}` |
| Job | jobs | service_type mapped from job title |
| Quote | quotes | status mapped from Jobber status enum |

## Service Type Mapping
Job titles are free-text in Jobber. The `normalize_service_type()` function maps keywords to canonical values:
- Roof, roof clean → `roof_cleaning`
- Soft wash, house wash → `softwash`
- Pressure wash, power wash, driveway → `pressure_washing`
- Window, windows → `window_cleaning`
- Fence, deck → `fence_deck`

**To add new mappings:** Edit `_SERVICE_MAP` in `tools/utils.py`

## Pagination
Jobber uses cursor-based pagination. The tool handles this automatically with `pageInfo.endCursor`. Default page size is 50 jobs per request.

## Edge Cases

**Token refresh:** Access tokens expire after 1 hour. The tool calls `_refresh_token_if_needed()` on startup. If the refresh token itself expires (rare), re-run the OAuth flow.

**Cancelled jobs:** Stored with `status='cancelled'`. Preserved in Supabase — never deleted.

**New service type not recognized:** Check logs for "Unknown service type" warnings. Add the keyword to `_SERVICE_MAP` in `utils.py`.

**Job title is null:** Defaults to `pressure_washing` service type. Update the job title in Jobber to improve classification.

**Customer overlap with QB:** Same customer may exist in both systems under different external_ids. The `query_engine` handles this by joining on name/email/phone when needed.

## Verification
```bash
python tools/sync_jobber.py --mode incremental --days-back 1
```
Then check:
```sql
SELECT service_type, status, COUNT(*), SUM(total_amount)
FROM jobs
GROUP BY service_type, status
ORDER BY 3 DESC;
```
