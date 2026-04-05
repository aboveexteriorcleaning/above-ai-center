# Sync Google Business Profile

## Objective
Pull Google reviews and business profile metrics (impressions, calls, etc.) into Supabase.

## Tool
`python tools/sync_google.py --days-back [N]`

## Auth Setup (one-time)
1. Go to console.cloud.google.com → create a project
2. Enable APIs: **My Business API**, **Business Profile Performance API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Run the OAuth flow once to get a refresh token:
   ```bash
   python tools/auth_google.py  # (see note below)
   ```
5. Set in `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_LOCATION_ID`

**Getting GOOGLE_LOCATION_ID:** After auth, call the accounts.locations.list API endpoint or use the Business Profile UI. Format: `accounts/XXXXXXXXX/locations/XXXXXXXXX`

**Note on auth_google.py:** This is a one-time setup script — run it interactively once to get the refresh token, then store it in `.env`. You can write this 10-line script using the `google-auth-oauthlib` library's `InstalledAppFlow`.

## What Gets Synced

| Google Data | Supabase Table | Conflict Key |
|---|---|---|
| Reviews | google_reviews | external_id (review ID) |
| Business metrics | google_business_metrics | metric_date (UNIQUE) |

## Metrics Tracked
searches_direct, searches_discovery, views_maps, views_search, calls, website_clicks, direction_requests

## Quota
Google My Business API: 1,000 requests/day. Daily sync (7am) is appropriate. Do not run more frequently.

## Edge Cases

**No new reviews:** The tool runs a full review pull each time (no incremental for reviews). This is safe — existing reviews are upserted by external_id.

**Review reply status:** If you reply to a review in Google Maps, the next sync will update `replied=true` and store the reply text.

**Insights API returns aggregate data:** The reportInsights endpoint returns data aggregated differently depending on the metric. Some metrics are only available in 4-week ranges. If you see gaps, check the Google Business Profile API documentation for metric-specific availability.

**API version deprecation:** Google deprecated the older My Business API v4 in favor of Business Profile Performance API. If sync fails with 404, check for API version updates and update the service name/version in `sync_google.py`.

## Verification
```bash
python tools/sync_google.py
```
Then check:
```sql
SELECT COUNT(*), AVG(rating), MIN(review_date), MAX(review_date) FROM google_reviews;
SELECT * FROM google_business_metrics ORDER BY metric_date DESC LIMIT 7;
```
