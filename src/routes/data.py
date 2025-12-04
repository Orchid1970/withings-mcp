import logging
from fastapi import APIRouter, HTTPException
import httpx
from datetime import datetime, timedelta
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

WITHINGS_API = "https://wbsapi.withings.net/measure"
ACTIVITY_API = "https://wbsapi.withings.net/v2/activity"
SLEEP_API = "https://wbsapi.withings.net/v2/sleep"

# Hardcoded tokens from OAuth callback (temporary)
ACCESS_TOKEN = "e04acd69a637aeb3d85b7b4653492f8835b6578b"
USER_ID = "13932981"

@router.get("/metrics")
async def get_metrics(start_date: str = None, end_date: str = None):
    """
    Fetch body metrics (weight, body composition, etc.)
    start_date and end_date format: YYYY-MM-DD
    """
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Convert dates to Unix timestamps
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
    
    logger.info(f"Fetching metrics from {start_date} to {end_date}")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(WITHINGS_API, params={
                "action": "getmeas",
                "access_token": ACCESS_TOKEN,
                "startdate": start_ts,
                "enddate": end_ts,
                "meastype": "1,4,5,6,8,9,10,11,12",  # Weight, fat mass, muscle mass, bone mass, etc.
            })
            
            data = resp.json()
            if data.get("status") != 0:
                logger.error(f"Withings API error: {data}")
                raise HTTPException(status_code=400, detail=f"Withings API error: {data.get('error')}")
            
            logger.info(f"Retrieved {len(data.get('body', {}).get('measuregrps', []))} measurement groups")
            return data
    except Exception as e:
        logger.error(f"Error fetching metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/activity")
async def get_activity(start_date: str = None, end_date: str = None):
    """
    Fetch activity data (steps, calories, distance, etc.)
    start_date and end_date format: YYYY-MM-DD
    """
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
    
    logger.info(f"Fetching activity from {start_date} to {end_date}")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(ACTIVITY_API, params={
                "action": "getactivity",
                "access_token": ACCESS_TOKEN,
                "startdateymd": start_date,
                "enddateymd": end_date,
            })
            
            data = resp.json()
            if data.get("status") != 0:
                logger.error(f"Withings API error: {data}")
                raise HTTPException(status_code=400, detail=f"Withings API error: {data.get('error')}")
            
            logger.info(f"Retrieved {len(data.get('body', {}).get('activities', []))} activity records")
            return data
    except Exception as e:
        logger.error(f"Error fetching activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sleep")
async def get_sleep(start_date: str = None, end_date: str = None):
    """
    Fetch sleep data (duration, quality, REM, deep sleep, etc.)
    start_date and end_date format: YYYY-MM-DD
    """
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
    
    logger.info(f"Fetching sleep from {start_date} to {end_date}")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(SLEEP_API, params={
                "action": "getsleep",
                "access_token": ACCESS_TOKEN,
                "startdate": start_ts,
                "enddate": end_ts,
            })
            
            data = resp.json()
            if data.get("status") != 0:
                logger.error(f"Withings API error: {data}")
                raise HTTPException(status_code=400, detail=f"Withings API error: {data.get('error')}")
            
            logger.info(f"Retrieved {len(data.get('body', {}).get('sleep', []))} sleep records")
            return data
    except Exception as e:
        logger.error(f"Error fetching sleep: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all")
async def get_all_data(start_date: str = None, end_date: str = None):
    """
    Fetch all data (metrics, activity, sleep) in one call
    """
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    logger.info(f"Fetching all data from {start_date} to {end_date}")
    
    try:
        metrics = await get_metrics(start_date, end_date)
        activity = await get_activity(start_date, end_date)
        sleep = await get_sleep(start_date, end_date)
        
        return {
            "metrics": metrics,
            "activity": activity,
            "sleep": sleep
        }
    except Exception as e:
        logger.error(f"Error fetching all data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
