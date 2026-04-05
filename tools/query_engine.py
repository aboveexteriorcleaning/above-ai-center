"""
AI Query Engine — natural language → SQL → synthesized answer.
Uses a two-pass Claude API approach:
  Pass 1: Generate SQL from natural language question
  Pass 2: Synthesize results into a plain-English answer

Usage:
    python tools/query_engine.py --question "What was my revenue last month?"
    python tools/query_engine.py --question "Which ad campaigns had the lowest cost per lead?"

Import:
    from query_engine import answer_question
    result = answer_question("What's my P&L for Q1 2026?")
"""

import os
import sys
import re
import json
import logging
import argparse
from typing import Any
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from supabase_client import execute_sql

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Schema context (static — describes all 17 tables) ─────────────────────────

SCHEMA_CONTEXT = """
DATABASE SCHEMA — Above Exterior Cleaning Business Intelligence Hub

TABLES:
customers (id uuid, external_id text, source text, full_name text, email text, phone text, address_line1 text, city text, state text, zip text, created_at timestamptz, last_synced_at timestamptz)

jobs (id uuid, external_id text, customer_id uuid→customers.id, title text, service_type text, status text, scheduled_start timestamptz, scheduled_end timestamptz, completed_at timestamptz, total_amount numeric, notes text, job_address text, created_at timestamptz)

quotes (id uuid, external_id text, customer_id uuid→customers.id, job_id uuid→jobs.id, status text, total_amount numeric, sent_at timestamptz, approved_at timestamptz, declined_at timestamptz, created_at timestamptz)

job_line_items (id uuid, job_id uuid→jobs.id, service_type text, description text, quantity numeric, unit_price numeric, total_price numeric)

invoices (id uuid, external_id text, source text, customer_id uuid→customers.id, job_id uuid→jobs.id, invoice_number text, status text, subtotal numeric, tax_amount numeric, total_amount numeric, amount_paid numeric, balance_due numeric, due_date date, paid_date date, created_at timestamptz)

payments (id uuid, external_id text, source text, invoice_id uuid→invoices.id, customer_id uuid→customers.id, amount numeric, payment_method text, payment_date date, reference_number text, created_at timestamptz)

expenses (id uuid, external_id text, source text, vendor_name text, category text, description text, amount numeric, expense_date date, job_id uuid→jobs.id, created_at timestamptz)

ad_campaigns (id uuid, external_id text, platform text, name text, status text, objective text, daily_budget numeric, lifetime_budget numeric, start_time timestamptz, stop_time timestamptz, created_at timestamptz)

ad_sets (id uuid, external_id text, campaign_id uuid→ad_campaigns.id, name text, status text, targeting_summary jsonb, daily_budget numeric, bid_strategy text, optimization_goal text, start_time timestamptz, stop_time timestamptz)

ads (id uuid, external_id text, ad_set_id uuid→ad_sets.id, campaign_id uuid→ad_campaigns.id, name text, status text, creative_type text, headline text, body_text text, call_to_action text)

ad_insights_daily (id uuid, ad_id uuid→ads.id, ad_set_id uuid→ad_sets.id, campaign_id uuid→ad_campaigns.id, date_start date, impressions int, reach int, clicks int, link_clicks int, spend numeric, leads int, cpm numeric, cpc numeric, cpl numeric, ctr numeric, roas numeric, raw_json jsonb)
  UNIQUE KEY: (ad_id, date_start)

sms_conversations (id uuid, external_id text, customer_id uuid→customers.id, phone_number text, direction text, status text, last_message_at timestamptz, message_count int, created_at timestamptz)

sms_messages (id uuid, external_id text, conversation_id uuid→sms_conversations.id, customer_id uuid→customers.id, direction text, body text, sent_at timestamptz)

email_threads (id uuid, thread_id text, customer_id uuid→customers.id, subject text, participants text[], message_count int, last_message_at timestamptz, has_unread bool, labels text[])

email_messages (id uuid, external_id text, thread_id uuid→email_threads.id, customer_id uuid→customers.id, from_address text, snippet text, direction text, sent_at timestamptz, labels text[])

google_reviews (id uuid, external_id text, reviewer_name text, rating int, review_text text, replied bool, reply_text text, review_date date)

google_business_metrics (id uuid, metric_date date UNIQUE, total_reviews int, average_rating numeric, searches_direct int, searches_discovery int, views_maps int, views_search int, calls int, website_clicks int, direction_requests int)

leads (id uuid, external_id text, lead_source text, platform text, first_name text, last_name text, full_name text, email text, phone text, city text, campaign_name text, ad_name text, lead_status text, customer_id uuid→customers.id, created_time timestamptz)

sync_logs (id uuid, source text, sync_type text, status text, records_fetched int, records_upserted int, error_message text, started_at timestamptz, completed_at timestamptz, duration_seconds numeric)

LEAD SOURCE DATA:
- leads table synced from Google Sheets (master lead tracking spreadsheet)
- leads.lead_source: 'meta' (Facebook/Instagram paid ads) or 'website' (organic/referral/Wix form)
- leads.platform: raw platform value — 'fb', 'ig', 'WIX'
- leads.customer_id links to customers.id when the lead's phone matched a Jobber customer
- To get revenue by lead source: JOIN leads → customers → jobs via customer_id
- leads.lead_status: 'CREATED' = lead came in, others indicate follow-up stage
- ~45% of leads are currently matched to Jobber customers (phone match); unmatched = lead did not convert or phone didn't match

ENUM VALUES:
- jobs.service_type: 'roof_cleaning', 'softwash', 'pressure_washing', 'window_cleaning', 'fence_deck'
- jobs.status: 'quote', 'scheduled', 'completed', 'cancelled'
- invoices.status: 'draft', 'sent', 'paid', 'overdue', 'void'
- payments.payment_method: 'cash', 'check', 'card', 'ach'
- ad_campaigns.status: 'ACTIVE', 'PAUSED', 'ARCHIVED'
- sms_conversations.status: 'open', 'closed', 'spam'
- email_messages.direction: 'inbound', 'outbound'

BUSINESS CONTEXT:
- Company: Above Exterior Cleaning, Thurston County WA
- Services: roof cleaning, house/home softwashing, pressure washing, window cleaning, fence & deck restoration
- Revenue tracked via: payments.amount (actual cash received) and invoices.total_amount (billed)
- Profit = payments (revenue) minus expenses.amount
- Ad performance: ad_insights_daily tracks daily spend, impressions, clicks, leads per ad
- Timezone: America/Los_Angeles
- CAC (cost to acquire a customer) = SUM(ad_insights_daily.spend) * 1.1 / new customers acquired
  The 1.1 multiplier covers all sales & marketing costs beyond Facebook ad spend.
  "New customers" = customers whose first-ever non-cancelled job was created in the period.
  Never use the expenses table for CAC calculations.

JOB SCHEDULING RULES:
- "This month" / "in March" / "scheduled in [month]" = filter on jobs.scheduled_start, NOT jobs.created_at
  Example: jobs scheduled in March 2026 → WHERE scheduled_start >= '2026-03-01' AND scheduled_start < '2026-04-01'
- jobs.created_at = when the job record was created in Jobber; jobs.scheduled_start = when the job is actually on the calendar
- Always use scheduled_start for "when is the job", created_at only for "when was it booked"
- "Last 30 days" = WHERE date_col >= CURRENT_DATE - INTERVAL '30 days'
- Job value = SUM(total_amount). Unless the user says otherwise, include ALL job statuses (scheduled, completed, cancelled).
  If they say "scheduled" or "on the books", use WHERE status IN ('scheduled', 'completed') to exclude cancelled.

AD PERFORMANCE / CPL RULES (CRITICAL):
- NEVER use AVG(cpl) to answer any cost-per-lead question. The cpl column stores a per-ad, per-day value and
  averaging it produces meaningless results (a day with 1 lead at $2 CPL counts the same as a day with 50 leads at $20 CPL).
- ALWAYS calculate CPL as: ROUND(SUM(spend) / NULLIF(SUM(leads), 0), 2)
- ALWAYS calculate ROAS as: ROUND(SUM(roas * leads) / NULLIF(SUM(leads), 0), 2)  -- or use revenue/spend if available
- When the user asks about "average CPL", "cost per lead", or similar: aggregate SUM(spend) and SUM(leads) over the
  requested period, then divide.
- Year filter example: WHERE date_start >= '2026-01-01' AND date_start < '2027-01-01'
- When leads = 0 for a row, cpl is NULL — this is correct; those rows are still included in SUM(spend).
- CPL LEAD SOURCE (CRITICAL): The denominator for CPL is ALWAYS ad_insights_daily.leads — the lead count Facebook
  reports via its API. NEVER use COUNT(*) or COUNT(id) from the leads table for CPL. The leads table is Google Sheets
  data matched against Jobber customers; it is incomplete (~45% match rate) and must not be used as the lead count
  for cost-per-lead calculations.

CAC vs CPL — THESE ARE DIFFERENT METRICS (CRITICAL):
- CPL (cost per lead) = SUM(spend) / SUM(leads) from ad_insights_daily. This is an ad metric.
- CAC (customer acquisition cost) = SUM(ad spend) * 1.1 / COUNT(new customers acquired). This is a business metric.
- When the user says "CAC", "cost to acquire a customer", or "customer acquisition cost":
  ALWAYS use the CAC formula with new customers. NEVER return CPL as the answer to a CAC question.
- "New customers" for a period = customers whose first-ever non-cancelled job was created in that period
  (MIN(jobs.created_at) falls within the period, across all non-cancelled jobs for that customer_id).
- The 1.1 multiplier on ad spend covers all sales & marketing overhead beyond Facebook ads.
"""

