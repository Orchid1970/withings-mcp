"""
Withings Data Routes
Endpoints for fetching Withings health metrics, activity, and sleep data
"""

from fastapi import APIRouter, Query
from datetime import datetime, timedelta
import httpx
import os
from typing import Optional

router = APIRouter()

# Get access token from environment
ACCESS_TOKEN = os.getenv("WITHINGS_ACCESS_TOKEN", "")
USER_ID = os.getenv("WITHINGS_USER_ID", "")
BASE_URL = "https://wbsapi.withings.net"

async def fetch_withings_data(measure_type: int, lookback_days: int = 365) -> dict:
    """
    Fetch data from Withings API with pagination support
    measure_type: 1=weight, 4=height, 5=fat_free_mass, 6=fat_ratio, 8=fat_mass, 
                  9=diastolic_bp, 10=systolic_bp, 11=heart_rate, 12=temperature,
                  54=spo2, 71=body_temperature, 73=skin_temperature
    """
    if not ACCESS_TOKEN:
        return {"error": "WITHINGS_ACCESS_TOKEN not configured"}
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    params = {
        "action": "getmeas",
        "meastypes": measure_type,
        "startdate": int(start_date.timestamp()),
        "enddate": int(end_date.timestamp()),
        "limit": 100
    }
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    all_measurements = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            offset = 0
            while True:
                params["offset"] = offset
                response = await client.get(
                    f"{BASE_URL}/measure",
                    params=params,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != 0:
                    return {"error": f"Withings API error: {data.get('error', 'Unknown')}"}
                
                measures = data.get("body", {}).get("measuregrps", [])
                if not measures:
                    break
                
                all_measurements.extend(measures)
                
                # Check if there are more results
                if len(measures) < 100:
                    break
                
                offset += 100
        
        return {
            "status": "ok",
            "measurements": all_measurements,
            "count": len(all_measurements),
            "lookback_days": lookback_days
        }
    
    except Exception as e:
        return {"error": str(e)}


async def fetch_withings_activity(lookback_days: int = 365) -> dict:
    """
    Fetch activity data from Withings API
    Uses the v2/user endpoint for activity data
    """
    if not ACCESS_TOKEN or not USER_ID:
        return {"error": "WITHINGS_ACCESS_TOKEN or WITHINGS_USER_ID not configured"}
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    params = {
        "action": "getactivity",
        "startdateymd": start_date.strftime("%Y-%m-%d"),
        "enddateymd": end_date.strftime("%Y-%m-%d")
    }
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BASE_URL}/v2/user",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != 0:
                return {"error": f"Withings API error: {data.get('error', 'Unknown')}"}
            
            activities = data.get("body", {}).get("activities", [])
            
            return {
                "status": "ok",
                "activities": activities,
                "count": len(activities),
                "lookback_days": lookback_days
            }
    
    except Exception as e:
        return {"error": str(e)}


async def fetch_withings_sleep(lookback_days: int = 365) -> dict:
    """
    Fetch sleep data from Withings API
    Uses the v2/sleep endpoint
    """
    if not ACCESS_TOKEN or not USER_ID:
        return {"error": "WITHINGS_ACCESS_TOKEN or WITHINGS_USER_ID not configured"}
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    params = {
        "action": "getsleep",
        "startdate": int(start_date.timestamp()),
        "enddate": int(end_date.timestamp())
    }
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BASE_URL}/v2/sleep",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != 0:
                return {"error": f"Withings API error: {data.get('error', 'Unknown')}"}
            
            sleep_data = data.get("body", {}).get("sleep", [])
            
            return {
                "status": "ok",
                "sleep": sleep_data,
                "count": len(sleep_data),
                "lookback_days": lookback_days
            }
    
    except Exception as e:
        return {"error": str(e)}


@router.get("/metrics")
async def get_metrics(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch weight metrics (measure_type=1)
    Returns weight measurements for the past N days (default 365)
    """
    return await fetch_withings_data(measure_type=1, lookback_days=lookback_days)


@router.get("/blood-pressure")
async def get_blood_pressure(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch blood pressure data (systolic=10, diastolic=9)
    Returns BP readings for the past N days (default 365)
    """
    # Fetch both systolic and diastolic - we'll combine them
    systolic = await fetch_withings_data(measure_type=10, lookback_days=lookback_days)
    diastolic = await fetch_withings_data(measure_type=9, lookback_days=lookback_days)
    
    return {
        "status": "ok",
        "systolic": systolic.get("measurements", []),
        "diastolic": diastolic.get("measurements", []),
        "count": len(systolic.get("measurements", [])),
        "lookback_days": lookback_days
    }


@router.get("/activity")
async def get_activity(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch activity data (steps, calories, distance, etc.)
    Returns activity measurements for the past N days (default 365)
    """
    return await fetch_withings_activity(lookback_days=lookback_days)


@router.get("/sleep")
async def get_sleep(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch sleep data (duration, quality, REM, deep sleep, etc.)
    Returns sleep measurements for the past N days (default 365)
    """
    return await fetch_withings_sleep(lookback_days=lookback_days)


@router.get("/all")
async def get_all_data(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch all available health data (weight, blood pressure, activity, sleep)
    """
    metrics = await fetch_withings_data(measure_type=1, lookback_days=lookback_days)
    bp = await get_blood_pressure(lookback_days=lookback_days)
    activity = await fetch_withings_activity(lookback_days=lookback_days)
    sleep = await fetch_withings_sleep(lookback_days=lookback_days)
    
    return {
        "status": "ok",
        "data": {
            "weight": metrics,
            "blood_pressure": bp,
            "activity": activity,
            "sleep": sleep
        },
        "lookback_days": lookback_days
    }
