"""
Observations routes for Withings MCP
Fetches health measurements from Withings API
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)

# Withings measurement types - comprehensive list
MEASUREMENT_TYPES = {
    1: {"name": "Weight", "unit": "kg", "convert_to_lbs": True},
    4: {"name": "Height", "unit": "m"},
    5: {"name": "Fat Free Mass", "unit": "kg", "convert_to_lbs": True},
    6: {"name": "Fat Ratio", "unit": "%"},
    8: {"name": "Fat Mass Weight", "unit": "kg", "convert_to_lbs": True},
    9: {"name": "BMI", "unit": "kg/m²"},
    10: {"name": "Muscle Mass", "unit": "kg", "convert_to_lbs": True},
    11: {"name": "Hydration", "unit": "kg"},
    12: {"name": "Heart Rate", "unit": "bpm"},
    14: {"name": "Systolic Blood Pressure", "unit": "mmHg"},
    15: {"name": "Diastolic Blood Pressure", "unit": "mmHg"},
    16: {"name": "Steps", "unit": "count"},
    17: {"name": "Distance", "unit": "m"},
    20: {"name": "Calories Burned", "unit": "kcal"},
    21: {"name": "Active Time", "unit": "minutes"},
    22: {"name": "Elevation", "unit": "m"},
    44: {"name": "Sleep Duration", "unit": "seconds"},
    45: {"name": "Sleep Quality", "unit": "%"},
    54: {"name": "Bone Mass", "unit": "kg", "convert_to_lbs": True},
    71: {"name": "Body Temperature", "unit": "°C"},
    73: {"name": "Skin Temperature", "unit": "°C"},
    74: {"name": "Heart Rate Variability", "unit": "ms"},
    76: {"name": "VO2 Max", "unit": "ml/kg/min"},
    77: {"name": "SpO2", "unit": "%"},
    88: {"name": "Respiratory Rate", "unit": "breaths/min"},
}


def convert_value(value: float, meastype: int) -> float:
    """Convert measurement value if needed (e.g., kg to lbs)"""
    if MEASUREMENT_TYPES.get(meastype, {}).get("convert_to_lbs"):
        return round(value * 2.20462, 2)
    return round(value, 2)


async def fetch_withings_data(
    access_token: str,
    meastype: int,
    days_back: int = 7,
    timeout: int = 5
) -> Optional[list]:
    """
    Fetch measurement data from Withings API
    
    Args:
        access_token: Withings API access token
        meastype: Measurement type ID
        days_back: Number of days to look back
        timeout: Request timeout in seconds
    
    Returns:
        List of measurements or None if error
    """
    start_date = int((datetime.now() - timedelta(days=days_back)).timestamp())
    end_date = int(datetime.now().timestamp())
    
    payload = {
        "action": "getmeas",
        "meastype": meastype,
        "startdate": start_date,
        "enddate": end_date,
        "lastupdate": 0,
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://wbsapi.withings.net/measure",
                data=payload,
                headers=headers,
                timeout=float(timeout)
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 0:
                    measuregrps = data.get("body", {}).get("measuregrps", [])
                    logger.info(f"Type {meastype} ({MEASUREMENT_TYPES.get(meastype, {}).get('name', 'Unknown')}): {len(measuregrps)} groups")
                    return measuregrps
                else:
                    error_msg = data.get("error", "Unknown error")
                    logger.warning(f"Withings API error for meastype {meastype}: {error_msg}")
                    return None
            else:
                logger.warning(f"Withings API HTTP {response.status_code} for meastype {meastype}")
                return None
                
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching meastype {meastype}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching meastype {meastype}: {str(e)}")
        return None


def parse_measurements(measuregrps: list, meastype: int) -> list:
    """
    Parse measurement groups from Withings API response
    
    Args:
        measuregrps: List of measurement groups from API
        meastype: Measurement type ID
    
    Returns:
        List of parsed measurements
    """
    measurements = []
    
    for group in measuregrps:
        measures = group.get("measures", [])
        for measure in measures:
            if measure.get("type") == meastype:
                value = measure.get("value", 0)
                unit = measure.get("unit", 0)
                
                # Apply unit scaling (Withings uses unit field for decimal places)
                if unit != 0:
                    value = value * (10 ** unit)
                
                # Convert if needed
                converted_value = convert_value(value, meastype)
                
                measurements.append({
                    "type": meastype,
                    "type_name": MEASUREMENT_TYPES.get(meastype, {}).get("name", "Unknown"),
                    "value": converted_value,
                    "unit": MEASUREMENT_TYPES.get(meastype, {}).get("unit", ""),
                    "date": datetime.fromtimestamp(group.get("date", 0)).isoformat(),
                })
    
    return measurements


@router.get("/observations")
async def get_observations(access_token: Optional[str] = None):
    """
    Get all health observations from Withings
    Fetches comprehensive measurement data for the last 7 days
    """
    import os
    
    token = access_token or os.getenv("WITHINGS_ACCESS_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Withings access token not configured")
    
    all_observations = []
    
    # Fetch measurement types sequentially with timeout protection
    for meastype in sorted(MEASUREMENT_TYPES.keys()):
        try:
            measuregrps = await fetch_withings_data(token, meastype, timeout=5)
            
            if measuregrps:
                measurements = parse_measurements(measuregrps, meastype)
                all_observations.extend(measurements)
            
            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(0.2)
            
        except Exception as e:
            logger.error(f"Unexpected error processing meastype {meastype}: {str(e)}")
            continue
    
    # Sort by date descending
    all_observations.sort(key=lambda x: x["date"], reverse=True)
    
    logger.info(f"Returning {len(all_observations)} total observations")
    return all_observations
