"""
QuickBooks P&L Report fetcher.
Calls the QB Reporting API directly for authoritative revenue/expense/profit data.

Usage:
    python tools/query_quickbooks_pl.py --start-date 2026-02-01 --end-date 2026-02-28
    python tools/query_quickbooks_pl.py --start-date 2026-01-01 --end-date 2026-03-31 --method Accrual

Import:
    from query_quickbooks_pl import get_pl_report
    data = get_pl_report("2026-02-01", "2026-02-28")
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from utils import persist_env_var

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QB_BASE_URL = "https://quickbooks.api.intuit.com"
QB_SANDBOX_URL = "https://sandbox-quickbooks.api.intuit.com"


def _get_auth_client():
    """Return a refreshed QB AuthClient."""
    from intuitlib.client import AuthClient

    auth_client = AuthClient(
        client_id=os.environ["QB_CLIENT_ID"],
        client_secret=os.environ["QB_CLIENT_SECRET"],
        environment=os.getenv("QB_ENVIRONMENT", "production"),
        redirect_uri="https://aboveexteriorcleaning.com/qb-callback",
    )
    auth_client.refresh(refresh_token=os.environ["QB_REFRESH_TOKEN"])

    if auth_client.refresh_token and auth_client.refresh_token != os.environ["QB_REFRESH_TOKEN"]:
        logger.info("QB refresh token rotated — persisting to .env")
        persist_env_var("QB_REFRESH_TOKEN", auth_client.refresh_token)

    return auth_client


def _parse_pl_rows(rows: list) -> dict:
    """
    Parse the nested QB P&L rows structure into a flat summary dict.

    Returns:
        {
            "total_income": float,
            "total_cogs": float,
            "gross_profit": float,
            "total_expenses": float,
            "net_income": float,
            "income_by_account": [{"name": str, "amount": float}],
            "expense_by_account": [{"name": str, "amount": float}],
        }
    """
    result = {
        "total_income": 0.0,
        "total_cogs": 0.0,
        "gross_profit": 0.0,
        "total_expenses": 0.0,
        "net_income": 0.0,
        "income_by_account": [],
        "expense_by_account": [],
    }

    def _get_value(col_data: list) -> float:
        """Extract numeric value from QB column data array."""
        for col in col_data:
            val = col.get("value", "")
            if val and val not in ("", "0.00"):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
        return 0.0

    def _parse_section(section: dict, context: str):
        """Recursively parse a section and its children."""
        group = section.get("group", "")
        rows_inner = (section.get("Rows") or {}).get("Row", [])
        summary = section.get("Summary")

        # Income section
        if group == "Income":
            for row in rows_inner:
                if row.get("type") == "Data":
                    cols = row.get("ColData", [])
                    if len(cols) >= 2:
                        name = cols[0].get("value", "")
                        amount = _get_value(cols[1:])
                        if name and amount:
                            result["income_by_account"].append({"name": name, "amount": amount})
            if summary:
                result["total_income"] = _get_value(summary.get("ColData", [])[1:])

        # Cost of Goods Sold
        elif group == "COGS":
            if summary:
                result["total_cogs"] = _get_value(summary.get("ColData", [])[1:])

        # Gross Profit line
        elif group == "GrossProfit":
            if summary:
                result["gross_profit"] = _get_value(summary.get("ColData", [])[1:])

        # Operating expenses / other expenses
        elif group in ("Expenses", "OtherExpenses", "OtherIncome"):
            for row in rows_inner:
                if row.get("type") == "Data":
                    cols = row.get("ColData", [])
                    if len(cols) >= 2:
                        name = cols[0].get("value", "")
                        amount = _get_value(cols[1:])
                        if name and amount:
                            result["expense_by_account"].append({"name": name, "amount": amount})
            if summary:
                result["total_expenses"] += _get_value(summary.get("ColData", [])[1:])

        # Net Income
        elif group == "NetIncome":
            if summary:
                result["net_income"] = _get_value(summary.get("ColData", [])[1:])

        # Recurse into nested sections
        for row in rows_inner:
            if row.get("type") == "Section":
                _parse_section(row, group)

    for row in rows:
        if row.get("type") == "Section":
            _parse_section(row, "")

    # Fallback: if gross_profit wasn't a named group, compute it
    if result["gross_profit"] == 0.0 and result["total_income"]:
        result["gross_profit"] = result["total_income"] - result["total_cogs"]

    return result


def get_pl_report(start_date: str, end_date: str, accounting_method: str = "Accrual") -> dict:
    """
    Fetch the QuickBooks P&L report for the given date range.

    Args:
        start_date: "YYYY-MM-DD"
        end_date:   "YYYY-MM-DD"
        accounting_method: "Cash" or "Accrual" (default: Cash)

    Returns:
        {
            "start_date": str,
            "end_date": str,
            "accounting_method": str,
            "total_income": float,
            "total_cogs": float,
            "gross_profit": float,
            "total_expenses": float,
            "net_income": float,
            "income_by_account": list[dict],
            "expense_by_account": list[dict],
            "error": str | None,
        }
    """
    import requests

    base = result = {
        "start_date": start_date,
        "end_date": end_date,
        "accounting_method": accounting_method,
        "total_income": 0.0,
        "total_cogs": 0.0,
        "gross_profit": 0.0,
        "total_expenses": 0.0,
        "net_income": 0.0,
        "income_by_account": [],
        "expense_by_account": [],
        "error": None,
    }

    try:
        auth_client = _get_auth_client()
        env = os.getenv("QB_ENVIRONMENT", "production")
        base_url = QB_SANDBOX_URL if env == "sandbox" else QB_BASE_URL
        company_id = os.environ["QB_COMPANY_ID"]

        url = f"{base_url}/v3/company/{company_id}/reports/ProfitAndLoss"
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "accounting_method": accounting_method,
            "minorversion": "65",
        }
        headers = {
            "Authorization": f"Bearer {auth_client.access_token}",
            "Accept": "application/json",
        }

        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        rows = (data.get("Rows") or {}).get("Row", [])
        parsed = _parse_pl_rows(rows)
        result.update(parsed)

        logger.info(
            "QB P&L fetched: income=%.2f expenses=%.2f net=%.2f (%s to %s, %s basis)",
            result["total_income"], result["total_expenses"], result["net_income"],
            start_date, end_date, accounting_method,
        )

    except Exception as exc:
        logger.error("QB P&L report failed: %s", exc)
        result["error"] = str(exc)

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch QuickBooks P&L report")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--method", default="Cash", choices=["Cash", "Accrual"])
    args = parser.parse_args()

    data = get_pl_report(args.start_date, args.end_date, args.method)

    print("\n" + "=" * 60)
    print(f"QB P&L REPORT: {args.start_date} → {args.end_date} ({args.method} basis)")
    print("=" * 60)

    if data["error"]:
        print(f"ERROR: {data['error']}")
        sys.exit(1)

    print(f"\nTotal Income:    ${data['total_income']:,.2f}")
    print(f"Total COGS:      ${data['total_cogs']:,.2f}")
    print(f"Gross Profit:    ${data['gross_profit']:,.2f}")
    print(f"Total Expenses:  ${data['total_expenses']:,.2f}")
    print(f"Net Income:      ${data['net_income']:,.2f}")

    if data["income_by_account"]:
        print("\nIncome by Account:")
        for item in data["income_by_account"]:
            print(f"  {item['name']}: ${item['amount']:,.2f}")

    if data["expense_by_account"]:
        print("\nExpenses by Account:")
        for item in data["expense_by_account"]:
            print(f"  {item['name']}: ${item['amount']:,.2f}")
    print()


if __name__ == "__main__":
    main()
