import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.withings_client import sync_all_users

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(sync_all_users, "interval", minutes=120, id="withings_sync")
    scheduler.start()
    logger.info("Scheduler started - syncing every 120 minutes")