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
                        
                        # Convert weight from kg to lbs (type 1 is Weight)
                        if meastype == 1 and value:
                            value = value * 2.20462
                            unit_label = "lbs"
                        else:
                            unit_label = "varies"
                        
                        observation = {
                            "type": meastype,
                            "type_name": MEASUREMENT_TYPES_V1[meastype],
                            "value": value,
                            "unit": unit_label,
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
    Fetch V2 activity data using correct Measure v2 endpoint
    Supports: steps, distance, active duration, calories, heart rate
    """
    observations = []
    
    logger.info(f"Starting V2 activity fetch with token: {access_token[:20]}...")
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Fetching V2 activity data (start: {start_date}, end: {end_date})")
            
            response = await client.post(
                WITHINGS_MEASURE_V2,
                data={
                    "action": "getactivity",
                    "startdate": start_date,
                    "enddate": end_date,
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
            
            logger.info(f"V2 Activity: {len(activities)} activity records")
            
            for activity in activities:
                timestamp = activity.get("date")
                
                observation = {
                    "type": "activity",
                    "type_name": "Activity",
                    "steps": activity.get("steps", 0),
                    "distance": activity.get("distance", 0),
                    "duration": activity.get("duration", 0),
                    "calories": activity.get("calories", 0),
                    "heart_rate": activity.get("heart_rate", 0),
                    "date": datetime.fromtimestamp(timestamp).isoformat()
                }
                observations.append(observation)
            
            logger.info(f"Added {len(activities)} activity records")
        
        except Exception as e:
            logger.error(f"Error fetching V2 activity: {str(e)}", exc_info=True)
    
    return observations


@router.get("/observations")
async def get_observations(days: int = 7):
    """
    Get health observations from Withings
    Query parameters:
    - days: number of days to fetch (default: 7)
    """
    try:
        access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
        if not access_token:
            logger.error("WITHINGS_ACCESS_TOKEN not set")
            raise HTTPException(status_code=500, detail="Withings token not configured")
        
        # Calculate date range
        end_date = int(datetime.utcnow().timestamp())
        start_date = int((datetime.utcnow() - timedelta(days=days)).timestamp())
        
        logger.info(f"Fetching observations for {days} days (start: {start_date}, end: {end_date})")
        
        # Fetch both V1 and V2 data
        v1_data = await fetch_v1_metrics(access_token, start_date, end_date)
        v2_data = await fetch_v2_activity(access_token, start_date, end_date)
        
        all_observations = v1_data + v2_data
        
        logger.info(f"Total observations retrieved: {len(all_observations)}")
        
        return {
            "status": "success",
            "count": len(all_observations),
            "observations": all_observations
        }
    
    except Exception as e:
        logger.error(f"Error in get_observations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
