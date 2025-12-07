"""
Withings Data Routes
Endpoints for fetching Withings health metrics, activity, and sleep data

TIMEZONE HANDLING:
- All Withings timestamps are Unix epoch seconds in UTC
- This module converts all timestamps to America/Los_Angeles (Pacific) for display
- Each measurement includes: timestamp (raw), datetime_utc, datetime_pacific, date_local
"""

from fastapi import APIRouter, Query
from datetime import datetime, timedelta, timezone
import httpx
import os
from typing import Optional
from zoneinfo import ZoneInfo

router = APIRouter()

# Get access token from environment
ACCESS_TOKEN = os.getenv("WITHINGS_ACCESS_TOKEN", "")
USER_ID = os.getenv("WITHINGS_USER_ID", "")
BASE_URL = "https://wbsapi.withings.net"

# Default timezone for display (Timothy's location)
DEFAULT_TIMEZONE = "America/Los_Angeles"

# Withings measure types reference
MEASURE_TYPES = {
    "weight": 1,
    "height": 4,
    "fat_free_mass": 5,
    "fat_ratio": 6,
    "fat_mass": 8,
    "diastolic_bp": 9,
    "systolic_bp": 10,
    "heart_rate": 11,
    "temperature": 12,
    "spo2": 54,
    "body_temperature": 71,
    "skin_temperature": 73,
    "muscle_mass": 76,
    "hydration": 77,
    "bone_mass": 88,
    "pulse_wave_velocity": 91,
    "blood_glucose": 148,
    "visceral_fat": 170,
    "nerve_health": 169,
    "extracellular_water": 168,
    "intracellular_water": 167,
    "vascular_age": 155,
    "fat_mass_segments": 174,
    "muscle_mass_segments": 175,
}


def convert_timestamp(ts: int, tz_name: str = None) -> dict:
    """
    Convert Unix timestamp (UTC) to multiple formats.
    
    Args:
        ts: Unix timestamp in seconds (UTC)
        tz_name: IANA timezone name (e.g., 'America/Los_Angeles', 'America/Boise')
                 Falls back to DEFAULT_TIMEZONE if not provided
    
    Returns:
        dict with timestamp, datetime_utc, datetime_pacific, date_local
    """
    if not ts:
        return None
    
    # Use provided timezone or default
    local_tz = ZoneInfo(tz_name) if tz_name else ZoneInfo(DEFAULT_TIMEZONE)
    pacific_tz = ZoneInfo(DEFAULT_TIMEZONE)
    
    # Convert from UTC timestamp
    utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    local_dt = utc_dt.astimezone(local_tz)
    pacific_dt = utc_dt.astimezone(pacific_tz)
    
    return {
        "timestamp": ts,
        "datetime_utc": utc_dt.isoformat(),
        "datetime_pacific": pacific_dt.isoformat(),
        "date_local": pacific_dt.strftime("%Y-%m-%d"),
        "time_local": pacific_dt.strftime("%H:%M:%S"),
        "timezone_device": tz_name or DEFAULT_TIMEZONE
    }


def format_measurement_group(grp: dict) -> dict:
    """
    Format a measurement group with proper timezone conversion.
    Extracts common fields and converts timestamps.
    """
    ts = grp.get("date")
    tz_name = grp.get("timezone", DEFAULT_TIMEZONE)
    
    time_info = convert_timestamp(ts, tz_name)
    
    return {
        "grpid": grp.get("grpid"),
        "model": grp.get("model"),
        "modelid": grp.get("modelid"),
        **time_info,
        "measures": grp.get("measures", [])
    }