def _build_sql_system_prompt() -> str:
    from datetime import date
    today = date.today()
    return f"""You are a SQL expert for a small business database. Given a natural language question, generate a single PostgreSQL SELECT query that answers it.

TODAY'S DATE: {today.strftime("%Y-%m-%d")}. The current year is {today.year}. The current month is {today.month} ({today.strftime("%B")}). Never hardcode a year that differs from this. Use this date as your reference for "this year", "this month", "last month", "last year", etc.

{SCHEMA_CONTEXT}

RULES:
1. Return ONLY a SELECT statement inside ```sql ... ``` code fences. No explanation.
2. Only use SELECT. Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, GRANT, or EXECUTE.
3. Always include meaningful column aliases for readability.
4. Limit results to 100 rows unless the question asks for all records.
5. For date/time comparisons, use CURRENT_DATE or NOW() rather than hardcoded dates.
6. Round monetary values to 2 decimal places. Round percentages to 1 decimal place.
7. When asked about "revenue" grouped or broken down by service type, ALWAYS use jobs.total_amount directly from the jobs table. Do NOT join payments or invoices — payments have no service_type column and the join chain is unreliable. Example: SUM(jobs.total_amount) GROUP BY jobs.service_type.
8. When asked about overall "revenue" (not by service type), use SUM(payments.amount) for actual cash received.
9. When asked about "billed" or "invoiced", use SUM(invoices.total_amount).
10. When asked about "profit" or "net" overall (not by service), calculate SUM(payments.amount) - SUM(expenses.amount).
11. When asked about profit or margin BY SERVICE TYPE, use jobs.total_amount for revenue (not payments) since payments cannot be joined to service_type reliably.
12. For ad performance questions, aggregate ad_insights_daily over the requested time period.
13. NEVER use AVG(cpl) for cost-per-lead. Always compute ROUND(SUM(spend) / NULLIF(SUM(leads), 0), 2).
    The leads denominator must always come from ad_insights_daily.leads (Facebook-reported). NEVER use COUNT(*) from the leads table for CPL — the leads table is for conversion tracking, not ad lead counts.
14. For scheduled job value, always filter on scheduled_start (not created_at), and include scheduled + completed unless told otherwise.
15. CAC and CPL are DIFFERENT. When asked for "CAC" or "customer acquisition cost", use the CTE pattern:
    ad spend * 1.1 / new customers (MIN(jobs.created_at) in period, non-cancelled). Never return CPL as a CAC answer.

CANONICAL SQL EXAMPLES (follow these patterns exactly):

Q: What is our average cost per lead in 2026?
```sql
SELECT
  SUM(spend) AS total_spend,
  SUM(leads) AS total_leads,
  ROUND(SUM(spend) / NULLIF(SUM(leads), 0), 2) AS avg_cpl
FROM ad_insights_daily
WHERE date_start >= '2026-01-01' AND date_start < '2027-01-01';
```

Q: How much job value do we have scheduled for March 2026?
```sql
SELECT
  COUNT(*) AS job_count,
  ROUND(SUM(total_amount), 2) AS total_job_value
FROM jobs
WHERE scheduled_start >= '2026-03-01'
  AND scheduled_start < '2026-04-01'
  AND status IN ('scheduled', 'completed');
```

Q: What is my cost to acquire a customer in 2026?
```sql
-- CAC = (Facebook ad spend * 1.1) / new customers acquired
-- The 1.1 multiplier accounts for all sales & marketing costs beyond Facebook ads.
-- "New customers" = customers whose first-ever job was created in the requested period.
WITH ad_spend AS (
  SELECT SUM(spend) * 1.1 AS sales_marketing_spend
  FROM ad_insights_daily
  WHERE date_start >= '2026-01-01' AND date_start < '2027-01-01'
),
new_customers AS (
  SELECT customer_id
  FROM jobs
  WHERE customer_id IS NOT NULL
    AND status NOT IN ('cancelled')
  GROUP BY customer_id
  HAVING MIN(created_at) >= '2026-01-01' AND MIN(created_at) < '2027-01-01'
)
SELECT
  ROUND(a.sales_marketing_spend, 2) AS sales_marketing_spend,
  (SELECT COUNT(*) FROM new_customers) AS new_customers_acquired,
  ROUND(a.sales_marketing_spend / NULLIF((SELECT COUNT(*) FROM new_customers), 0), 2) AS cost_per_acquired_customer
FROM ad_spend a;
```

Q: What is my CAC for March 2026?
```sql
-- CAC = (Facebook ad spend * 1.1) / new customers acquired
-- "New customers" = customers whose first-ever non-cancelled job was created in the period.
WITH ad_spend AS (
  SELECT SUM(spend) * 1.1 AS sales_marketing_spend
  FROM ad_insights_daily
  WHERE date_start >= '2026-03-01' AND date_start < '2026-04-01'
),
new_customers AS (
  SELECT customer_id
  FROM jobs
  WHERE customer_id IS NOT NULL
    AND status NOT IN ('cancelled')
  GROUP BY customer_id
  HAVING MIN(created_at) >= '2026-03-01' AND MIN(created_at) < '2026-04-01'
)
SELECT
  ROUND(a.sales_marketing_spend, 2) AS sales_marketing_spend,
  (SELECT COUNT(*) FROM new_customers) AS new_customers_acquired,
  ROUND(a.sales_marketing_spend / NULLIF((SELECT COUNT(*) FROM new_customers), 0), 2) AS cac
FROM ad_spend a;
```

Q: What is our average cost per booked job in 2026?
```sql
WITH costs AS (
  SELECT SUM(amount) AS total_expenses
  FROM expenses
  WHERE expense_date >= '2026-01-01' AND expense_date < '2027-01-01'
),
bookings AS (
  SELECT COUNT(*) AS booked_jobs
  FROM jobs
  WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01'
    AND status NOT IN ('cancelled')
)
SELECT
  ROUND(c.total_expenses, 2) AS total_expenses,
  b.booked_jobs,
  ROUND(c.total_expenses / NULLIF(b.booked_jobs, 0), 2) AS cost_per_booked_job
FROM costs c, bookings b;
```

Q: Which lead source generates the most revenue? / Revenue by lead source (meta vs website).
```sql
SELECT
  l.lead_source,
  COUNT(DISTINCT l.id)              AS leads,
  COUNT(DISTINCT j.id)              AS jobs_booked,
  ROUND(SUM(j.total_amount), 2)     AS total_revenue,
  ROUND(AVG(j.total_amount), 2)     AS avg_job_value
FROM leads l
JOIN customers c ON c.id = l.customer_id
JOIN jobs j ON j.customer_id = c.id
WHERE j.status IN ('scheduled', 'completed')
GROUP BY l.lead_source
ORDER BY total_revenue DESC;
```

Q: Which lead source has the best conversion rate?
```sql
SELECT
  lead_source,
  COUNT(*)                                                          AS total_leads,
  COUNT(customer_id)                                                AS converted,
  ROUND(COUNT(customer_id)::numeric / COUNT(*) * 100, 1)           AS conversion_pct
FROM leads
GROUP BY lead_source
ORDER BY conversion_pct DESC;
```

Q: Which services are most profitable? / What service makes the most money? / Revenue by service type.
```sql
-- IMPORTANT: Always use jobs.total_amount for service-type breakdowns. Never join payments for this.
SELECT
  service_type,
  COUNT(*)                          AS job_count,
  ROUND(SUM(total_amount), 2)       AS total_revenue,
  ROUND(AVG(total_amount), 2)       AS avg_job_value
FROM jobs
WHERE status IN ('scheduled', 'completed')
GROUP BY service_type
ORDER BY total_revenue DESC;
```

Q: Which service generates the most revenue? / Break down revenue by service type for Q1 2026.
```sql
SELECT
  service_type,
  COUNT(*)                          AS job_count,
  ROUND(SUM(total_amount), 2)       AS total_value,
  ROUND(AVG(total_amount), 2)       AS avg_job_value
FROM jobs
WHERE scheduled_start >= '2026-01-01'
  AND scheduled_start < '2026-04-01'
  AND status IN ('scheduled', 'completed')
GROUP BY service_type
ORDER BY total_value DESC;
```

Q: What is our cost per lead by campaign this month?
```sql
SELECT
  c.name AS campaign_name,
  SUM(i.spend) AS total_spend,
  SUM(i.leads) AS total_leads,
  ROUND(SUM(i.spend) / NULLIF(SUM(i.leads), 0), 2) AS cpl
FROM ad_insights_daily i
JOIN ad_campaigns c ON i.campaign_id = c.id
WHERE i.date_start >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY c.name
ORDER BY cpl ASC NULLS LAST;
```
"""

