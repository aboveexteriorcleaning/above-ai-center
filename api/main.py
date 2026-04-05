"""
FastAPI backend for the Above AI Center dashboard.
Wraps tools/query_engine.py as an HTTP API.

Routes:
    POST /api/query               — AI natural language query
    GET  /api/dashboard/kpis      — KPI cards (MTD headline numbers)
    GET  /api/dashboard/revenue   — Monthly revenue trend
    GET  /api/dashboard/services  — Revenue by service type (YTD)
    GET  /api/dashboard/ads       — Ad campaign performance (MTD)
    GET  /api/dashboard/leads     — Lead source breakdown (MTD)
    GET  /api/dashboard/google    — Google Business metrics (last 30 days)
    GET  /api/dashboard/sync      — Last sync status per source
    GET  /api/health              — Health check (no auth required)
"""

import os
import sys
import logging
from decimal import Decimal
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Path setup — mirrors slack_bot.py and scheduler.py pattern ────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from auth import verify_api_key
import dashboard_queries as dq

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Above AI Center API", version="1.0.0", docs_url=None, redoc_url=None)

# Allow the Next.js frontend (and localhost for dev) to call this API
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── JSON serialization helper (handles Decimal, date, datetime) ───────────────

def _jsonify(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types."""
    if isinstance(obj, list):
        return [_jsonify(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


# ── Request / Response models ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sql_used: str | None = None
    data: list[dict] = []
    chart_hint: str = "none"
    error: str | None = None


# ── Health check (no auth) ────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── AI query endpoint ─────────────────────────────────────────────────────────

@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest, _: str = Depends(verify_api_key)):
    """Forward a natural language question to query_engine.answer_question()."""
    logger.info("query question=%r", req.question[:120])

    # Lazy import — avoids loading Anthropic client at startup
    from query_engine import answer_question  # noqa: PLC0415

    result = answer_question(req.question)
    return QueryResponse(
        answer=result.get("answer", ""),
        sql_used=result.get("sql_used"),
        data=_jsonify(result.get("data", [])),
        chart_hint=result.get("chart_hint", "none"),
        error=result.get("error"),
    )


# ── Pre-built dashboard endpoints (fast, no AI cost) ─────────────────────────

@app.get("/api/dashboard/kpis")
def dashboard_kpis(_: str = Depends(verify_api_key)):
    return _jsonify(dq.get_kpis_mtd())


@app.get("/api/dashboard/revenue")
def dashboard_revenue(months: int = 12, _: str = Depends(verify_api_key)):
    return _jsonify(dq.get_revenue_by_month(months))


@app.get("/api/dashboard/services")
def dashboard_services(_: str = Depends(verify_api_key)):
    return _jsonify(dq.get_revenue_by_service_ytd())


@app.get("/api/dashboard/ads")
def dashboard_ads(_: str = Depends(verify_api_key)):
    return {
        "campaigns": _jsonify(dq.get_ad_campaigns_mtd()),
        "daily": _jsonify(dq.get_ad_spend_daily_last30()),
    }


@app.get("/api/dashboard/leads")
def dashboard_leads(_: str = Depends(verify_api_key)):
    return _jsonify(dq.get_leads_by_source_mtd())


@app.get("/api/dashboard/google")
def dashboard_google(_: str = Depends(verify_api_key)):
    return _jsonify(dq.get_google_metrics_last30())


@app.get("/api/dashboard/sync")
def dashboard_sync(_: str = Depends(verify_api_key)):
    return _jsonify(dq.get_sync_status())


@app.get("/api/dashboard/jobs")
def dashboard_jobs(_: str = Depends(verify_api_key)):
    return {
        "by_service": _jsonify(dq.get_revenue_by_service_ytd()),
        "trend": _jsonify(dq.get_jobs_trend_mtd()),
    }
