"""
Shared utility functions used across all ETL tools.
"""

import re
import logging
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from supabase_client import get_client

logger = logging.getLogger(__name__)

# ── Phone normalization ────────────────────────────────────────────────────────

def normalize_phone(raw: str | None) -> str | None:
    """Strip all non-digits and format as E.164 (+1XXXXXXXXXX for US numbers)."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return digits or None


# ── Service type normalization ─────────────────────────────────────────────────

_SERVICE_MAP = {
    "roof": "roof_cleaning",
    "roof clean": "roof_cleaning",
    "roof cleaning": "roof_cleaning",
    "soft wash": "softwash",
    "softwash": "softwash",
    "soft washing": "softwash",
    "house wash": "softwash",
    "home wash": "softwash",
    "siding": "softwash",
    "pressure wash": "pressure_washing",
    "pressure washing": "pressure_washing",
    "powerwash": "pressure_washing",
    "power wash": "pressure_washing",
    "driveway": "pressure_washing",
    "window": "window_cleaning",
    "windows": "window_cleaning",
    "window cleaning": "window_cleaning",
    "window wash": "window_cleaning",
    "fence": "fence_deck",
    "deck": "fence_deck",
    "fence cleaning": "fence_deck",
    "deck cleaning": "fence_deck",
    "deck restoration": "fence_deck",
    "fence restoration": "fence_deck",
}

VALID_SERVICE_TYPES = {
    "roof_cleaning",
    "softwash",
    "pressure_washing",
    "window_cleaning",
    "fence_deck",
}


def normalize_service_type(raw: str | None) -> str:
    """Map a free-text job title to one of the canonical service_type values."""
    if not raw:
        return "pressure_washing"  # safe default
    lower = raw.lower().strip()
    # Exact match first
    if lower in _SERVICE_MAP:
        return _SERVICE_MAP[lower]
    # Keyword scan
    for keyword, stype in _SERVICE_MAP.items():
        if keyword in lower:
            return stype
    logger.debug("Unknown service type %r — defaulting to pressure_washing", raw)
    return "pressure_washing"


# ── Decimal helpers ────────────────────────────────────────────────────────────

def safe_decimal(value: Any) -> Decimal | None:
    """Convert any numeric or string value to Decimal; return None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


# ── Date helpers ───────────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: int) -> date:
    return (datetime.now(timezone.utc) - timedelta(days=n)).date()


def iso(dt: datetime | date | None) -> str | None:
    """Return ISO 8601 string or None."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


# ── List chunking ──────────────────────────────────────────────────────────────

def chunk_list(lst: list, size: int) -> list[list]:
    """Split a list into sub-lists of at most `size` elements."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]


# ── Sync logging ───────────────────────────────────────────────────────────────

def log_sync_start(source: str, sync_type: str = "incremental") -> str:
    """
    Insert a sync_logs row with status='running'.
    Returns the new log row's id (uuid string).
    """
    client = get_client()
    row = {
        "source": source,
        "sync_type": sync_type,
        "status": "running",
        "records_fetched": 0,
        "records_upserted": 0,
        "records_failed": 0,
        "started_at": now_utc().isoformat(),
    }
    response = client.table("sync_logs").insert(row).execute()
    log_id = response.data[0]["id"]
    logger.info("Sync started: source=%s type=%s log_id=%s", source, sync_type, log_id)
    return log_id


def log_sync_complete(
    log_id: str,
    status: str,
    records_fetched: int = 0,
    records_upserted: int = 0,
    records_failed: int = 0,
    error_message: str | None = None,
    started_at: datetime | None = None,
) -> None:
    """Update a sync_logs row to final status."""
    client = get_client()
    completed_at = now_utc()
    duration = None
    if started_at:
        duration = (completed_at - started_at).total_seconds()

    client.table("sync_logs").update({
        "status": status,
        "records_fetched": records_fetched,
        "records_upserted": records_upserted,
        "records_failed": records_failed,
        "error_message": error_message,
        "completed_at": completed_at.isoformat(),
        "duration_seconds": duration,
    }).eq("id", log_id).execute()

    logger.info(
        "Sync complete: log_id=%s status=%s fetched=%d upserted=%d failed=%d",
        log_id, status, records_fetched, records_upserted, records_failed,
    )


# ── .env persistence ───────────────────────────────────────────────────────────

def persist_env_var(key: str, value: str, env_path: str | None = None) -> None:
    """
    Update a single key=value line in the .env file on disk.
    If the key exists, it's replaced in-place. If not, it's appended.
    Also updates os.environ so the change is immediately visible in-process.
    """
    import os
    import re

    if env_path is None:
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.abspath(env_path)

    try:
        with open(env_path, "r") as f:
            content = f.read()

        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        new_line = f"{key}={value}"

        if pattern.search(content):
            content = pattern.sub(new_line, content)
        else:
            content = content.rstrip("\n") + f"\n{new_line}\n"

        with open(env_path, "w") as f:
            f.write(content)

        os.environ[key] = value
        logger.info("Persisted %s to .env", key)
    except Exception as exc:
        logger.warning("Could not persist %s to .env: %s", key, exc)


# ── Customer matching ──────────────────────────────────────────────────────────

def find_customer_id_by_phone(phone: str | None) -> str | None:
    """Look up a customer uuid by normalized phone number. Returns None if not found."""
    if not phone:
        return None
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    from supabase_client import fetch_records
    rows = fetch_records("customers", filters={"phone": normalized}, columns="id", limit=1)
    return rows[0]["id"] if rows else None


def find_customer_id_by_email(email: str | None) -> str | None:
    """Look up a customer uuid by email address. Returns None if not found."""
    if not email:
        return None
    from supabase_client import fetch_records
    rows = fetch_records("customers", filters={"email": email.lower().strip()}, columns="id", limit=1)
    return rows[0]["id"] if rows else None