def _build_synthesis_prompt() -> str:
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    return f"""You are a business analyst for Above Exterior Cleaning, a small exterior cleaning company in Thurston County, WA.

TODAY'S DATE: {today}. The current year is {date.today().year}. Do NOT assume any year is in the future.

You will receive a business question, the SQL query that was run, and the raw results.
Synthesize this into a clear, direct, actionable answer.

Guidelines:
- Lead with the direct answer, then provide supporting context
- If the data shows something notable (unusually high CPL, declining revenue trend, top performer), call it out
- Format dollar amounts with $ and 2 decimal places
- Keep your response under 200 words
- If results are empty, say so clearly and suggest the data may not have synced yet — never claim a year is in the future
- Do not mention the SQL query in your response
"""


def _build_pl_synthesis_prompt() -> str:
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    return f"""You are a business analyst for Above Exterior Cleaning, a small exterior cleaning company in Thurston County, WA.

TODAY'S DATE: {today}. The current year is {date.today().year}.

You will receive a business question and a QuickBooks P&L report pulled directly from QuickBooks Online (Accrual basis). This is the authoritative source of truth for revenue, expenses, and profit.

Synthesize this into a clear, direct, actionable answer.

Guidelines:
- Lead with the direct answer, then provide supporting context
- Format dollar amounts with $ and 2 decimal places
- Keep your response under 200 words
- Do not mention QuickBooks or the API in your response — just answer the question naturally
"""


