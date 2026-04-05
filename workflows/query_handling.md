# Query Handling — Natural Language Business Questions

## Objective
Turn a plain-English question from the owner into an accurate SQL query, execute it against Supabase, and return a synthesized answer.

## Tool
```bash
python tools/query_engine.py --question "What ads worked best last month?"
```
Or imported by `slack_bot.py`:
```python
from query_engine import answer_question
result = answer_question("What's my P&L for Q1?")
```

## How It Works

**Revenue/profit/P&L questions** are routed directly to the QuickBooks P&L Report API before any SQL is attempted. This returns the same numbers your accountant sees in QuickBooks (Cash basis). The `query_quickbooks_pl.py` tool handles the API call.

**All other questions** use the two-pass SQL approach below.

## Two-Pass Claude API (SQL route)

**Pass 1 — SQL Generation:**
- Input: natural language question + full schema context + business context
- Output: a PostgreSQL SELECT statement
- Model: claude-haiku-4-5 (fast, cheap, accurate for SQL)
- Safety guard: only SELECT statements accepted; DDL/DML raises ValueError

**Pass 2 — Answer Synthesis:**
- Input: original question + SQL used + result rows (up to 20 shown)
- Output: plain-English answer with business insight
- Model: claude-haiku-4-5

**Return value:**
```python
{
    "answer": str,       # Synthesized answer
    "sql_used": str,     # The SQL that ran
    "data": list[dict],  # All result rows (up to 100)
    "chart_hint": str,   # "line_chart" | "bar_chart" | "kpi_cards" | "table" | "none"
    "error": str | None
}
```

## Chart Hints
The engine auto-detects the best visualization:
- date column + numeric column → `line_chart`
- category column + numeric column → `bar_chart`
- single row, multiple numerics → `kpi_cards`
- otherwise → `table`

These hints are used by the future React dashboard.

## Example Questions This Handles

| Question | Type |
|---|---|
| "What was my revenue in March?" | kpi_cards |
| "Which service type makes the most money?" | bar_chart |
| "Show me revenue by week for the last 3 months" | line_chart |
| "What's my cost per lead for each campaign?" | table |
| "What's my CAC for March 2026?" | kpi_cards |
| "Which customers haven't booked in 6 months?" | table |
| "What's my total expenses by category this quarter?" | bar_chart |
| "How many jobs did I complete last month vs the month before?" | kpi_cards |
| "Which ad has the lowest CPL in the last 30 days?" | table |
| "What's my average Google review rating?" | kpi_cards |
| "Show me all overdue invoices" | table |

## Edge Cases

**No data returned:** The synthesis prompt instructs Claude to note if no data was found and suggest why (e.g., "No completed jobs in January — data may not have synced yet").

**CAC vs CPL confusion:** CAC (customer acquisition cost) and CPL (cost per lead) are different metrics. CAC = ad spend × 1.1 / new customers acquired. CPL = spend / leads from ad_insights_daily. The engine is trained to distinguish these — if you ask for CAC and get CPL, it means the question was ambiguous. Be explicit: "What's my customer acquisition cost for March?" not "What's my cost per lead?"

**Ambiguous question:** If the question is unclear (e.g., "revenue" could mean billed vs received), Claude will choose the most business-relevant interpretation and note it in the answer. To be explicit, ask: "What was my cash received revenue last month?"

**Multi-step questions:** For questions that require two separate queries (e.g., "What's my margin per service type?"), Claude may attempt to combine them in a single SQL with CTEs. If the first attempt fails, it retries with the error message.

**SQL generation fails twice:** Returns an error response with the original question. Try rephrasing or breaking into simpler sub-questions.

**Large result sets:** Rows are capped at 100 in SQL (LIMIT 100). The synthesis pass shows only the top 20 rows for analysis.

## Improving Query Accuracy
If you notice Claude generating incorrect SQL for certain question types, document the correct SQL in the `SCHEMA_CONTEXT` examples section in `query_engine.py`. Adding 2-3 few-shot examples dramatically improves accuracy for similar future questions.

## Verification
```bash
python tools/query_engine.py -q "What was my total revenue last month?"
python tools/query_engine.py -q "Which campaign has the lowest cost per lead in the last 30 days?"
python tools/query_engine.py -q "How many jobs did I complete by service type this year?"
```
All three should return SQL, data rows, and a synthesized answer without errors.
