"""
Observations route for fetching Withings health data
Supports both V1 (metrics) and V2 (activity) endpoints
"""

import logging
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()
logger = logging.getLogger(__name__)

# Withings API endpoints
WITHINGS_MEASURE_V1 = "https://wbsapi.withings.net/measure"
WITHINGS_MEASURE_V2 = "https://wbsapi.withings.net/v2/measure"

# V1 Measurement types (metrics)
MEASUREMENT_TYPES_V1 = {
    1: "Weight",
    4: "Height",
    5: "Fat Free Mass",
    6: "Fat Ratio",
    8: "Fat Mass Weight",
    9: "BMI",
    10: "Muscle Mass",
    11: "Hydration",
    12: "Heart Rate",
    14: "Systolic Blood Pressure",
    15: "Diastolic Blood Pressure",
    20: "Calories",
    54: "Bone Mass",
    71: "Body Temperature",
    73: "Skin Temperature",
    74: "Heart Rate Variability",
    76: "VO2 Max",
    77: "SpO2",
    88: "Respiratory Rate"
}


async def fetch_v1_metrics(access_token: str, start_date: int, end_date: int) -> list:
    """
    Fetch V1 metrics data (weight, body composition, vitals)
    """
    observations = []
    
    logger.info(f"Starting V1 metrics fetch with token: {access_token[:20]}...")
    
    async with httpx.AsyncClient() as client:
        for meastype in MEASUREMENT_TYPES_V1.keys():
            try:
                logger.info(f"Fetching meastype {meastype} from Withings API (start: {start_date}, end: {end_date})")
                
                response = await client.post(
                    WITHINGS_MEASURE_V1,
                    data={
                        "action": "getmeas",
                        "meastypes": str(meastype),
                        "category": 1,
                        "startdate": start_date,
                        "enddate": end_date,
                        "access_token": access_token
                    },
                    timeout=10.0
                )
                
                logger.info(f"Withings API response status: {response.status_code} for meastype {meastype}")
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch meastype {meastype}: {response.text}")
                    continue
                
                data = response.json()
                
                if data.get("status") != 0:
                    logger.warning(f"Withings API error for meastype {meastype}: status={data.get('status')}, error={data.get('error')}")
                    continue
                
                body = data.get("body", {})
                measuregrps = body.get("measuregrps", [])
                
                logger.info(f"Type {meastype} ({MEASUREMENT_TYPES_V1[meastype]}): {len(measuregrps)} groups")
                
                for group in measuregrps:
                    measures = group.get("measures", [])
                    timestamp = group.get("date")
                    
                    for measure in measures:
                        value = measure.get("value")
                        unit = measure.get("unit")
                        
                        # Handle unit scaling
                        if unit and unit < 0:
                            value = value / (10 ** abs(unit))
                        
                        observation = {
                            "type": meastype,
                            "type_name": MEASUREMENT_TYPES_V1[meastype],
                            "value": value,
                            "unit": "varies",
                            "date": datetime.fromtimestamp(timestamp).isoformat()
                        }
                        observations.append(observation)
                
                logger.info(f"Added {len(measures)} measurements for type {meastype}")
            
            except Exception as e:
                logger.error(f"Error fetching meastype {meastype}: {str(e)}", exc_info=True)
                continue
    
    return observations