# ── QB P&L route helpers ───────────────────────────────────────────────────────

_PL_KEYWORDS = re.compile(
    r"\b(revenue|income|gross revenue|total revenue|profit|net income|net profit|gross profit|"
    r"p&l|profit.and.loss|earnings|how much (did|have) (we|i) (make|earn|bring in|collect))\b",
    re.IGNORECASE,
)

# Questions that mention service-level breakdowns can't be answered by QB (no service detail there).
# Route these to SQL against the jobs table instead.
_SERVICE_BREAKDOWN_KEYWORDS = re.compile(
    r"\b(by service|service type|per service|each service|which service|service breakdown|"
    r"services? (generated|made|brought|earned|produced|profitable|performing|popular)|"
    r"(revenue|income|money).{0,40}\bservices?\b|\bservices?\b.{0,40}(revenue|income|money|profitable|performing)|"
    r"roof.clean|pressure.wash|window.clean|softwash|gutter|fence|deck|"
    r"lead source|by lead|per lead|which lead|lead channel|lead breakdown|"
    r"meta|facebook|instagram|website lead|conversion rate)\b",
    re.IGNORECASE,
)

# Simpler catch-all: any question mentioning "service(s)" is almost certainly asking for
# Jobber data since QuickBooks only reports a single lumped "Services" line.
_SERVICE_WORD = re.compile(r"\bservices?\b", re.IGNORECASE)