async def fetch_withings_data(measure_type: int, lookback_days: int = 365) -> dict:
    """
    Fetch data from Withings API with pagination support
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
                    return {"error": f"Withings API error (status {data.get('status')}): {data.get('error', 'Unknown')}"}
                
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


async def fetch_multiple_measures(measure_types: list, lookback_days: int = 365) -> dict:
    """
    Fetch multiple measure types in a single API call
    """
    if not ACCESS_TOKEN:
        return {"error": "WITHINGS_ACCESS_TOKEN not configured"}
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    params = {
        "action": "getmeas",
        "meastypes": ",".join(str(m) for m in measure_types),
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
                    return {"error": f"Withings API error (status {data.get('status')}): {data.get('error', 'Unknown')}"}
                
                measures = data.get("body", {}).get("measuregrps", [])
                if not measures:
                    break
                
                all_measurements.extend(measures)
                
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
    Uses the v2/measure endpoint with POST for activity data
    """
    if not ACCESS_TOKEN:
        return {"error": "WITHINGS_ACCESS_TOKEN not configured"}
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    # All available activity data fields
    data_fields = ",".join([
        "steps",
        "distance",
        "elevation",
        "soft",
        "moderate",
        "intense",
        "active",
        "calories",
        "totalcalories",
        "hr_average",
        "hr_min",
        "hr_max",
        "hr_zone_0",
        "hr_zone_1",
        "hr_zone_2",
        "hr_zone_3"
    ])
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    payload = {
        "action": "getactivity",
        "startdateymd": start_date.strftime("%Y-%m-%d"),
        "enddateymd": end_date.strftime("%Y-%m-%d"),
        "data_fields": data_fields
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/v2/measure",
                headers=headers,
                data=payload
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != 0:
                return {"error": f"Withings API error (status {data.get('status')}): {data.get('error', 'Unknown')}"}
            
            activities = data.get("body", {}).get("activities", [])
            
            # Activity already has date strings and timezone, but let's add modified timestamp conversion
            for activity in activities:
                modified_ts = activity.get("modified")
                if modified_ts:
                    tz_name = activity.get("timezone", DEFAULT_TIMEZONE)
                    activity["modified_info"] = convert_timestamp(modified_ts, tz_name)
            
            return {
                "status": "ok",
                "activities": activities,
                "count": len(activities),
                "lookback_days": lookback_days,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                }
            }
    
    except Exception as e:
        return {"error": str(e)}


async def fetch_withings_sleep(lookback_days: int = 365) -> dict:
    """
    Fetch sleep summary data from Withings API
    Uses the v2/sleep endpoint with POST for sleep summaries
    """
    if not ACCESS_TOKEN:
        return {"error": "WITHINGS_ACCESS_TOKEN not configured"}
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    # All available sleep data fields
    data_fields = ",".join([
        "nb_rem_episodes",
        "sleep_efficiency",
        "sleep_latency",
        "total_sleep_time",
        "total_timeinbed",
        "wakeup_latency",
        "waso",
        "apnea_hypopnea_index",
        "breathing_disturbances_intensity",
        "asleepduration",
        "deepsleepduration",
        "durationtosleep",
        "durationtowakeup",
        "hr_average",
        "hr_max",
        "hr_min",
        "lightsleepduration",
        "night_events",
        "out_of_bed_count",
        "remsleepduration",
        "rr_average",
        "rr_max",
        "rr_min",
        "sleep_score",
        "snoring",
        "snoringepisodecount",
        "wakeupcount",
        "wakeupduration"
    ])
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    payload = {
        "action": "getsummary",
        "startdateymd": start_date.strftime("%Y-%m-%d"),
        "enddateymd": end_date.strftime("%Y-%m-%d"),
        "data_fields": data_fields
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/v2/sleep",
                headers=headers,
                data=payload
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != 0:
                return {"error": f"Withings API error (status {data.get('status')}): {data.get('error', 'Unknown')}"}
            
            sleep_data = data.get("body", {}).get("series", [])
            
            # Convert any timestamps in sleep data
            for sleep in sleep_data:
                if sleep.get("startdate"):
                    sleep["start_info"] = convert_timestamp(sleep.get("startdate"))
                if sleep.get("enddate"):
                    sleep["end_info"] = convert_timestamp(sleep.get("enddate"))
            
            return {
                "status": "ok",
                "sleep": sleep_data,
                "count": len(sleep_data),
                "lookback_days": lookback_days
            }
    
    except Exception as e:
        return {"error": str(e)}


# ============== ENDPOINTS ==============
# Note: All endpoints support both 'days' and 'lookback_days' query params
# 'days' is used by MCP protocol, 'lookback_days' is the internal param
# All timestamps are converted to America/Los_Angeles (Pacific) timezone

@router.get("/weight")
async def get_weight(
    days: Optional[int] = Query(None, ge=1, le=1825, description="Number of days (alias for lookback_days)"),
    lookback_days: int = Query(30, ge=1, le=1825, description="Number of days of history")
):
    """
    Fetch weight measurements (measure_type=1)
    Returns weight in kg and lbs with proper Pacific timezone conversion
    """
    effective_days = days if days is not None else lookback_days
    result = await fetch_withings_data(measure_type=1, lookback_days=effective_days)
    
    if result.get("error"):
        return result
    
    # Process measurements with timezone conversion
    processed = []
    for grp in result.get("measurements", []):
        ts = grp.get("date")
        tz_name = grp.get("timezone", DEFAULT_TIMEZONE)
        time_info = convert_timestamp(ts, tz_name)
        
        for measure in grp.get("measures", []):
            if measure.get("type") == 1:  # weight
                kg = measure.get("value") * (10 ** measure.get("unit", 0))
                lbs = kg * 2.20462
                processed.append({
                    **time_info,
                    "kg": round(kg, 2),
                    "lbs": round(lbs, 1),
                    "model": grp.get("model"),
                })
    
    # Sort by timestamp descending (most recent first)
    processed.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "status": "ok",
        "weight_measurements": processed,
        "count": len(processed),
        "days": effective_days,
        "timezone_note": "All times converted to America/Los_Angeles (Pacific)",
        "unit_note": "Weight provided in both kg and lbs"
    }


