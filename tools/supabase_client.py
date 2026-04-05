"""
Supabase client — shared connection and upsert helpers.
All ETL tools import this module for database access.

Usage:
    from supabase_client import get_client, upsert_records, fetch_records, get_db_connection
"""

import os
import logging
import psycopg2
import psycopg2.extras
from typing import Any
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logger = logging.getLogger(__name__)

# ── Singleton Supabase client ──────────────────────────────────────────────────

_client: Client | None = None


def get_client() -> Client:
    """Return the singleton Supabase client (lazy-initialized)."""
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client


# ── Direct Postgres connection (for query_engine arbitrary SELECT) ─────────────

def get_db_connection() -> psycopg2.extensions.connection:
    """
    Return a direct psycopg2 connection to Supabase Postgres.
    Used by query_engine.py to execute arbitrary SELECT queries.
    Caller is responsible for closing the connection.
    """
    db_url = os.environ["SUPABASE_DB_URL"]
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.set_session(readonly=True, autocommit=True)
    return conn


# ── Upsert helpers ─────────────────────────────────────────────────────────────

def upsert_records(
    table: str,
    records: list[dict],
    conflict_column: str = "external_id",
) -> dict[str, int]:
    """
    Upsert a list of dicts into a Supabase table.

    Args:
        table:           Table name (e.g. "jobs", "invoices")
        records:         List of row dicts. All rows must share the same keys.
        conflict_column: Column used for ON CONFLICT resolution (default: "external_id").

    Returns:
        {"upserted": N, "failed": M}
    """
    if not records:
        return {"upserted": 0, "failed": 0}

    client = get_client()
    upserted = 0
    failed = 0

    # Supabase Python client upserts in one call; batch in chunks of 500
    chunk_size = 500
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        try:
            client.table(table).upsert(chunk, on_conflict=conflict_column).execute()
            upserted += len(chunk)
        except Exception as exc:
            logger.error("Upsert failed on table=%s chunk=%d: %s", table, i // chunk_size, exc)
            failed += len(chunk)

    logger.info("upsert_records table=%s upserted=%d failed=%d", table, upserted, failed)
    return {"upserted": upserted, "failed": failed}


def fetch_records(
    table: str,
    filters: dict[str, Any] | None = None,
    columns: str = "*",
    limit: int = 1000,
) -> list[dict]:
    """
    Fetch rows from a Supabase table with optional equality filters.

    Args:
        table:   Table name
        filters: Dict of {column: value} equality filters
        columns: Comma-separated column names (default "*")
        limit:   Max rows to return

    Returns:
        List of row dicts
    """
    client = get_client()
    query = client.table(table).select(columns).limit(limit)

    if filters:
        for col, val in filters.items():
            query = query.eq(col, val)

    response = query.execute()
    return response.data or []


def execute_sql(sql: str) -> list[dict]:
    """
    Execute a raw SELECT query via direct Postgres connection.
    Used by query_engine only. Enforces read-only session.

    Returns list of row dicts.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()
