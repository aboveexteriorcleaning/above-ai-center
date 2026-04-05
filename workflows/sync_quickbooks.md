# Sync QuickBooks Online

## Objective
Pull customers, invoices, payments, and expenses from QuickBooks Online into Supabase.

## Tool
`python tools/sync_quickbooks.py --mode [full|incremental] --days-back [N]`

## Auth Setup (one-time)
1. Go to developer.intuit.com → create a QuickBooks Online app
2. Add scopes: `com.intuit.quickbooks.accounting`
3. Run the OAuth 2.0 authorization flow to get a refresh token
4. Set in `.env`: `QB_CLIENT_ID`, `QB_CLIENT_SECRET`, `QB_REFRESH_TOKEN`, `QB_COMPANY_ID`
5. `QB_ENVIRONMENT=production` (use `sandbox` for testing)

## What Gets Synced

| QB Object | Supabase Table | Conflict Key |
|---|---|---|
| Customer | customers | external_id = `qb_{QB_ID}` |
| Invoice | invoices | external_id = `qb_inv_{QB_ID}` |
| Payment | payments | external_id = `qb_pay_{QB_ID}` |
| Purchase (expense) | expenses | external_id = `qb_exp_{QB_ID}_{line}` |

## Sync Modes
- `--mode incremental --days-back 7` (default): Only records updated in the last N days
- `--mode full`: All records (use for initial load or after a gap)

## Edge Cases

**Token rotation:** QB OAuth refresh tokens rotate on use. The new token is stored in `os.environ["QB_REFRESH_TOKEN"]` for the session. For persistence, manually update `.env` with the new token. Log message: "QB refresh token rotated — update QB_REFRESH_TOKEN in .env"

**Rate limits:** QB allows 500 requests/minute. If rate-limited, you'll get a 429. Reduce sync frequency or add `time.sleep(0.5)` between large batch queries.

**Voided invoices:** Synced with `status='void'`. Never deleted from Supabase.

**P&L report:** Not fetched by this sync tool. Instead, `query_engine.py` calls the QB Reporting API directly via `query_quickbooks_pl.py` whenever a revenue/profit question is asked. This gives authoritative Accrual-basis numbers without needing a separate P&L sync.

**Customer deduplication with Jobber:** QB and Jobber may have the same customer with different IDs. Use `phone` or `email` to cross-reference. The `external_id` prefix (`qb_` vs `jobber_`) keeps them distinct in the DB.

## Verification
```bash
python tools/sync_quickbooks.py --mode incremental --days-back 1
```
Then check Supabase:
```sql
SELECT COUNT(*), MAX(last_synced_at) FROM invoices WHERE source='quickbooks';
SELECT COUNT(*), MAX(last_synced_at) FROM payments WHERE source='quickbooks';
SELECT COUNT(*), MAX(last_synced_at) FROM expenses;
```
