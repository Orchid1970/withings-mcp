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
    Fetch V2 activity data using correct Measure v2 endpoint [so-27]
    Supports: steps, distance, active duration, calories, heart rate
    """
    observations = []
    
    logger.info(f"Starting V2 activity fetch with token: {access_token[:20]}...")
    
    async with httpx.AsyncClient() as client:
