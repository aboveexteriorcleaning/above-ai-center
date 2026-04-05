"""
APScheduler — runs all ETL sync jobs on a schedule.
Persists job state to avoid duplicate runs on restart.

Run (keep alive in background):
    python tools/scheduler.py

Or run a single source immediately:
    python tools/scheduler.py --run quickbooks
    python tools/scheduler.py --run all
"""

import os
import sys
import logging
import argparse
import subprocess
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Sync job runner ───────────────────────────────────────────────────────────

def run_sync_job(script: str, args: list[str] | None = None, notify_slack: bool = True):
    """Run a sync script and optionally notify Slack on failure."""
    script_path = os.path.join(TOOLS_DIR, script)
    cmd = [sys.executable, script_path] + (args or ["--mode", "incremental"])

    logger.info("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode == 0:
            logger.info("SUCCESS: %s", script)
        else:
            error = (proc.stderr or proc.stdout or "")[-500:]
            logger.error("FAILED: %s\n%s", script, error)
            if notify_slack:
                _slack_notify(f"❌ Sync failed: `{script}`\n```{error}```")
    except subprocess.TimeoutExpired:
        logger.error("TIMEOUT: %s exceeded 10 minutes", script)
        if notify_slack:
            _slack_notify(f"⏱️ Sync timeout: `{script}` exceeded 10 minutes")
    except Exception as exc:
        logger.error("ERROR running %s: %s", script, exc, exc_info=True)
        if notify_slack:
            _slack_notify(f"❌ Scheduler error for `{script}`: {exc}")


def _slack_notify(message: str):
    """Post a message to the Slack channel (best-effort, no crash on failure)."""
    try:
        from slack_sdk import WebClient
        client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
        client.chat_postMessage(channel=os.environ["SLACK_CHANNEL_ID"], text=message)
    except Exception as exc:
        logger.warning("Slack notify failed: %s", exc)


# ── Individual sync job functions (called by scheduler) ───────────────────────

def sync_quo():
    run_sync_job("sync_quo_sms.py", ["--days-back", "2"])

def sync_jobber():
    run_sync_job("sync_jobber.py", ["--mode", "incremental", "--days-back", "30"])

def sync_gmail():
    run_sync_job("sync_gmail.py", ["--days-back", "7"])

def sync_facebook():
    run_sync_job("sync_facebook_ads.py", ["--lookback-days", "30"])

def sync_quickbooks():
    run_sync_job("sync_quickbooks.py", ["--mode", "incremental", "--days-back", "7"])

def sync_google():
    run_sync_job("sync_google.py", ["--days-back", "30"])

def sync_leads():
    run_sync_job("sync_leads_sheet.py", [])

def full_sync_all():
    """Weekly full re-sync across all sources."""
    logger.info("Starting weekly full sync...")
    for script, args in [
        ("sync_quickbooks.py", ["--mode", "full"]),
        ("sync_jobber.py", ["--mode", "full"]),
        ("sync_facebook_ads.py", ["--mode", "full"]),
        ("sync_google.py", ["--days-back", "365"]),
        ("sync_leads_sheet.py", []),
        ("sync_gmail.py", ["--days-back", "90"]),
        ("sync_quo_sms.py", ["--days-back", "90"]),
    ]:
        run_sync_job(script, args)
    logger.info("Weekly full sync complete.")


# ── Scheduler setup ───────────────────────────────────────────────────────────

def start_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor

    db_path = os.path.join(os.path.dirname(TOOLS_DIR), ".tmp", "scheduler.db")

    jobstores = {
        "default": SQLAlchemyJobStore(url=f"sqlite:///{db_path}")
    }
    executors = {
        "default": ThreadPoolExecutor(max_workers=2)  # max 2 syncs at once
    }

    scheduler = BlockingScheduler(jobstores=jobstores, executors=executors)

    # ── Schedule definitions ──────────────────────────────────────────────────
    # Quo SMS: every 60 minutes
    scheduler.add_job(sync_quo, "interval", minutes=60, id="sync_quo", replace_existing=True)

    # Jobber: every 2 hours
    scheduler.add_job(sync_jobber, "interval", hours=2, id="sync_jobber", replace_existing=True)

    # Gmail: every 3 hours
    scheduler.add_job(sync_gmail, "interval", hours=3, id="sync_gmail", replace_existing=True)

    # Facebook Ads: every 4 hours
    scheduler.add_job(sync_facebook, "interval", hours=4, id="sync_facebook", replace_existing=True)

    # QuickBooks: every 6 hours
    scheduler.add_job(sync_quickbooks, "interval", hours=6, id="sync_quickbooks", replace_existing=True)

    # Google Business: daily at 7am
    scheduler.add_job(sync_google, "cron", hour=7, minute=0, id="sync_google", replace_existing=True)

    # Lead sheet: every 4 hours
    scheduler.add_job(sync_leads, "interval", hours=4, id="sync_leads", replace_existing=True)

    # Weekly full sync: Sunday at 2am
    scheduler.add_job(full_sync_all, "cron", day_of_week="sun", hour=2, minute=0, id="full_sync", replace_existing=True)

    logger.info("Scheduler started with %d jobs. Press Ctrl+C to stop.", len(scheduler.get_jobs()))
    _slack_notify("🚀 Above AI scheduler started. All sync jobs are running on schedule.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        _slack_notify("⛔ Above AI scheduler stopped.")


# ── CLI ───────────────────────────────────────────────────────────────────────

RUNNABLE = {
    "quickbooks": sync_quickbooks,
    "jobber": sync_jobber,
    "facebook": sync_facebook,
    "ads": sync_facebook,
    "google": sync_google,
    "gmail": sync_gmail,
    "quo": sync_quo,
    "sms": sync_quo,
    "leads": sync_leads,
    "all": full_sync_all,
}


def main():
    parser = argparse.ArgumentParser(description="Above AI sync scheduler")
    parser.add_argument("--run", metavar="SOURCE", help="Run a specific source immediately and exit")
    args = parser.parse_args()

    if args.run:
        fn = RUNNABLE.get(args.run.lower())
        if not fn:
            print(f"Unknown source '{args.run}'. Valid: {', '.join(RUNNABLE.keys())}")
            sys.exit(1)
        fn()
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
