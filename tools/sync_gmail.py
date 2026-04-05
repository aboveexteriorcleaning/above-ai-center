"""
Gmail sync tool.
Pulls email thread metadata and snippets into Supabase.
Stores snippets only (first 200 chars) — no full email bodies.

Usage:
    python tools/sync_gmail.py --days-back 30  (default)
    python tools/sync_gmail.py --days-back 90
"""

import os
import sys
import logging
import argparse
import base64
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import upsert_records
from utils import days_ago, now_utc, log_sync_start, log_sync_complete, find_customer_id_by_email

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Business email address (used to determine inbound vs outbound)
BUSINESS_EMAIL = os.getenv("GMAIL_ADDRESS", "").lower().strip()


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_gmail_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


# ── Threads ───────────────────────────────────────────────────────────────────

def sync_threads(days_back: int = 30) -> int:
    service = get_gmail_service()
    since = days_ago(days_back).isoformat()
    query = f"after:{since.replace('-', '/')}"

    thread_records = []
    message_records = []
    next_page_token = None

    while True:
        params = {"userId": "me", "q": query, "maxResults": 100}
        if next_page_token:
            params["pageToken"] = next_page_token

        response = service.users().threads().list(**params).execute()
        threads = response.get("threads", [])

        for thread_summary in threads:
            thread_id = thread_summary["id"]

            # Fetch thread detail (metadata only — no body)
            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()

            messages = thread.get("messages", [])
            if not messages:
                continue

            # Thread-level metadata from first and last messages
            first_msg = messages[0]
            last_msg = messages[-1]

            def get_header(msg, name):
                for h in msg.get("payload", {}).get("headers", []):
                    if h["name"].lower() == name.lower():
                        return h["value"]
                return None

            subject = get_header(first_msg, "Subject") or "(no subject)"
            last_snippet = last_msg.get("snippet", "")[:200]
            labels = list(set(
                label for msg in messages for label in msg.get("labelIds", [])
            ))
            has_unread = "UNREAD" in labels

            # Collect all participant email addresses
            participants = set()
            for msg in messages:
                from_addr = get_header(msg, "From") or ""
                to_addr = get_header(msg, "To") or ""
                for addr in (from_addr + "," + to_addr).split(","):
                    addr = addr.strip().lower()
                    if addr and "@" in addr:
                        # Extract email from "Name <email>" format
                        if "<" in addr:
                            addr = addr.split("<")[1].rstrip(">").strip()
                        participants.add(addr)

            # Determine last message timestamp
            last_date = get_header(last_msg, "Date")
            last_message_at = None
            if last_date:
                from email.utils import parsedate_to_datetime
                try:
                    last_message_at = parsedate_to_datetime(last_date).isoformat()
                except Exception:
                    pass

            # Try to match to a customer (check all participant emails)
            customer_id = None
            for email_addr in participants:
                if email_addr and email_addr != BUSINESS_EMAIL:
                    customer_id = find_customer_id_by_email(email_addr)
                    if customer_id:
                        break

            thread_records.append({
                "thread_id": thread_id,
                "customer_id": customer_id,
                "subject": subject[:500],
                "participants": list(participants),
                "message_count": len(messages),
                "last_message_at": last_message_at,
                "has_unread": has_unread,
                "labels": [l for l in labels if not l.startswith("Label_")],  # system labels only
                "last_synced_at": now_utc().isoformat(),
            })

            # Sync individual message metadata
            for msg in messages:
                from_addr = get_header(msg, "From") or ""
                if "<" in from_addr:
                    from_email = from_addr.split("<")[1].rstrip(">").strip().lower()
                else:
                    from_email = from_addr.strip().lower()

                direction = "outbound" if from_email == BUSINESS_EMAIL else "inbound"
                date_header = get_header(msg, "Date")
                sent_at = None
                if date_header:
                    from email.utils import parsedate_to_datetime
                    try:
                        sent_at = parsedate_to_datetime(date_header).isoformat()
                    except Exception:
                        pass

                message_records.append({
                    "external_id": msg["id"],
                    "thread_id": None,  # resolved after thread upsert
                    "customer_id": customer_id,
                    "from_address": from_email,
                    "to_addresses": [get_header(msg, "To") or ""],
                    "subject": subject[:500],
                    "snippet": msg.get("snippet", "")[:200],
                    "direction": direction,
                    "sent_at": sent_at,
                    "labels": msg.get("labelIds", []),
                    "last_synced_at": now_utc().isoformat(),
                })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    thread_result = upsert_records("email_threads", thread_records, conflict_column="thread_id")
    msg_result = upsert_records("email_messages", message_records)
    total = thread_result["upserted"] + msg_result["upserted"]
    logger.info("Gmail threads synced: %d, messages: %d", thread_result["upserted"], msg_result["upserted"])
    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync Gmail threads to Supabase")
    parser.add_argument("--days-back", type=int, default=30)
    args = parser.parse_args()

    started_at = now_utc()
    log_id = log_sync_start("gmail", "incremental")

    total_upserted = 0
    error_msg = None

    try:
        total_upserted = sync_threads(args.days_back)
        status = "success"
    except Exception as exc:
        logger.error("Gmail sync failed: %s", exc, exc_info=True)
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