@router.get("/metrics")
async def get_metrics(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch weight metrics (measure_type=1) - raw format
    Returns weight measurements for the past N days (default 365)
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=1, lookback_days=effective_days)


@router.get("/height")
async def get_height(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch height (measure_type=4)
    Returns height in meters
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=4, lookback_days=effective_days)


@router.get("/blood-pressure")
async def get_blood_pressure(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch blood pressure data (systolic=10, diastolic=9)
    Returns BP readings with proper Pacific timezone conversion
    """
    effective_days = days if days is not None else lookback_days
    systolic_result = await fetch_withings_data(measure_type=10, lookback_days=effective_days)
    diastolic_result = await fetch_withings_data(measure_type=9, lookback_days=effective_days)
    
    if systolic_result.get("error"):
        return systolic_result
    
    # Build a map of grpid -> diastolic value
    diastolic_map = {}
    for grp in diastolic_result.get("measurements", []):
        grpid = grp.get("grpid")
        for measure in grp.get("measures", []):
            if measure.get("type") == 9:
                diastolic_map[grpid] = measure.get("value")
    
    # Process systolic and combine with diastolic
    processed = []
    for grp in systolic_result.get("measurements", []):
        ts = grp.get("date")
        tz_name = grp.get("timezone", DEFAULT_TIMEZONE)
        time_info = convert_timestamp(ts, tz_name)
        grpid = grp.get("grpid")
        
        for measure in grp.get("measures", []):
            if measure.get("type") == 10:  # systolic
                systolic_val = measure.get("value")
                diastolic_val = diastolic_map.get(grpid)
                
                processed.append({
                    **time_info,
                    "systolic": systolic_val,
                    "diastolic": diastolic_val,
                    "reading": f"{systolic_val}/{diastolic_val}" if diastolic_val else f"{systolic_val}/-",
                    "model": grp.get("model"),
                })
    
    # Sort by timestamp descending
    processed.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "status": "ok",
        "blood_pressure": processed,
        "count": len(processed),
        "days": effective_days,
        "timezone_note": "All times converted to America/Los_Angeles (Pacific)"
    }


@router.get("/blood-glucose")
async def get_blood_glucose(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch blood glucose data (measure_type=148)
    Returns blood glucose readings in mg/dL for the past N days (default 365)
    Note: Requires CGM or glucose meter synced via HealthKit to Withings
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=148, lookback_days=effective_days)


@router.get("/heart-rate")
async def get_heart_rate(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch resting heart rate (measure_type=11)
    Returns HR readings with proper Pacific timezone conversion
    """
    effective_days = days if days is not None else lookback_days
    result = await fetch_withings_data(measure_type=11, lookback_days=effective_days)
    
    if result.get("error"):
        return result
    
    # Process measurements with timezone conversion
    processed = []
    for grp in result.get("measurements", []):
        ts = grp.get("date")
        tz_name = grp.get("timezone", DEFAULT_TIMEZONE)
        time_info = convert_timestamp(ts, tz_name)
        
        for measure in grp.get("measures", []):
            if measure.get("type") == 11:  # heart rate
                bpm = measure.get("value")
                processed.append({
                    **time_info,
                    "bpm": bpm,
                    "model": grp.get("model"),
                })
    
    # Sort by timestamp descending
    processed.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "status": "ok",
        "heart_rate": processed,
        "count": len(processed),
        "days": effective_days,
        "timezone_note": "All times converted to America/Los_Angeles (Pacific)"
    }


@router.get("/spo2")
async def get_spo2(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch SpO2/oxygen saturation (measure_type=54)
    Returns pulse oximetry readings
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=54, lookback_days=effective_days)


@router.get("/temperature")
async def get_temperature(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch body temperature readings (measure_type=71)
    Returns temperature in Celsius from Withings Thermo
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=71, lookback_days=effective_days)


