"""
Google Business Profile sync tool.
Pulls reviews and business metrics (impressions, calls, etc.) into Supabase.

Usage:
    python tools/sync_google.py
    python tools/sync_google.py --days-back 90
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import upsert_records
from utils import days_ago, now_utc, log_sync_start, log_sync_complete

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_google_service(api_name: str, version: str, scopes: list[str]):
    """Build an authenticated Google API service client."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=scopes,
    )
    creds.refresh(Request())
    return build(api_name, version, credentials=creds)


# ── Reviews ───────────────────────────────────────────────────────────────────

def sync_reviews() -> int:
    """Pull all Google reviews for the business location."""
    service = get_google_service(
        "mybusiness", "v4",
        scopes=["https://www.googleapis.com/auth/business.manage"],
    )

    location_id = os.environ["GOOGLE_LOCATION_ID"]
    records = []
    next_page_token = None

    while True:
        params = {"pageSize": 50}
        if next_page_token:
            params["pageToken"] = next_page_token

        response = service.accounts().locations().reviews().list(
            parent=location_id, **params
        ).execute()

        for r in response.get("reviews", []):
            review_id = r.get("reviewId", "")
            rating_map = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
            rating = rating_map.get(r.get("starRating", ""), None)

            reply = r.get("reviewReply", {})
            records.append({
                "external_id": review_id,
                "reviewer_name": r.get("reviewer", {}).get("displayName"),
                "rating": rating,
                "review_text": r.get("comment"),
                "replied": bool(reply),
                "reply_text": reply.get("comment") if reply else None,
                "review_date": r.get("createTime", "")[:10] if r.get("createTime") else None,
                "reply_date": reply.get("updateTime", "")[:10] if reply else None,
                "last_synced_at": now_utc().isoformat(),
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    result = upsert_records("google_reviews", records)
    logger.info("Google reviews synced: %d", result["upserted"])
    return result["upserted"]


# ── Business Metrics ──────────────────────────────────────────────────────────

def sync_business_metrics(days_back: int = 90) -> int:
    """Pull Google Business Profile search and action metrics."""
    service = get_google_service(
        "mybusiness", "v4",
        scopes=["https://www.googleapis.com/auth/business.manage"],
    )

    location_id = os.environ["GOOGLE_LOCATION_ID"]
    start_date = days_ago(days_back)
    end_date = days_ago(0)

    body = {
        "locationNames": [location_id],
        "basicRequest": {
            "metricRequests": [
                {"metric": "QUERIES_DIRECT"},
                {"metric": "QUERIES_INDIRECT"},
                {"metric": "VIEWS_MAPS"},
                {"metric": "VIEWS_SEARCH"},
                {"metric": "ACTIONS_PHONE"},
                {"metric": "ACTIONS_WEBSITE"},
                {"metric": "ACTIONS_DRIVING_DIRECTIONS"},
            ],
            "timeRange": {
                "startTime": f"{start_date.isoformat()}T00:00:00Z",
                "endTime": f"{end_date.isoformat()}T23:59:59Z",
            },
        },
    }

    # Extract account name from location_id (format: accounts/XXX/locations/XXX)
    account_name = "/".join(location_id.split("/")[:2])
    response = service.accounts().locations().reportInsights(
        name=account_name, body=body
    ).execute()

    records = []
    for loc_metrics in response.get("locationMetrics", []):
        # Aggregate metrics by date
        date_data: dict = {}

        for metric_series in loc_metrics.get("metricValues", []):
            metric_name = metric_series.get("metric")
            for dv in metric_series.get("dimensionalValues", []):
                time_dim = dv.get("timeDimension", {})
                date_str = time_dim.get("timeRange", {}).get("startTime", "")[:10]
                if not date_str:
                    continue
                if date_str not in date_data:
                    date_data[date_str] = {}
                date_data[date_str][metric_name] = int(dv.get("value", 0))

        for date_str, metrics in date_data.items():
            records.append({
                "metric_date": date_str,
                "searches_direct": metrics.get("QUERIES_DIRECT", 0),
                "searches_discovery": metrics.get("QUERIES_INDIRECT", 0),
                "views_maps": metrics.get("VIEWS_MAPS", 0),
                "views_search": metrics.get("VIEWS_SEARCH", 0),
                "calls": metrics.get("ACTIONS_PHONE", 0),
                "website_clicks": metrics.get("ACTIONS_WEBSITE", 0),
                "direction_requests": metrics.get("ACTIONS_DRIVING_DIRECTIONS", 0),
                "last_synced_at": now_utc().isoformat(),
            })

    result = upsert_records("google_business_metrics", records, conflict_column="metric_date")
    logger.info("Google business metrics synced: %d days", result["upserted"])
    return result["upserted"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync Google Business Profile data to Supabase")
    parser.add_argument("--days-back", type=int, default=90)
    args = parser.parse_args()

    started_at = now_utc()
    log_id = log_sync_start("google", "incremental")

    total_upserted = 0
    error_msg = None

    try:
        total_upserted += sync_reviews()
        total_upserted += sync_business_metrics(args.days_back)
        status = "success"
    except Exception as exc:
        logger.error("Google sync failed: %s", exc, exc_info=True)
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
