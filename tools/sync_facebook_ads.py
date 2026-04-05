"""
Meta / Facebook Ads sync tool.
Pulls campaigns, ad sets, ads, and daily insights into Supabase.

Usage:
    python tools/sync_facebook_ads.py --lookback-days 30  (default)
    python tools/sync_facebook_ads.py --lookback-days 90
    python tools/sync_facebook_ads.py --mode full  (all-time history)
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import upsert_records
from utils import safe_decimal, days_ago, now_utc, log_sync_start, log_sync_complete

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_ad_account():
    from facebook_business.api import FacebookAdsApi
    from facebook_business.adobjects.adaccount import AdAccount

    FacebookAdsApi.init(
        app_id=os.environ["META_APP_ID"],
        app_secret=os.environ["META_APP_SECRET"],
        access_token=os.environ["META_ACCESS_TOKEN"],
    )
    return AdAccount(os.environ["META_AD_ACCOUNT_ID"])


# ── Campaigns ─────────────────────────────────────────────────────────────────

def sync_campaigns(account) -> tuple[int, dict]:
    """Sync campaigns. Returns (upserted_count, {external_id: uuid}) map."""
    from facebook_business.adobjects.campaign import Campaign

    fields = [
        Campaign.Field.id,
        Campaign.Field.name,
        Campaign.Field.status,
        Campaign.Field.objective,
        Campaign.Field.daily_budget,
        Campaign.Field.lifetime_budget,
        Campaign.Field.start_time,
        Campaign.Field.stop_time,
        Campaign.Field.created_time,
    ]

    campaigns = account.get_campaigns(fields=fields)
    records = []

    for c in campaigns:
        records.append({
            "external_id": str(c["id"]),
            "platform": "facebook",
            "name": c.get("name"),
            "status": c.get("status"),
            "objective": c.get("objective"),
            "daily_budget": float(safe_decimal(c.get("daily_budget", 0)) or 0) / 100,  # cents → dollars
            "lifetime_budget": float(safe_decimal(c.get("lifetime_budget", 0)) or 0) / 100,
            "start_time": c.get("start_time"),
            "stop_time": c.get("stop_time"),
            "created_at": c.get("created_time"),
            "last_synced_at": now_utc().isoformat(),
        })

    result = upsert_records("ad_campaigns", records)
    logger.info("Campaigns synced: %d", result["upserted"])

    # Build external_id → uuid map for downstream use
    from supabase_client import fetch_records
    rows = fetch_records("ad_campaigns", columns="id,external_id", limit=5000)
    id_map = {r["external_id"]: r["id"] for r in rows}
    return result["upserted"], id_map


# ── Ad Sets ───────────────────────────────────────────────────────────────────

def sync_ad_sets(account, campaign_id_map: dict) -> tuple[int, dict]:
    from facebook_business.adobjects.adset import AdSet

    fields = [
        AdSet.Field.id,
        AdSet.Field.name,
        AdSet.Field.status,
        AdSet.Field.campaign_id,
        AdSet.Field.daily_budget,
        AdSet.Field.bid_strategy,
        AdSet.Field.optimization_goal,
        AdSet.Field.targeting,
        AdSet.Field.start_time,
    ]

    ad_sets = account.get_ad_sets(fields=fields)
    records = []

    for s in ad_sets:
        campaign_uuid = campaign_id_map.get(str(s.get("campaign_id")))
        targeting = s.get("targeting", {})
        targeting_summary = {
            "age_min": targeting.get("age_min"),
            "age_max": targeting.get("age_max"),
            "geo_locations": targeting.get("geo_locations", {}).get("cities", []),
            "interests": [i.get("name") for i in targeting.get("flexible_spec", [{}])[0].get("interests", [])],
        } if targeting else {}

        records.append({
            "external_id": str(s["id"]),
            "campaign_id": campaign_uuid,
            "name": s.get("name"),
            "status": s.get("status"),
            "targeting_summary": targeting_summary,
            "daily_budget": float(safe_decimal(s.get("daily_budget", 0)) or 0) / 100,
            "bid_strategy": s.get("bid_strategy"),
            "optimization_goal": s.get("optimization_goal"),
            "start_time": s.get("start_time"),
            "stop_time": s.get("stop_time"),
            "last_synced_at": now_utc().isoformat(),
        })

    result = upsert_records("ad_sets", records)
    logger.info("Ad sets synced: %d", result["upserted"])

    from supabase_client import fetch_records
    rows = fetch_records("ad_sets", columns="id,external_id", limit=5000)
    id_map = {r["external_id"]: r["id"] for r in rows}
    return result["upserted"], id_map


# ── Ads ───────────────────────────────────────────────────────────────────────

def sync_ads(account, ad_set_id_map: dict, campaign_id_map: dict) -> tuple[int, dict]:
    from facebook_business.adobjects.ad import Ad

    fields = [
        Ad.Field.id,
        Ad.Field.name,
        Ad.Field.status,
        Ad.Field.adset_id,
        Ad.Field.campaign_id,
        Ad.Field.creative,
    ]

    ads = account.get_ads(fields=fields)
    records = []

    for a in ads:
        creative = a.get("creative", {})
        records.append({
            "external_id": str(a["id"]),
            "ad_set_id": ad_set_id_map.get(str(a.get("adset_id"))),
            "campaign_id": campaign_id_map.get(str(a.get("campaign_id"))),
            "name": a.get("name"),
            "status": a.get("status"),
            "creative_type": None,  # enriched separately if needed
            "headline": None,
            "body_text": None,
            "call_to_action": None,
            "last_synced_at": now_utc().isoformat(),
        })

    result = upsert_records("ads", records)
    logger.info("Ads synced: %d", result["upserted"])

    from supabase_client import fetch_records
    rows = fetch_records("ads", columns="id,external_id", limit=10000)
    id_map = {r["external_id"]: r["id"] for r in rows}
    return result["upserted"], id_map


# ── Daily Insights ────────────────────────────────────────────────────────────

def sync_insights(account, ad_id_map: dict, ad_set_id_map: dict, campaign_id_map: dict, lookback_days: int) -> int:
    from facebook_business.adobjects.adsinsights import AdsInsights

    date_start = days_ago(lookback_days).isoformat()
    date_stop = days_ago(0).isoformat()

    fields = [
        AdsInsights.Field.ad_id,
        AdsInsights.Field.adset_id,
        AdsInsights.Field.campaign_id,
        AdsInsights.Field.date_start,
        AdsInsights.Field.impressions,
        AdsInsights.Field.reach,
        AdsInsights.Field.clicks,
        AdsInsights.Field.spend,
        AdsInsights.Field.cpm,
        AdsInsights.Field.cpc,
        AdsInsights.Field.ctr,
        AdsInsights.Field.actions,  # contains leads
        AdsInsights.Field.action_values,
    ]

    params = {
        "level": "ad",
        "time_increment": 1,  # daily breakdown
        "time_range": {"since": date_start, "until": date_stop},
        "action_attribution_windows": ["7d_click", "1d_view"],
    }

    insights = account.get_insights(fields=fields, params=params)
    records = []

    for row in insights:
        ad_ext_id = str(row.get("ad_id", ""))
        adset_ext_id = str(row.get("adset_id", ""))
        campaign_ext_id = str(row.get("campaign_id", ""))

        # Extract lead count from actions array.
        # Use only "lead" action type — "onsite_conversion.lead_grouped" overlaps
        # with "lead" and double-counts the same form submissions.
        leads = 0
        for action in row.get("actions", []):
            if action.get("action_type") == "lead":
                leads += int(action.get("value", 0))

        spend = float(safe_decimal(row.get("spend", 0)) or 0)
        cpl = round(spend / leads, 4) if leads > 0 else None

        records.append({
            "ad_id": ad_id_map.get(ad_ext_id),
            "ad_set_id": ad_set_id_map.get(adset_ext_id),
            "campaign_id": campaign_id_map.get(campaign_ext_id),
            "date_start": row.get("date_start"),
            "impressions": int(row.get("impressions", 0)),
            "reach": int(row.get("reach", 0)),
            "clicks": int(row.get("clicks", 0)),
            "link_clicks": int(row.get("inline_link_clicks", 0)),
            "spend": spend,
            "leads": leads,
            "cpm": float(safe_decimal(row.get("cpm", 0)) or 0),
            "cpc": float(safe_decimal(row.get("cpc", 0)) or 0),
            "cpl": cpl,
            "ctr": float(safe_decimal(row.get("ctr", 0)) or 0),
            "raw_json": dict(row),
            "last_synced_at": now_utc().isoformat(),
        })

    # Insights use composite conflict key; upsert with ON CONFLICT (ad_id, date_start)
    result = upsert_records("ad_insights_daily", records, conflict_column="ad_id,date_start")
    logger.info("Ad insights synced: %d rows (lookback=%d days)", result["upserted"], lookback_days)
    return result["upserted"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync Meta/Facebook Ads data to Supabase")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    args = parser.parse_args()

    lookback = 365 if args.mode == "full" else args.lookback_days
    started_at = now_utc()
    log_id = log_sync_start("facebook_ads", args.mode)

    total_upserted = 0
    error_msg = None

    try:
        account = get_ad_account()
        count, campaign_map = sync_campaigns(account)
        total_upserted += count
        count, adset_map = sync_ad_sets(account, campaign_map)
        total_upserted += count
        count, ad_map = sync_ads(account, adset_map, campaign_map)
        total_upserted += count
        total_upserted += sync_insights(account, ad_map, adset_map, campaign_map, lookback)
        status = "success"
    except Exception as exc:
        logger.error("Facebook Ads sync failed: %s", exc, exc_info=True)
        error_msg = str(exc)
        status = "failed"

    log_sync_complete(
        log_id,
        status=status,
        records_fetched=total_upserted,
        records_upserted=total_upserted,
        error_message=error_msg,
        started_at=started_at,
    )
    sys.exit(0 if status == "success" else 1)


if __name__ == "__main__":
    main()
