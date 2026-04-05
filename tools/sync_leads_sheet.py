"""
Google Sheets lead sync tool.
Pulls leads from the master lead tracking sheet into Supabase.
Classifies each lead as 'meta' (fb/ig) or 'website' and matches to customers by phone.

Usage:
    python tools/sync_leads_sheet.py
"""

import os
import sys
import re
import logging
from datetime import timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from supabase_client import upsert_records, fetch_records, get_db_connection
from utils import normalize_phone, now_utc, log_sync_start, log_sync_complete

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SHEET_ID = "1D4GG_0mQwMgDi5tZEgZwQi7-Eq9JxULiuARlCedsH7c"
SHEET_NAME = "Sheet1"

META_PLATFORMS = {"fb", "ig", "facebook", "instagram"}


def get_sheets_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)


def classify_lead_source(platform: str) -> str:
    """Return 'meta' for Facebook/Instagram leads, 'website' for everything else."""
    if (platform or "").strip().lower() in META_PLATFORMS:
        return "meta"
    return "website"


def normalize_lead_phone(raw: str) -> str | None:
    """Strip the 'p:' prefix Jobber adds, then normalize."""
    if not raw:
        return None
    cleaned = re.sub(r"^p:", "", raw.strip())
    return normalize_phone(cleaned)


def build_phone_to_customer_map() -> dict[str, str]:
    """Return {normalized_phone: customer_uuid} for all Jobber customers with a phone."""
    rows = fetch_records("customers", filters={"source": "jobber"}, columns="id,phone", limit=10000)
    mapping = {}
    for r in rows:
        phone = normalize_phone(r.get("phone") or "")
        if phone:
            mapping[phone] = r["id"]
    return mapping


def fetch_sheet_rows() -> list[dict]:
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A1:Z10000",
    ).execute()
    rows = result.get("values", [])
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


def sync_leads() -> int:
    log_id = log_sync_start("leads_sheet", "full")
    phone_to_customer = build_phone_to_customer_map()
    logger.info("Customer phone map built: %d entries", len(phone_to_customer))

    rows = fetch_sheet_rows()
    logger.info("Sheet rows fetched: %d", len(rows))

    records = []
    for r in rows:
        lead_id = r.get("id", "").strip()
        if not lead_id:
            continue

        platform = r.get("platform", "").strip()
        lead_source = classify_lead_source(platform)

        phone = normalize_lead_phone(r.get("phone", ""))
        customer_id = phone_to_customer.get(phone) if phone else None

        full_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()

        created_raw = r.get("created_time", "")
        created_time = None
        if created_raw:
            try:
                from datetime import datetime
                created_time = datetime.fromisoformat(created_raw).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass

        records.append({
            "external_id": lead_id,
            "lead_source": lead_source,
            "platform": platform,
            "first_name": r.get("first_name", "").strip() or None,
            "last_name": r.get("last_name", "").strip() or None,
            "full_name": full_name or None,
            "email": r.get("email", "").strip().lower() or None,
            "phone": phone,
            "city": r.get("city", "").strip() or None,
            "campaign_name": r.get("campaign_name", "").strip() or None,
            "ad_name": r.get("ad_name", "").strip() or None,
            "lead_status": r.get("lead_status", "").strip() or None,
            "customer_id": customer_id,
            "created_time": created_time,
            "last_synced_at": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    result = upsert_records("leads", records, conflict_column="external_id")
    matched = sum(1 for r in records if r["customer_id"])
    logger.info(
        "Leads synced: %d upserted, %d matched to customers, %d unmatched",
        result["upserted"], matched, len(records) - matched,
    )
    log_sync_complete(log_id, len(records), result["upserted"], result["failed"])
    return result["upserted"]


def main():
    synced = sync_leads()
    print(f"Done — {synced} leads synced")


if __name__ == "__main__":
    main()