def _is_pl_question(question: str) -> bool:
    """Return True if the question is about revenue, profit, or P&L for a time period.
    Returns False if the question asks for a service-level breakdown — QB can't answer those."""
    if _SERVICE_BREAKDOWN_KEYWORDS.search(question):
        return False
    # If "service(s)" appears anywhere in a revenue question, QB won't have the detail needed
    if _SERVICE_WORD.search(question) and _PL_KEYWORDS.search(question):
        return False
    return bool(_PL_KEYWORDS.search(question))


def _extract_date_range(question: str, client) -> dict | None:
    """
    Use a quick LLM call to extract start_date and end_date from the question.
    Returns {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"} or None on failure.
    """
    from datetime import date
    today = date.today()

    prompt = f"""TODAY IS {today.strftime("%Y-%m-%d")} (year {today.year}).

Extract the date range from this business question. Return ONLY a JSON object with start_date and end_date in YYYY-MM-DD format. No explanation.

Examples:
- "revenue in February this year" → {{"start_date": "{today.year}-02-01", "end_date": "{today.year}-02-28"}}
- "revenue last month" → {{"start_date": "{today.year}-02-01", "end_date": "{today.year}-02-28"}}
- "revenue in Q1 2026" → {{"start_date": "2026-01-01", "end_date": "2026-03-31"}}
- "revenue this year" → {{"start_date": "{today.year}-01-01", "end_date": "{today.strftime('%Y-%m-%d')}"}}
- "revenue last year" → {{"start_date": "{today.year - 1}-01-01", "end_date": "{today.year - 1}-12-31"}}

Question: {question}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if "start_date" in parsed and "end_date" in parsed:
            return parsed
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _answer_from_pl(question: str, client) -> dict | None:
    """
    Try to answer a revenue/profit question using the QB P&L report API.
    Returns an answer_question-compatible dict, or None if QB call fails.
    """
    try:
        from query_quickbooks_pl import get_pl_report
    except ImportError:
        logger.warning("query_quickbooks_pl not found — falling back to SQL")
        return None

    date_range = _extract_date_range(question, client)
    if not date_range:
        logger.warning("Could not extract date range from question — falling back to SQL")
        return None

    pl = get_pl_report(date_range["start_date"], date_range["end_date"])
    if pl["error"]:
        logger.warning("QB P&L API error: %s — falling back to SQL", pl["error"])
        return None

    # Synthesize answer from real QB data
    pl_summary = (
        f"QuickBooks P&L Report ({date_range['start_date']} to {date_range['end_date']}, Accrual basis):\n"
        f"  Total Income:   ${pl['total_income']:,.2f}\n"
        f"  Total COGS:     ${pl['total_cogs']:,.2f}\n"
        f"  Gross Profit:   ${pl['gross_profit']:,.2f}\n"
        f"  Total Expenses: ${pl['total_expenses']:,.2f}\n"
        f"  Net Income:     ${pl['net_income']:,.2f}\n"
    )
    if pl["income_by_account"]:
        pl_summary += "\nIncome breakdown:\n"
        for item in pl["income_by_account"]:
            pl_summary += f"  {item['name']}: ${item['amount']:,.2f}\n"

    synthesis_response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_build_pl_synthesis_prompt(),
        messages=[{"role": "user", "content": f"Question: {question}\n\n{pl_summary}"}],
    )

    answer = synthesis_response.content[0].text.strip()

    # Build data rows for chart hint detection
    data = [{
        "total_income": pl["total_income"],
        "total_cogs": pl["total_cogs"],
        "gross_profit": pl["gross_profit"],
        "total_expenses": pl["total_expenses"],
        "net_income": pl["net_income"],
    }]

    return {
        "answer": answer,
        "sql_used": f"[QuickBooks P&L API: {date_range['start_date']} to {date_range['end_date']}, Accrual basis]",
        "data": data,
        "chart_hint": "kpi_cards",
        "error": None,
    }


# ── SQL Safety Guard ───────────────────────────────────────────────────────────

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXECUTE|CALL)\b",
    re.IGNORECASE,
)


def validate_sql(sql: str) -> str:
    """Raise ValueError if SQL is not a safe SELECT statement (or CTE)."""
    stripped = sql.strip()
    upper = stripped.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ValueError(f"SQL must start with SELECT or WITH. Got: {stripped[:50]}")
    if _FORBIDDEN_KEYWORDS.search(stripped):
        raise ValueError(f"SQL contains forbidden keyword")
    return stripped


# ── Chart hint detection ───────────────────────────────────────────────────────

def detect_chart_hint(rows: list[dict]) -> str:
    """Infer the best visualization type from result shape."""
    if not rows:
        return "none"
    cols = list(rows[0].keys())
    date_cols = [c for c in cols if any(w in c.lower() for w in ("date", "month", "week", "day", "period"))]
    numeric_cols = [c for c in cols if isinstance(rows[0].get(c), (int, float)) and c != "id"]
    category_cols = [c for c in cols if isinstance(rows[0].get(c), str) and c not in ("id",)]

    if len(rows) == 1 and len(numeric_cols) >= 2:
        return "kpi_cards"
    if date_cols and numeric_cols:
        return "line_chart"
    if category_cols and numeric_cols:
        return "bar_chart"
    return "table"


# ── Core query function ────────────────────────────────────────────────────────

def answer_question(question: str) -> dict[str, Any]:
    """
    Answer a natural language business question.

    Returns:
        {
            "answer": str,          # Plain-English synthesized answer
            "sql_used": str,        # The SQL query that was executed
            "data": list[dict],     # Raw result rows (max 100)
            "chart_hint": str,      # "line_chart" | "bar_chart" | "kpi_cards" | "table" | "none"
            "error": str | None,    # Error message if failed
        }
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ── QB P&L route: revenue/profit questions go directly to QuickBooks ──────
    if _is_pl_question(question):
        pl_result = _answer_from_pl(question, client)
        if pl_result:
            return pl_result
        logger.info("QB P&L route failed or unavailable — falling back to SQL")

    # ── Pass 1: Generate SQL ──────────────────────────────────────────────────
    sql_system_prompt = _build_sql_system_prompt()
    sql = None
    for attempt in range(2):
        user_msg = question if attempt == 0 else f"{question}\n\nPrevious SQL failed with: {last_error}\nFix the SQL and try again."

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=sql_system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = response.content[0].text
        match = re.search(r"```sql\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
        if not match:
            last_error = "No SQL code block found in response"
            continue

        candidate_sql = match.group(1).strip()
        try:
            sql = validate_sql(candidate_sql)
            break
        except ValueError as e:
            last_error = str(e)
            continue

    if not sql:
        return {
            "answer": "I wasn't able to generate a valid SQL query for that question. Please try rephrasing.",
            "sql_used": None,
            "data": [],
            "chart_hint": "none",
            "error": last_error,
        }

    # ── Execute SQL ───────────────────────────────────────────────────────────
    try:
        rows = execute_sql(sql)
    except Exception as exc:
        logger.error("SQL execution failed: %s\nSQL: %s", exc, sql)
        # Retry with error feedback
        retry_response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=sql_system_prompt,
            messages=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"```sql\n{sql}\n```"},
                {"role": "user", "content": f"That SQL failed with error: {exc}\nPlease fix it."},
            ],
        )
        raw = retry_response.content[0].text
        match = re.search(r"```sql\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                sql = validate_sql(match.group(1).strip())
                rows = execute_sql(sql)
            except Exception as exc2:
                return {
                    "answer": f"Database query failed: {exc2}",
                    "sql_used": sql,
                    "data": [],
                    "chart_hint": "none",
                    "error": str(exc2),
                }
        else:
            return {
                "answer": f"Database query failed: {exc}",
                "sql_used": sql,
                "data": [],
                "chart_hint": "none",
                "error": str(exc),
            }

    # ── Pass 2: Synthesize answer ─────────────────────────────────────────────
    data_preview = json.dumps(rows[:20], indent=2, default=str)
    synthesis_response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_build_synthesis_prompt(),
        messages=[{
            "role": "user",
            "content": f"Question: {question}\n\nSQL run:\n{sql}\n\nResults ({len(rows)} rows):\n{data_preview}"
        }],
    )

    answer = synthesis_response.content[0].text.strip()
    chart_hint = detect_chart_hint(rows)

    logger.info("Query answered: %d result rows, chart_hint=%s", len(rows), chart_hint)
    return {
        "answer": answer,
        "sql_used": sql,
        "data": rows,
        "chart_hint": chart_hint,
        "error": None,
    }


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ask a natural language question about the business")
    parser.add_argument("--question", "-q", required=True, help="Your business question")
    args = parser.parse_args()

    result = answer_question(args.question)

    print("\n" + "=" * 60)
    print(f"QUESTION: {args.question}")
    print("=" * 60)
    print(f"\nANSWER:\n{result['answer']}")
    if result["sql_used"]:
        print(f"\nSQL USED:\n{result['sql_used']}")
    print(f"\nROWS RETURNED: {len(result['data'])}")
    print(f"CHART HINT: {result['chart_hint']}")
    if result["error"]:
        print(f"ERROR: {result['error']}")
    print()


if __name__ == "__main__":
    main()
