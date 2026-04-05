# Sync Facebook / Meta Ads

## Objective
Pull campaign structure and daily performance insights from Meta Ads into Supabase for ad ROI analysis.

## Tool
`python tools/sync_facebook_ads.py --lookback-days [N] --mode [full|incremental]`

## Auth Setup (one-time)
1. Go to developers.facebook.com → create an app (type: Business)
2. Add product: Marketing API
3. Create a System User in Meta Business Manager → grant the System User access to your Ad Account
4. Generate a System User token with scopes: `ads_read`, `ads_management`
5. Get your Ad Account ID from Meta Business Manager (format: `act_XXXXXXXXX`)
6. Set in `.env`: `META_APP_ID`, `META_APP_SECRET`, `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`

**Note:** System User tokens don't expire (unlike User tokens which expire in 60 days). Use a System User for this integration.

## What Gets Synced

| Meta Object | Supabase Table | Conflict Key |
|---|---|---|
| Campaign | ad_campaigns | external_id |
| Ad Set | ad_sets | external_id |
| Ad | ads | external_id |
| Daily insights per ad | ad_insights_daily | (ad_id, date_start) |

## Insights Fields Tracked
impressions, reach, clicks, link_clicks, spend, leads, CPM, CPC, CPL, CTR

**Leads** are counted from the `actions` array in the API response, specifically action_type = `lead` or `onsite_conversion.lead_grouped`.

**CPL** (cost per lead) = spend / leads. Calculated in the tool. Null if no leads in that day.

## Lookback Window
- Default: 30 days (`--lookback-days 30`)
- For initial load: `--mode full` (365 days)
- Insights re-sync the same date range each run — existing rows are upserted (ON CONFLICT on ad_id + date_start)

## Edge Cases

**Deleted campaigns:** Archived status preserved in DB. Insights for deleted campaigns still accessible via API for 90 days after deletion.

**Async insights jobs:** For very large lookback windows (90+ days), the Meta API queues insights as async jobs. The SDK handles polling automatically but can take 1-5 minutes. If it times out, reduce `--lookback-days`.

**Attribution windows:** The tool requests `7d_click, 1d_view` attribution. Changing this will show different lead counts — keep it consistent.

**Rate limits:** Meta uses a token bucket rate limiter. The SDK respects `x-business-use-case-usage` headers automatically with exponential backoff.

**Budget in cents:** Meta returns budgets in cents (integer). The tool divides by 100 to store as dollars.

## Verification
```bash
python tools/sync_facebook_ads.py --lookback-days 7
```
Then check:
```sql
SELECT c.name AS campaign, SUM(i.spend) AS total_spend,
       SUM(i.leads) AS total_leads,
       ROUND(SUM(i.spend)/NULLIF(SUM(i.leads),0), 2) AS avg_cpl
FROM ad_insights_daily i
JOIN ad_campaigns c ON c.id = i.campaign_id
WHERE i.date_start >= CURRENT_DATE - 7
GROUP BY c.name
ORDER BY total_spend DESC;
```