@router.get("/body-composition")
async def get_body_composition(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch all Body Scan / body composition metrics in one call with timezone conversion
    """
    effective_days = days if days is not None else lookback_days
    measure_types = [1, 5, 6, 8, 76, 77, 88, 170, 169, 168, 167, 155, 91]
    result = await fetch_multiple_measures(measure_types, lookback_days=effective_days)
    
    if result.get("error"):
        return result
    
    type_to_name = {
        1: "weight",
        5: "fat_free_mass",
        6: "fat_ratio",
        8: "fat_mass",
        76: "muscle_mass",
        77: "hydration",
        88: "bone_mass",
        170: "visceral_fat",
        169: "nerve_health",
        168: "extracellular_water",
        167: "intracellular_water",
        155: "vascular_age",
        91: "pulse_wave_velocity",
    }
    
    # Organize measurements by type with timezone conversion
    organized = {name: [] for name in type_to_name.values()}
    
    for grp in result.get("measurements", []):
        ts = grp.get("date")
        tz_name = grp.get("timezone", DEFAULT_TIMEZONE)
        time_info = convert_timestamp(ts, tz_name)
        
        for measure in grp.get("measures", []):
            mtype = measure.get("type")
            if mtype in type_to_name:
                value = measure.get("value") * (10 ** measure.get("unit", 0))
                organized[type_to_name[mtype]].append({
                    **time_info,
                    "value": round(value, 2) if isinstance(value, float) else value
                })
    
    # Sort each category by timestamp descending
    for key in organized:
        organized[key].sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "status": "ok",
        "body_composition": organized,
        "raw_count": result.get("count", 0),
        "days": effective_days,
        "timezone_note": "All times converted to America/Los_Angeles (Pacific)"
    }


@router.get("/fat-mass")
async def get_fat_mass(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch fat mass (measure_type=8)
    Returns fat mass in kg
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=8, lookback_days=effective_days)


@router.get("/fat-ratio")
async def get_fat_ratio(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch fat ratio/percentage (measure_type=6)
    Returns body fat percentage
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=6, lookback_days=effective_days)


@router.get("/muscle-mass")
async def get_muscle_mass(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch muscle mass (measure_type=76)
    Returns muscle mass in kg from Body Scan
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=76, lookback_days=effective_days)


@router.get("/bone-mass")
async def get_bone_mass(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch bone mass (measure_type=88)
    Returns bone mass in kg from Body Scan
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=88, lookback_days=effective_days)


@router.get("/hydration")
async def get_hydration(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch hydration percentage (measure_type=77)
    Returns body water percentage from Body Scan
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=77, lookback_days=effective_days)


@router.get("/visceral-fat")
async def get_visceral_fat(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch visceral fat index (measure_type=170)
    Returns visceral fat rating from Body Scan
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=170, lookback_days=effective_days)


@router.get("/nerve-health")
async def get_nerve_health(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch nerve health/ECG score (measure_type=169)
    Returns nerve health assessment from Body Scan
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=169, lookback_days=effective_days)


@router.get("/vascular-age")
async def get_vascular_age(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch vascular age (measure_type=155)
    Returns estimated vascular age from Body Scan
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=155, lookback_days=effective_days)


@router.get("/pulse-wave-velocity")
async def get_pulse_wave_velocity(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch pulse wave velocity (measure_type=91)
    Returns PWV in m/s - indicator of arterial stiffness
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_data(measure_type=91, lookback_days=effective_days)


@router.get("/activity")
async def get_activity(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch activity data (steps, calories, distance, heart rate zones, etc.)
    Returns activity measurements for the past N days (default 365)
    Note: Activity already includes date strings and timezone from Withings
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_activity(lookback_days=effective_days)


@router.get("/sleep")
async def get_sleep(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch sleep summary data (duration, quality, stages, HR, RR, snoring, etc.)
    Returns sleep measurements for the past N days (default 365)
    """
    effective_days = days if days is not None else lookback_days
    return await fetch_withings_sleep(lookback_days=effective_days)


@router.get("/all")
async def get_all_data(
    days: Optional[int] = Query(None, ge=1, le=1825),
    lookback_days: int = Query(365, ge=1, le=1825)
):
    """
    Fetch all available health data (weight, blood pressure, body composition, activity, sleep)
    """
    effective_days = days if days is not None else lookback_days
    weight = await get_weight(days=effective_days)
    bp = await get_blood_pressure(days=effective_days)
    body_comp = await get_body_composition(days=effective_days)
    hr = await get_heart_rate(days=effective_days)
    activity = await fetch_withings_activity(lookback_days=effective_days)
    sleep = await fetch_withings_sleep(lookback_days=effective_days)
    blood_glucose = await fetch_withings_data(measure_type=148, lookback_days=effective_days)
    
    return {
        "status": "ok",
        "data": {
            "weight": weight,
            "blood_pressure": bp,
            "body_composition": body_comp,
            "heart_rate": hr,
            "blood_glucose": blood_glucose,
            "activity": activity,
            "sleep": sleep
        },
        "days": effective_days,
        "timezone_note": "All times converted to America/Los_Angeles (Pacific)"
    }
