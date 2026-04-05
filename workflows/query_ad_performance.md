# Workflow: Ad Performance Queries

## Objective
Answer questions about Facebook/Meta ad performance accurately, with correct CPL, spend, lead, and ROAS calculations.

## Data Source
Table: `ad_insights_daily`
- One row per ad per day
- Key fields: `date_start`, `spend`, `leads`, `impressions`, `clicks`, `cpm`, `cpc`, `cpl`, `ctr`, `roas`
- Joined to: `ads`, `ad_sets`, `ad_campaigns` for names

Synced every 4 hours (last 30 days). Full year available after Sunday full sync.

## CRITICAL: CPL Calculation

**NEVER use `AVG(cpl)`** — the stored `cpl` column is a per-ad, per-day value. Averaging it weights
a day with 1 lead equally to a day with 50 leads, producing nonsense.

**Always compute CPL as:**
```sql
ROUND(SUM(spend) / NULLIF(SUM(leads), 0), 2) AS avg_cpl
```

This is: total dollars spent ÷ total leads generated. That is the real cost per lead.

**Lead count source (CRITICAL):** The denominator is always `ad_insights_daily.leads` — the count
Facebook reports via its API. NEVER use `COUNT(*)` from the `leads` table for CPL. The `leads` table
is Google Sheets / Jobber-matched data with a ~45% match rate; it undercounts actual leads and must
not be used as the denominator in any CPL calculation.

## Common Query Patterns

### Average CPL for a period
```sql
SELECT
  SUM(spend)                                     AS total_spend,
  SUM(leads)                                     AS total_leads,
  ROUND(SUM(spend) / NULLIF(SUM(leads), 0), 2)  AS avg_cpl
FROM ad_insights_daily
WHERE date_start >= '2026-01-01' AND date_start < '2027-01-01';
```

### CPL by campaign
```sql
SELECT
  c.name                                         AS campaign,
  SUM(i.spend)                                   AS total_spend,
  SUM(i.leads)                                   AS total_leads,
  ROUND(SUM(i.spend) / NULLIF(SUM(i.leads), 0), 2) AS cpl
FROM ad_insights_daily i
JOIN ad_campaigns c ON i.campaign_id = c.id
WHERE i.date_start >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY c.name
ORDER BY cpl ASC NULLS LAST;
```

### Monthly spend + leads trend
```sql
SELECT
  DATE_TRUNC('month', date_start)::date          AS month,
  ROUND(SUM(spend), 2)                           AS total_spend,
  SUM(leads)                                     AS total_leads,
  ROUND(SUM(spend) / NULLIF(SUM(leads), 0), 2)  AS cpl
FROM ad_insights_daily
WHERE date_start >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY 1
ORDER BY 1;
```

## Edge Cases
- Days with 0 leads have `cpl = NULL` in the stored column — correct behavior. They are still included in `SUM(spend)`.
- If `SUM(leads) = 0` for the whole period, CPL returns NULL — note this in the answer.
- Facebook ad data updates retroactively due to attribution windows; data from the last 7 days may shift slightly.
