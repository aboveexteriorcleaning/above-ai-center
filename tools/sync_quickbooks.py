"""
QuickBooks Online sync tool.
Pulls customers, invoices, payments, and expenses into Supabase.

Usage:
    python tools/sync_quickbooks.py --mode full
    python tools/sync_quickbooks.py --mode incremental  (default, last 7 days)
    python tools/sync_quickbooks.py --days-back 30
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

# Allow running from project root or tools/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from supabase_client import upsert_records
from utils import safe_decimal, normalize_phone, days_ago, now_utc, log_sync_start, log_sync_complete, persist_env_var

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── QuickBooks OAuth token refresh ────────────────────────────────────────────

def get_qb_client():
    """Return an authenticated QuickBooks client, refreshing the token if needed."""
    from intuitlib.client import AuthClient
    from quickbooks import QuickBooks

    auth_client = AuthClient(
        client_id=os.environ["QB_CLIENT_ID"],
        client_secret=os.environ["QB_CLIENT_SECRET"],
        environment=os.getenv("QB_ENVIRONMENT", "production"),
        redirect_uri="https://aboveexteriorcleaning.com/qb-callback",
    )

    # Refresh using stored refresh token
    auth_client.refresh(refresh_token=os.environ["QB_REFRESH_TOKEN"])

    # Persist the new refresh token back to .env in memory (not disk)
    # In production, write this to a secrets store or update .env programmatically
    if auth_client.refresh_token and auth_client.refresh_token != os.environ["QB_REFRESH_TOKEN"]:
        logger.info("QB refresh token rotated — persisting to .env")
        persist_env_var("QB_REFRESH_TOKEN", auth_client.refresh_token)

    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=auth_client.refresh_token,
        company_id=os.environ["QB_COMPANY_ID"],
    )
    return client


# ── Pagination helper ─────────────────────────────────────────────────────────

def _paginate(qb_class, base_query: str, client, page_size: int = 1000) -> list:
    """Fetch all records using STARTPOSITION pagination."""
    all_records = []
    start = 1
    while True:
        page_query = f"{base_query} STARTPOSITION {start} MAXRESULTS {page_size}"
        batch = qb_class.query(page_query, qb=client)
        all_records.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return all_records


# ── Customers ─────────────────────────────────────────────────────────────────

def sync_customers(client, since_date: str | None = None) -> int:
    from quickbooks.objects.customer import Customer

    base_query = "SELECT * FROM Customer"
    if since_date:
        base_query += f" WHERE MetaData.LastUpdatedTime >= '{since_date}'"

    customers = _paginate(Customer, base_query, client)
    records = []

    for c in customers:
        phone = normalize_phone(
            getattr(c.PrimaryPhone, "FreeFormNumber", None) if c.PrimaryPhone else None
        )
        email = c.PrimaryEmailAddr.Address if c.PrimaryEmailAddr else None
        addr = c.BillAddr

        records.append({
            "external_id": f"qb_{c.Id}",
            "source": "quickbooks",
            "full_name": c.DisplayName or c.FullyQualifiedName or "",
            "email": email.lower().strip() if email else None,
            "phone": phone,
            "address_line1": getattr(addr, "Line1", None) if addr else None,
            "city": getattr(addr, "City", None) if addr else None,
            "state": getattr(addr, "CountrySubDivisionCode", "WA") if addr else "WA",
            "zip": getattr(addr, "PostalCode", None) if addr else None,
            "last_synced_at": now_utc().isoformat(),
        })

    result = upsert_records("customers", records)
    logger.info("Customers synced: %d", result["upserted"])
    return result["upserted"]


# ── Invoices ──────────────────────────────────────────────────────────────────

def sync_invoices(client, since_date: str | None = None) -> int:
    from quickbooks.objects.invoice import Invoice

    base_query = "SELECT * FROM Invoice"
    if since_date:
        base_query += f" WHERE MetaData.LastUpdatedTime >= '{since_date}'"

    invoices = _paginate(Invoice, base_query, client)
    records = []

    for inv in invoices:
        records.append({
            "external_id": f"qb_inv_{inv.Id}",
            "source": "quickbooks",
            "customer_id": None,  # resolved post-sync via external_id cross-reference
            "invoice_number": inv.DocNumber,
            "status": _map_invoice_status(inv.EmailStatus, inv.Balance),
            "subtotal": float(safe_decimal(getattr(inv, "SubTotal", None)) or 0),
            "tax_amount": float(safe_decimal(inv.TxnTaxDetail.TotalTax) if getattr(inv, "TxnTaxDetail", None) else 0),
            "total_amount": float(safe_decimal(inv.TotalAmt) or 0),
            "amount_paid": float(safe_decimal(inv.TotalAmt) or 0) - float(safe_decimal(inv.Balance) or 0),
            "balance_due": float(safe_decimal(inv.Balance) or 0),
            "due_date": inv.DueDate,
            "paid_date": None,  # QB doesn't expose paid_date directly on invoice
            "created_at": (inv.MetaData.get("CreateTime") if isinstance(inv.MetaData, dict) else getattr(inv.MetaData, "CreateTime", None)) if inv.MetaData else None,
            "last_synced_at": now_utc().isoformat(),
        })

    result = upsert_records("invoices", records)
    logger.info("Invoices synced: %d", result["upserted"])
    return result["upserted"]


def _map_invoice_status(email_status: str, balance) -> str:
    balance_val = float(safe_decimal(balance) or 0)
    if balance_val == 0:
        return "paid"
    if email_status == "EmailSent":
        return "sent"
    return "draft"


# ── Payments ──────────────────────────────────────────────────────────────────

def sync_payments(client, since_date: str | None = None) -> int:
    from quickbooks.objects.payment import Payment

    base_query = "SELECT * FROM Payment"
    if since_date:
        base_query += f" WHERE MetaData.LastUpdatedTime >= '{since_date}'"

    payments = _paginate(Payment, base_query, client)
    records = []

    for p in payments:
        records.append({
            "external_id": f"qb_pay_{p.Id}",
            "source": "quickbooks",
            "invoice_id": None,  # resolved post-sync
            "customer_id": None,  # resolved post-sync
            "amount": float(safe_decimal(p.TotalAmt) or 0),
            "payment_method": getattr(p.PaymentMethodRef, "name", None) if p.PaymentMethodRef else None,
            "payment_date": p.TxnDate,
            "reference_number": p.PaymentRefNum,
            "created_at": (p.MetaData.get("CreateTime") if isinstance(p.MetaData, dict) else getattr(p.MetaData, "CreateTime", None)) if p.MetaData else None,
            "last_synced_at": now_utc().isoformat(),
        })

    result = upsert_records("payments", records)
    logger.info("Payments synced: %d", result["upserted"])
    return result["upserted"]


# ── Expenses ──────────────────────────────────────────────────────────────────

def sync_expenses(client, since_date: str | None = None) -> int:
    from quickbooks.objects.purchase import Purchase

    base_query = "SELECT * FROM Purchase WHERE PaymentType IN ('Cash', 'Check', 'CreditCard')"
    if since_date:
        base_query += f" AND MetaData.LastUpdatedTime >= '{since_date}'"

    purchases = _paginate(Purchase, base_query, client)
    records = []

    for p in purchases:
        vendor_name = None
        if p.EntityRef:
            vendor_name = p.EntityRef.name

        for i, line in enumerate(p.Line or []):
            category = None
            if line.AccountBasedExpenseLineDetail:
                category = getattr(line.AccountBasedExpenseLineDetail.AccountRef, "name", None)
            amount = float(safe_decimal(line.Amount) or 0)
            if amount <= 0:
                continue

            records.append({
                "external_id": f"qb_exp_{p.Id}_{i}",
                "source": "quickbooks",
                "vendor_name": vendor_name,
                "category": category,
                "description": line.Description,
                "amount": amount,
                "expense_date": p.TxnDate,
                "created_at": (p.MetaData.get("CreateTime") if isinstance(p.MetaData, dict) else getattr(p.MetaData, "CreateTime", None)) if p.MetaData else None,
                "last_synced_at": now_utc().isoformat(),
            })

    result = upsert_records("expenses", records)
    logger.info("Expenses synced: %d", result["upserted"])
    return result["upserted"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync QuickBooks Online data to Supabase")
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--days-back", type=int, default=7)
    args = parser.parse_args()

    since_date = None if args.mode == "full" else days_ago(args.days_back).isoformat()
    sync_type = args.mode
    started_at = now_utc()
    log_id = log_sync_start("quickbooks", sync_type)

    total_fetched = 0
    total_upserted = 0
    error_msg = None

    try:
        client = get_qb_client()
        total_upserted += sync_customers(client, since_date)
        total_upserted += sync_invoices(client, since_date)
        total_upserted += sync_payments(client, since_date)
        total_upserted += sync_expenses(client, since_date)
        total_fetched = total_upserted
        status = "success"
    except Exception as exc:
        logger.error("QuickBooks sync failed: %s", exc, exc_info=True)
        error_msg = str(exc)
        status = "failed"

    log_sync_complete(
        log_id,
        status=status,
        records_fetched=total_fetched,
        records_upserted=total_upserted,
        error_message=error_msg,
        started_at=started_at,
    )
    sys.exit(0 if status == "success" else 1)


if __name__ == "__main__":
    main()
