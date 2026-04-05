"""
Pre-built SQL queries for dashboard KPI endpoints.
These call execute_sql() directly — no Claude API, instant response.
To add a new dashboard widget, add a function here and a route in main.py.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from supabase_client import execute_sql


def get_kpis_mtd() -> dict:
    """All headline KPI values for the current month-to-date."""
    sql = """
    SELECT
        (
            SELECT ROUND(COALESCE(SUM(amount), 0), 2)
            FROM payments
            WHERE payment_date >= DATE_TRUNC('month', CURRENT_DATE)
        ) AS cash_revenue_mtd,
        (
            SELECT ROUND(COALESCE(SUM(total_amount), 0), 2)
            FROM invoices
            WHERE status NOT IN ('void', 'cancelled')
              AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
        ) AS billed_revenue_mtd,
        (
            SELECT COUNT(*)
            FROM jobs
            WHERE status = 'completed'
              AND completed_at >= DATE_TRUNC('month', CURRENT_DATE)
        ) AS jobs_completed_mtd,
        (
            SELECT COUNT(*)
            FROM jobs
            WHERE status IN ('scheduled', 'active')
              AND scheduled_start >= CURRENT_DATE
        ) AS jobs_scheduled_upcoming,
        (
            SELECT COUNT(*)
            FROM leads
            WHERE created_time >= DATE_TRUNC('month', CURRENT_DATE)
        ) AS leads_mtd,
        (
            SELECT ROUND(COALESCE(SUM(spend), 0), 2)
            FROM ad_insights_daily
            WHERE date_start >= DATE_TRUNC('month', CURRENT_DATE)
        ) AS ad_spend_mtd,
        (
            SELECT ROUND(
                NULLIF(SUM(spend), 0) / NULLIF(SUM(leads), 0),
                2
            )
            FROM ad_insights_daily
            WHERE date_start >= DATE_TRUNC('month', CURRENT_DATE)
        ) AS cpl_mtd,
        (
            SELECT ROUND(COALESCE(AVG(rating), 0), 1)
            FROM google_reviews
        ) AS google_avg_rating,
        (
            SELECT COUNT(*)
            FROM google_reviews
        ) AS google_review_count
    """
    rows = execute_sql(sql)
    return rows[0] if rows else {}


def get_revenue_by_month(months: int = 12) -> list[dict]:
    """Cash revenue grouped by month for the last N months."""
    sql = f"""
    SELECT
        TO_CHAR(DATE_TRUNC('month', payment_date), 'YYYY-MM') AS month,
        ROUND(SUM(amount), 2) AS cash_revenue
    FROM payments
    WHERE payment_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '{months - 1} months'
    GROUP BY DATE_TRUNC('month', payment_date)
    ORDER BY DATE_TRUNC('month', payment_date)
    """
    return execute_sql(sql)


def get_revenue_by_service_ytd() -> list[dict]:
    """Revenue by service type for the current year-to-date."""
    sql = """
    SELECT
        COALESCE(service_type, 'other') AS service_type,
        ROUND(SUM(total_amount), 2) AS revenue,
        COUNT(*) AS job_count
    FROM jobs
    WHERE status = 'completed'
      AND completed_at >= DATE_TRUNC('year', CURRENT_DATE)
    GROUP BY service_type
    ORDER BY revenue DESC
    """
    return execute_sql(sql)


def get_ad_campaigns_mtd() -> list[dict]:
    """Ad campaign performance for the current month-to-date."""
    sql = """
    SELECT
        c.name AS campaign_name,
        c.status,
        ROUND(SUM(i.spend), 2) AS spend,
        SUM(i.leads) AS leads,
        SUM(i.impressions) AS impressions,
        SUM(i.clicks) AS clicks,
        ROUND(SUM(i.spend) / NULLIF(SUM(i.leads), 0), 2) AS cpl,
        ROUND(SUM(i.roas * i.spend) / NULLIF(SUM(i.spend), 0), 2) AS roas
    FROM ad_insights_daily i
    JOIN ad_campaigns c ON c.id = i.campaign_id
    WHERE i.date_start >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY c.id, c.name, c.status
    ORDER BY spend DESC
    """
    return execute_sql(sql)


def get_leads_by_source_mtd() -> list[dict]:
    """Lead counts by source for current month-to-date."""
    sql = """
    SELECT
        COALESCE(lead_source, 'unknown') AS lead_source,
        COUNT(*) AS total_leads,
        COUNT(customer_id) AS converted_leads,
        ROUND(
            COUNT(customer_id)::numeric / NULLIF(COUNT(*), 0) * 100,
            1
        ) AS conversion_rate_pct
    FROM leads
    WHERE created_time >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY lead_source
    ORDER BY total_leads DESC
    """
    return execute_sql(sql)


def get_google_metrics_last30() -> list[dict]:
    """Google Business Profile metrics for the last 30 days."""
    sql = """
    SELECT
        metric_date,
        total_reviews,
        average_rating,
        searches_direct,
        searches_discovery,
        views_maps,
        views_search,
        calls,
        website_clicks,
        direction_requests
    FROM google_business_metrics
    WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY metric_date
    """
    return execute_sql(sql)


def get_sync_status() -> list[dict]:
    """Last successful sync time and status per source."""
    sql = """
    SELECT DISTINCT ON (source)
        source,
        status,
        records_upserted,
        completed_at,
        duration_seconds
    FROM sync_logs
    WHERE status = 'success'
    ORDER BY source, completed_at DESC
    """
    return execute_sql(sql)


def get_jobs_trend_mtd() -> list[dict]:
    """Job counts and value by week for the current month."""
    sql = """
    SELECT
        TO_CHAR(DATE_TRUNC('week', scheduled_start), 'YYYY-MM-DD') AS week_start,
        status,
        COUNT(*) AS job_count,
        ROUND(SUM(total_amount), 2) AS total_value
    FROM jobs
    WHERE scheduled_start >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY DATE_TRUNC('week', scheduled_start), status
    ORDER BY DATE_TRUNC('week', scheduled_start), status
    """
    return execute_sql(sql)


def get_ad_spend_daily_last30() -> list[dict]:
    """Daily ad spend for the last 30 days."""
    sql = """
    SELECT
        date_start AS date,
        ROUND(SUM(spend), 2) AS spend,
        SUM(leads) AS leads,
        ROUND(SUM(spend) / NULLIF(SUM(leads), 0), 2) AS cpl
    FROM ad_insights_daily
    WHERE date_start >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY date_start
    ORDER BY date_start
    """
    return execute_sql(sql)
