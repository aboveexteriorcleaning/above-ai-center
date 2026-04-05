"""
Jobber sync tool.
Pulls clients, jobs, quotes, and invoices via Jobber's GraphQL API into Supabase.

Usage:
    python tools/sync_jobber.py --mode full
    python tools/sync_jobber.py --mode incremental  (default, last 7 days)
    python tools/sync_jobber.py --days-back 30
"""

import os
import sys
import logging
import argparse
import time
import requests
from datetime import timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import upsert_records, fetch_records
from utils import normalize_phone, normalize_service_type, safe_decimal, days_ago, now_utc, log_sync_start, log_sync_complete

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JOBBER_API_URL = "https://api.getjobber.com/api/graphql"


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_headers() -> dict:
    """Return Jobber API headers, refreshing token if needed."""
    access_token = os.environ["JOBBER_ACCESS_TOKEN"]
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-JOBBER-GRAPHQL-VERSION": "2026-03-10",
    }


def _refresh_token_if_needed():
    """Refresh Jobber OAuth token using refresh_token."""
    refresh_token = os.getenv("JOBBER_REFRESH_TOKEN")
    if not refresh_token:
        return
    resp = requests.post(
        "https://api.getjobber.com/api/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": os.environ["JOBBER_CLIENT_ID"],
            "client_secret": os.environ["JOBBER_CLIENT_SECRET"],
        },
    )
    if resp.ok:
        data = resp.json()
        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", refresh_token)
        os.environ["JOBBER_ACCESS_TOKEN"] = new_access
        os.environ["JOBBER_REFRESH_TOKEN"] = new_refresh
        _persist_tokens_to_env(new_access, new_refresh)
        logger.info("Jobber token refreshed")
    else:
        logger.warning("Jobber token refresh failed: %s", resp.text)


