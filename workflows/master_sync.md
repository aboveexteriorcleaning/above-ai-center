# Master Sync — All Sources

## Objective
Orchestrate a complete or partial data sync across all integrated platforms into Supabase.

## When to Run
- Automatically: via `scheduler.py` (incremental syncs throughout the day, full sync weekly Sunday 2am)
- Manually: `python tools/scheduler.py --run all`
- Via Slack: `/sync all`

## Required Inputs
- Valid credentials in `.env` for all sources
- Supabase schema already migrated (`tools/schema.sql` applied)

## Sync Order (dependency-aware)
Run in this order — customers must exist before jobs, jobs before line items, etc.

1. **sync_quickbooks.py** — QB customers, invoices, payments, expenses
2. **sync_jobber.py** — Jobber clients, jobs, quotes (overwrites customer data with fresher Jobber data)
3. **sync_facebook_ads.py** — Campaigns, ad sets, ads, daily insights
4. **sync_google.py** — Reviews, business metrics
5. **sync_gmail.py** — Email threads and message snippets
6. **sync_quo_sms.py** — SMS conversations and messages

## Expected Outputs
- All 17 Supabase tables populated or updated
- A `sync_logs` row per source with status, record counts, duration
- Slack notification on failure

## Edge Cases

**Partial failure:** If one source fails, continue with remaining sources. Log the failure. Each sync is independent.

**API downtime:** Check `sync_logs` for the failed source. Re-run manually: `python tools/scheduler.py --run [source]`

**Token expiry:** QuickBooks and Jobber OAuth tokens expire. If a sync fails with 401/auth error, re-run the OAuth flow for that service and update the refresh token in `.env`.

**Supabase connection failure:** Check `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`. Verify the project is active at supabase.com.

**Stale data:** If data looks old, check `sync_logs` for the last successful sync per source. Run a manual full sync for that source.

## Verification
```sql
-- Check last sync per source
SELECT source, status, records_upserted, completed_at, duration_seconds
FROM sync_logs
WHERE started_at > NOW() - INTERVAL '24 hours'
ORDER BY started_at DESC;

-- Quick record counts
SELECT 'customers' AS tbl, COUNT(*) FROM customers
UNION ALL SELECT 'jobs', COUNT(*) FROM jobs
UNION ALL SELECT 'ad_insights_daily', COUNT(*) FROM ad_insights_daily;
```
