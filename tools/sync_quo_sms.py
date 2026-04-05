"""
OpenPhone SMS sync tool (stored under the Quo SMS name for consistency).
Pulls conversations and messages from OpenPhone into Supabase.

Usage:
    python tools/sync_quo_sms.py --days-back 30  (default)
    python tools/sync_quo_sms.py --days-back 7
"""

import os
import sys
import logging
import argparse
import requests
from datetime import timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import upsert_records
from utils import normalize_phone, days_ago, now_utc, log_sync_start, log_sync_complete, find_customer_id_by_phone

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://api.openphone.com/v1"


def _headers() -> dict:
    return {
        "Authorization": os.environ["QUO_API_KEY"],
        "Content-Type": "application/json",
    }


def _get(path: str, params: dict | None = None) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Phone Numbers ─────────────────────────────────────────────────────────────

def get_phone_number_ids() -> list[str]:
    data = _get("/phone-numbers")
    return [pn["id"] for pn in data.get("data", [])]


# ── Conversations ─────────────────────────────────────────────────────────────

def sync_conversations(phone_number_ids: list[str], since_iso: str) -> tuple[int, list[dict]]:
    """Sync conversations for all phone numbers. Returns (upserted_count, conversation list)."""
    records = []
    all_conversations = []

    for pn_id in phone_number_ids:
        page_cursor = None
        while True:
            params = {"phoneNumberId": pn_id, "maxResults": 100}
            if page_cursor:
                params["pageToken"] = page_cursor

            data = _get("/conversations", params=params)
            conversations = data.get("data", [])

            for c in conversations:
                updated_at = c.get("updatedAt") or c.get("createdAt", "")
                # Stop paginating once we pass the since_iso window
                if updated_at and updated_at < since_iso:
                    conversations = []
                    break

                # participants is a list of E.164 phone number strings
                participants = c.get("participants", [])
                phone_raw = participants[0] if participants else None

                phone = normalize_phone(phone_raw)
                customer_id = find_customer_id_by_phone(phone)

                records.append({
                    "external_id": c["id"],
                    "customer_id": customer_id,
                    "phone_number": phone,
                    "direction": "inbound",  # OpenPhone doesn't flag direction on conversation
                    "status": "open",
                    "last_message_at": c.get("lastActivityAt") or updated_at or None,
                    "message_count": c.get("totalItems", 0),
                    "created_at": c.get("createdAt"),
                    "last_synced_at": now_utc().isoformat(),
                })
                all_conversations.append(c)

            next_page = data.get("nextPageToken")
            if not next_page or not conversations:
                break
            page_cursor = next_page

    result = upsert_records("sms_conversations", records)
    logger.info("OpenPhone conversations synced: %d", result["upserted"])
    return result["upserted"], all_conversations


# ── Messages ──────────────────────────────────────────────────────────────────

def sync_messages(conversations: list[dict]) -> int:
    from supabase_client import fetch_records

    conv_rows = fetch_records("sms_conversations", columns="id,external_id", limit=10000)
    conv_id_map = {r["external_id"]: r["id"] for r in conv_rows}

    total_upserted = 0

    for c in conversations:
        conv_ext_id = c["id"]
        conv_uuid = conv_id_map.get(conv_ext_id)

        participants = c.get("participants", [])
        phone_raw = participants[0] if participants else None
        phone = normalize_phone(phone_raw)
        customer_id = find_customer_id_by_phone(phone)

        pn_id = c.get("phoneNumberId")
        if not pn_id or not phone_raw:
            continue

        page_cursor = None
        while True:
            params = {
                "phoneNumberId": pn_id,
                "participants": [phone_raw],
                "maxResults": 100,
            }
            if page_cursor:
                params["pageToken"] = page_cursor

            data = _get("/messages", params=params)
            messages = data.get("data", [])

            if not messages:
                break

            msg_records = []
            for m in messages:
                direction = "inbound" if m.get("direction") == "incoming" else "outbound"
                msg_records.append({
                    "external_id": m["id"],
                    "conversation_id": conv_uuid,
                    "customer_id": customer_id,
                    "direction": direction,
                    "body": m.get("text") or m.get("body") or "",
                    "sent_at": m.get("createdAt"),
                    "delivered_at": None,
                    "read_at": None,
                    "last_synced_at": now_utc().isoformat(),
                })

            result = upsert_records("sms_messages", msg_records)
            total_upserted += result["upserted"]

            next_page = data.get("nextPageToken")
            if not next_page:
                break
            page_cursor = next_page

    logger.info("OpenPhone messages synced: %d total", total_upserted)
    return total_upserted


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync OpenPhone SMS data to Supabase")
    parser.add_argument("--days-back", type=int, default=30)
    args = parser.parse_args()

    since_iso = days_ago(args.days_back).isoformat()
    started_at = now_utc()
    log_id = log_sync_start("quo_sms", "incremental")

    total_upserted = 0
    error_msg = None

    try:
        phone_number_ids = get_phone_number_ids()
        logger.info("Found %d OpenPhone number(s)", len(phone_number_ids))

        conv_count, conversation_list = sync_conversations(phone_number_ids, since_iso)
        total_upserted += conv_count
        total_upserted += sync_messages(conversation_list)
        status = "success"
    except Exception as exc:
        logger.error("OpenPhone sync failed: %s", exc, exc_info=True)
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
