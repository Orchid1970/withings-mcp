"""
Token Refresh Scheduler
=======================
Background scheduler that automatically refreshes Withings tokens before expiration.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler_task: Optional[asyncio.Task] = None
_scheduler_running: bool = False

# Refresh interval in seconds (2 hours = 7200 seconds)
# Tokens expire in 3 hours, so we refresh at 2 hours to be safe
REFRESH_INTERVAL_SECONDS = int(os.getenv("TOKEN_REFRESH_INTERVAL_SECONDS", "7200"))


async def refresh_token_job():
    """
    Job that refreshes the Withings token.
    """
    try:
        from app.services.token_refresh import TokenRefreshService
        
        logger.info(f"[Scheduler] Starting scheduled token refresh at {datetime.now(timezone.utc).isoformat()}")
        
        service = TokenRefreshService()
        result = await service.do_refresh()
        
        if result.get("success"):
            logger.info(f"[Scheduler] Token refresh successful. Expires at: {result.get('expires_at')}. Persisted: {result.get('persisted')}")
        else:
            logger.error(f"[Scheduler] Token refresh failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"[Scheduler] Unexpected error during scheduled refresh: {e}")


async def scheduler_loop():
    """
    Main scheduler loop that runs token refresh on interval.
    """
    global _scheduler_running
    
    logger.info(f"[Scheduler] Starting scheduler loop. Refresh interval: {REFRESH_INTERVAL_SECONDS} seconds ({REFRESH_INTERVAL_SECONDS/3600:.1f} hours)")
    
    # Wait a bit on startup before first refresh (let app fully initialize)
    await asyncio.sleep(30)
    
    while _scheduler_running:
        try:
            # Run the refresh job
            await refresh_token_job()
            
            # Wait for next interval
            logger.info(f"[Scheduler] Next refresh in {REFRESH_INTERVAL_SECONDS} seconds")
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
            
        except asyncio.CancelledError:
            logger.info("[Scheduler] Scheduler loop cancelled")
            break
        except Exception as e:
            logger.error(f"[Scheduler] Error in scheduler loop: {e}")
            # Wait a bit before retrying on error
            await asyncio.sleep(60)
    
    logger.info("[Scheduler] Scheduler loop stopped")


def start_scheduler():
    """
    Start the background scheduler.
    """
    global _scheduler_task, _scheduler_running
    
    if _scheduler_task is not None and not _scheduler_task.done():
        logger.warning("[Scheduler] Scheduler already running")
        return
    
    _scheduler_running = True
    _scheduler_task = asyncio.create_task(scheduler_loop())
    logger.info("[Scheduler] Background scheduler started")


def stop_scheduler():
    """
    Stop the background scheduler.
    """
    global _scheduler_task, _scheduler_running
    
    _scheduler_running = False
    
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        logger.info("[Scheduler] Background scheduler stopped")


def get_scheduler_status() -> dict:
    """
    Get current scheduler status.
    
    Returns:
        Dict with scheduler status information
    """
    return {
        "running": _scheduler_running,
        "task_active": _scheduler_task is not None and not _scheduler_task.done() if _scheduler_task else False,
        "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
        "refresh_interval_hours": round(REFRESH_INTERVAL_SECONDS / 3600, 2)
    }