def _persist_tokens_to_env(access_token: str, refresh_token: str):
    """Write updated Jobber tokens back to .env so they survive process restarts."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        logger.warning("Could not find .env file to persist tokens")
        return
    with open(env_path, "r") as f:
        content = f.read()
    import re
    content = re.sub(r"^JOBBER_ACCESS_TOKEN=.*$", f"JOBBER_ACCESS_TOKEN={access_token}", content, flags=re.MULTILINE)
    content = re.sub(r"^JOBBER_REFRESH_TOKEN=.*$", f"JOBBER_REFRESH_TOKEN={refresh_token}", content, flags=re.MULTILINE)
    with open(env_path, "w") as f:
        f.write(content)
    logger.info("Jobber tokens persisted to .env")


def _gql(query: str, variables: dict | None = None, _retries: int = 6) -> dict:
    """Execute a GraphQL query against Jobber API with throttle-aware pacing."""
    for attempt in range(_retries):
        resp = requests.post(
            JOBBER_API_URL,
            json={"query": query, "variables": variables or {}},
            headers=get_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("errors", [])
        if errors:
            if any(e.get("extensions", {}).get("code") == "THROTTLED" for e in errors):
                wait = min(2 ** attempt, 60)
                logger.warning("Jobber throttled — waiting %ds (attempt %d/%d)", wait, attempt + 1, _retries)
                time.sleep(wait)
                continue
            raise RuntimeError(f"Jobber GraphQL errors: {errors}")

        # Proactively wait if quota is running low (< 20% remaining)
        throttle = data.get("extensions", {}).get("cost", {}).get("throttleStatus", {})
        actual_cost = data.get("extensions", {}).get("cost", {}).get("actualQueryCost")
        available = throttle.get("currentlyAvailable", 10000)
        maximum = throttle.get("maximumAvailable", 10000)
        restore_rate = throttle.get("restoreRate", 500)
        if actual_cost:
            logger.debug("Jobber query cost=%d available=%d/%d restore=%d/s", actual_cost, available, maximum, restore_rate)
        if maximum and available / maximum < 0.20:
            wait = (maximum * 0.5 - available) / restore_rate
            wait = max(1, min(wait, 60))
            logger.info("Jobber quota low (%d/%d) — waiting %.1fs", available, maximum, wait)
            time.sleep(wait)

        return data["data"]
    raise RuntimeError("Jobber API throttled after max retries")


# ── Clients → customers ───────────────────────────────────────────────────────

CLIENTS_QUERY = """
query GetClients($after: String) {
  clients(first: 100, after: $after) {
    nodes {
      id
      name
      firstName
      lastName
      email
      phones { number }
      billingAddress {
        street1
        street2
        city
        province
        postalCode
      }
      createdAt
      updatedAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def sync_clients() -> int:
    records = []
    cursor = None

    while True:
        data = _gql(CLIENTS_QUERY, {"after": cursor})
        nodes = data["clients"]["nodes"]
        page_info = data["clients"]["pageInfo"]

        for c in nodes:
            phone_raw = c["phones"][0]["number"] if c.get("phones") else None
            addr = c.get("billingAddress") or {}
            full_name = c.get("name") or f"{c.get('firstName','')} {c.get('lastName','')}".strip()

            records.append({
                "external_id": f"jobber_{c['id']}",
                "source": "jobber",
                "full_name": full_name,
                "email": (c.get("email") or "").lower().strip() or None,
                "phone": normalize_phone(phone_raw),
                "address_line1": addr.get("street1"),
                "address_line2": addr.get("street2"),
                "city": addr.get("city"),
                "state": addr.get("province") or "WA",
                "zip": addr.get("postalCode"),
                "created_at": c.get("createdAt"),
                "updated_at": c.get("updatedAt"),
                "last_synced_at": now_utc().isoformat(),
            })

        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    result = upsert_records("customers", records)
    logger.info("Jobber clients synced: %d", result["upserted"])
    return result["upserted"]


# ── Customer ID lookup ────────────────────────────────────────────────────────

def build_customer_id_lookup() -> dict[str, str]:
    """
    Return a mapping of {jobber_external_id → supabase_uuid} for all Jobber customers.
    Called after sync_clients() so the customers table is up to date.
    """
    rows = fetch_records("customers", filters={"source": "jobber"}, columns="id,external_id", limit=10000)
    return {r["external_id"]: r["id"] for r in rows}


# ── Jobs ──────────────────────────────────────────────────────────────────────

JOBS_QUERY = """
query GetJobs($after: String, $filter: JobFilterAttributes) {
  jobs(first: 50, after: $after, filter: $filter) {
    nodes {
      id
      title
      jobStatus
      startAt
      endAt
      completedAt
      total
      client { id }
      property { address { street city province postalCode } }
      createdAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def sync_jobs(since_date: str | None = None, customer_lookup: dict[str, str] | None = None) -> int:
    job_records = []
    line_item_records = []
    cursor = None
    filters = {}
    if since_date:
        filters["updatedAt"] = {"gt": since_date}

    while True:
        data = _gql(JOBS_QUERY, {"after": cursor, "filter": filters or None})
        nodes = data["jobs"]["nodes"]
        page_info = data["jobs"]["pageInfo"]

        for j in nodes:
            client_id_external = f"jobber_{j['client']['id']}" if j.get("client") else None
            customer_uuid = (customer_lookup or {}).get(client_id_external) if client_id_external else None
            addr = j.get("property", {}).get("address", {}) if j.get("property") else {}
            full_address = ", ".join(filter(None, [
                addr.get("street"), addr.get("city"), addr.get("province"), addr.get("postalCode")
            ])) if addr else None

            job_records.append({
                "external_id": f"jobber_job_{j['id']}",
                "customer_id": customer_uuid,
                "title": j.get("title"),
                "service_type": normalize_service_type(j.get("title")),
                "status": _map_job_status(j.get("jobStatus")),
                "scheduled_start": j.get("startAt"),
                "scheduled_end": j.get("endAt"),
                "completed_at": j.get("completedAt"),
                "total_amount": float(safe_decimal(j.get("total")) or 0),
                "notes": None,
                "job_address": full_address,
                "created_at": j.get("createdAt"),
                "last_synced_at": now_utc().isoformat(),
            })

            # Line items omitted from this query to stay within Jobber API quota limits.
            # Sync line items separately if needed.

        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    result = upsert_records("jobs", job_records)
    logger.info("Jobber jobs synced: %d", result["upserted"])
    return result["upserted"]


def _map_job_status(raw: str | None) -> str:
    if not raw:
        return "scheduled"
    mapping = {
        "QUOTE": "quote",
        "UPCOMING": "scheduled",
        "ACTIVE": "scheduled",
        "COMPLETED": "completed",
        "CANCELLED": "cancelled",
        "ARCHIVED": "completed",
    }
    return mapping.get(raw.upper(), "scheduled")


# ── Quotes ────────────────────────────────────────────────────────────────────

QUOTES_QUERY = """
query GetQuotes($after: String) {
  quotes(first: 100, after: $after) {
    nodes {
      id
      quoteStatus
      amounts { subtotal }
      sentAt
      client { id }
      createdAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def sync_quotes(customer_lookup: dict[str, str] | None = None) -> int:
    records = []
    cursor = None

    while True:
        data = _gql(QUOTES_QUERY, {"after": cursor})
        nodes = data["quotes"]["nodes"]
        page_info = data["quotes"]["pageInfo"]

        for q in nodes:
            client_id_external = f"jobber_{q['client']['id']}" if q.get("client") else None
            customer_uuid = (customer_lookup or {}).get(client_id_external) if client_id_external else None
            records.append({
                "external_id": f"jobber_quote_{q['id']}",
                "customer_id": customer_uuid,
                "status": _map_quote_status(q.get("quoteStatus")),
                "total_amount": float(safe_decimal((q.get("amounts") or {}).get("subtotal")) or 0),
                "sent_at": q.get("sentAt"),
                "approved_at": None,
                "created_at": q.get("createdAt"),
                "last_synced_at": now_utc().isoformat(),
            })

        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    result = upsert_records("quotes", records)
    logger.info("Jobber quotes synced: %d", result["upserted"])
    return result["upserted"]


def _map_quote_status(raw: str | None) -> str:
    mapping = {
        "DRAFT": "draft",
        "AWAITING_RESPONSE": "sent",
        "CHANGES_REQUESTED": "sent",
        "APPROVED": "approved",
        "ARCHIVED": "declined",
    }
    return mapping.get((raw or "").upper(), "draft")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync Jobber data to Supabase")
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--days-back", type=int, default=7)
    args = parser.parse_args()

    since_date = None if args.mode == "full" else days_ago(args.days_back).isoformat()
    started_at = now_utc()
    log_id = log_sync_start("jobber", args.mode)

    total_upserted = 0
    error_msg = None

    try:
        _refresh_token_if_needed()
        total_upserted += sync_clients()
        logger.info("Pausing 30s for Jobber API quota recovery...")
        time.sleep(30)
        customer_lookup = build_customer_id_lookup()
        logger.info("Customer lookup built: %d Jobber customers", len(customer_lookup))
        total_upserted += sync_jobs(since_date, customer_lookup=customer_lookup)
        logger.info("Pausing 30s for Jobber API quota recovery...")
        time.sleep(30)
        total_upserted += sync_quotes(customer_lookup=customer_lookup)
        status = "success"
    except Exception as exc:
        logger.error("Jobber sync failed: %s", exc, exc_info=True)
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