async def fetch_v2_activity(access_token: str, start_date: int, end_date: int) -> list:
    """
    Fetch V2 activity data (steps, distance, active time, etc.)
    """
    observations = []
    
    logger.info(f"Starting V2 activity fetch with token: {access_token[:20]}...")
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Fetching activity data from V2 endpoint (start: {start_date}, end: {end_date})")
            
            response = await client.post(
                f"{WITHINGS_MEASURE_V2}/getactivity",
                data={
                    "startdateymd": datetime.fromtimestamp(start_date).strftime("%Y-%m-%d"),
                    "enddateymd": datetime.fromtimestamp(end_date).strftime("%Y-%m-%d"),
                    "access_token": access_token
                },
                timeout=10.0
            )
            
            logger.info(f"Withings V2 API response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch V2 activity: {response.text}")
                return observations
            
            data = response.json()
            
            if data.get("status") != 0:
                logger.warning(f"Withings V2 API error: status={data.get('status')}, error={data.get('error')}")
                return observations
            
            body = data.get("body", {})
            activities = body.get("activities", [])
            
            logger.info(f"V2 Activity: Retrieved {len(activities)} activity records")
            
            for activity in activities:
                date = activity.get("date")
                
                # Extract activity metrics
                if activity.get("steps"):
                    observations.append({
                        "type": 16,
                        "type_name": "Steps",
                        "value": activity.get("steps"),
                        "unit": "steps",
                        "date": f"{date}T00:00:00"
                    })
                
                if activity.get("distance"):
                    observations.append({
                        "type": 17,
                        "type_name": "Distance",
                        "value": activity.get("distance"),
                        "unit": "meters",
                        "date": f"{date}T00:00:00"
                    })
                
                if activity.get("duration"):
                    observations.append({
                        "type": 21,
                        "type_name": "Active Duration",
                        "value": activity.get("duration"),
                        "unit": "seconds",
                        "date": f"{date}T00:00:00"
                    })
                
                if activity.get("calories"):
                    observations.append({
                        "type": 20,
                        "type_name": "Calories",
                        "value": activity.get("calories"),
                        "unit": "kcal",
                        "date": f"{date}T00:00:00"
                    })
                
                if activity.get("elevation"):
                    observations.append({
                        "type": 22,
                        "type_name": "Elevation",
                        "value": activity.get("elevation"),
                        "unit": "meters",
                        "date": f"{date}T00:00:00"
                    })
            
            logger.info(f"Added {len(observations)} activity observations from V2")
        
        except Exception as e:
            logger.error(f"Error fetching V2 activity: {str(e)}", exc_info=True)
    
    return observations


async def fetch_v2_intraday_activity(access_token: str, start_date: int, end_date: int) -> list:
    """
    Fetch V2 intraday activity data (hourly/minute-level steps, heart rate, etc.)
    """
    observations = []
    
    logger.info(f"Starting V2 intraday activity fetch with token: {access_token[:20]}...")
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Fetching intraday activity data from V2 endpoint (start: {start_date}, end: {end_date})")
            
            response = await client.post(
                f"{WITHINGS_MEASURE_V2}/getintradayactivity",
                data={
                    "startdate": start_date,
                    "enddate": end_date,
                    "access_token": access_token
                },
                timeout=10.0
            )
            
            logger.info(f"Withings V2 intraday API response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch V2 intraday activity: {response.text}")
                return observations
            
            data = response.json()
            
            if data.get("status") != 0:
                logger.warning(f"Withings V2 intraday API error: status={data.get('status')}, error={data.get('error')}")
                return observations
            
            body = data.get("body", {})
            series = body.get("series", {})
            
            logger.info(f"V2 Intraday Activity: Retrieved {len(series)} intraday records")
            
            for timestamp_str, metrics in series.items():
                timestamp = int(timestamp_str)
                date_str = datetime.fromtimestamp(timestamp).isoformat()
                
                if metrics.get("steps"):
                    observations.append({
                        "type": 16,
                        "type_name": "Steps (Intraday)",
                        "value": metrics.get("steps"),
                        "unit": "steps",
                        "date": date_str
                    })
                
                if metrics.get("heart_rate"):
                    observations.append({
                        "type": 12,
                        "type_name": "Heart Rate (Intraday)",
                        "value": metrics.get("heart_rate"),
                        "unit": "bpm",
                        "date": date_str
                    })
            
            logger.info(f"Added {len(observations)} intraday observations from V2")
        
        except Exception as e:
            logger.error(f"Error fetching V2 intraday activity: {str(e)}", exc_info=True)
    
    return observations


@router.get("/observations")
async def get_observations():
    """
    Fetch all health observations from both V1 and V2 endpoints
    Returns combined metrics and activity data
    """
    access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
    
    if not access_token:
        logger.error("WITHINGS_ACCESS_TOKEN not configured")
        raise HTTPException(status_code=500, detail="Access token not configured")
    
    # Calculate date range (last 7 days)
    end_date = int(datetime.now().timestamp())
    start_date = int((datetime.now() - timedelta(days=7)).timestamp())
    
    try:
        # Fetch from both V1 and V2 endpoints
        v1_observations = await fetch_v1_metrics(access_token, start_date, end_date)
        v2_daily_observations = await fetch_v2_activity(access_token, start_date, end_date)
        v2_intraday_observations = await fetch_v2_intraday_activity(access_token, start_date, end_date)
        
        # Combine all observations
        all_observations = v1_observations + v2_daily_observations + v2_intraday_observations
        
        logger.info(f"Returning {len(all_observations)} total observations")
        
        return all_observations
    
    except Exception as e:
        logger.error(f"Error fetching observations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching observations: {str(e)}")
