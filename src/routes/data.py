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
            
            return {
                "status": "ok",
                "sleep": sleep_data,
                "count": len(sleep_data),
                "lookback_days": lookback_days
            }
    
    except Exception as e:
        return {"error": str(e)}


# ============== ENDPOINTS ==============

@router.get("/metrics")
async def get_metrics(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch weight metrics (measure_type=1)
    Returns weight measurements for the past N days (default 365)
    """
    return await fetch_withings_data(measure_type=1, lookback_days=lookback_days)


@router.get("/height")
async def get_height(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch height (measure_type=4)
    Returns height in meters
    """
    return await fetch_withings_data(measure_type=4, lookback_days=lookback_days)


@router.get("/blood-pressure")
async def get_blood_pressure(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch blood pressure data (systolic=10, diastolic=9)
    Returns BP readings for the past N days (default 365)
    """
    systolic = await fetch_withings_data(measure_type=10, lookback_days=lookback_days)
    diastolic = await fetch_withings_data(measure_type=9, lookback_days=lookback_days)
    
    return {
        "status": "ok",
        "systolic": systolic.get("measurements", []),
        "diastolic": diastolic.get("measurements", []),
        "count": len(systolic.get("measurements", [])),
        "lookback_days": lookback_days
    }


@router.get("/blood-glucose")
async def get_blood_glucose(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch blood glucose data (measure_type=148)
    Returns blood glucose readings in mg/dL for the past N days (default 365)
    Note: Requires CGM or glucose meter synced via HealthKit to Withings
    """
    return await fetch_withings_data(measure_type=148, lookback_days=lookback_days)


@router.get("/heart-rate")
async def get_heart_rate(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch resting heart rate (measure_type=11)
    Returns HR readings from scale measurements
    """
    return await fetch_withings_data(measure_type=11, lookback_days=lookback_days)


@router.get("/spo2")
async def get_spo2(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch SpO2/oxygen saturation (measure_type=54)
    Returns pulse oximetry readings
    """
    return await fetch_withings_data(measure_type=54, lookback_days=lookback_days)


@router.get("/temperature")
async def get_temperature(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch body temperature readings (measure_type=71)
    Returns temperature in Celsius from Withings Thermo
    """
    return await fetch_withings_data(measure_type=71, lookback_days=lookback_days)


@router.get("/body-composition")
async def get_body_composition(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch all Body Scan / body composition metrics in one call:
    - Weight (1)
    - Fat Free Mass (5)
    - Fat Ratio % (6)
    - Fat Mass (8)
    - Muscle Mass (76)
    - Hydration (77)
    - Bone Mass (88)
    - Visceral Fat (170)
    - Nerve Health/ECG (169)
    - Extracellular Water (168)
    - Intracellular Water (167)
    - Vascular Age (155)
    - Pulse Wave Velocity (91)
    """
    measure_types = [1, 5, 6, 8, 76, 77, 88, 170, 169, 168, 167, 155, 91]
    result = await fetch_multiple_measures(measure_types, lookback_days=lookback_days)
    
    if result.get("error"):
        return result
    
    # Organize measurements by type for easier consumption
    organized = {
        "weight": [],
        "fat_free_mass": [],
        "fat_ratio": [],
        "fat_mass": [],
        "muscle_mass": [],
        "hydration": [],
        "bone_mass": [],
        "visceral_fat": [],
        "nerve_health": [],
        "extracellular_water": [],
        "intracellular_water": [],
        "vascular_age": [],
        "pulse_wave_velocity": [],
    }
    
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
    
    for grp in result.get("measurements", []):
        timestamp = grp.get("date")
        for measure in grp.get("measures", []):
            mtype = measure.get("type")
            if mtype in type_to_name:
                value = measure.get("value") * (10 ** measure.get("unit", 0))
                organized[type_to_name[mtype]].append({
                    "timestamp": timestamp,
                    "value": value
                })
    
    return {
        "status": "ok",
        "body_composition": organized,
        "raw_count": result.get("count", 0),
        "lookback_days": lookback_days
    }


@router.get("/fat-mass")
async def get_fat_mass(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch fat mass (measure_type=8)
    Returns fat mass in kg
    """
    return await fetch_withings_data(measure_type=8, lookback_days=lookback_days)


@router.get("/fat-ratio")
async def get_fat_ratio(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch fat ratio/percentage (measure_type=6)
    Returns body fat percentage
    """
    return await fetch_withings_data(measure_type=6, lookback_days=lookback_days)


@router.get("/muscle-mass")
async def get_muscle_mass(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch muscle mass (measure_type=76)
    Returns muscle mass in kg from Body Scan
    """
    return await fetch_withings_data(measure_type=76, lookback_days=lookback_days)


@router.get("/bone-mass")
async def get_bone_mass(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch bone mass (measure_type=88)
    Returns bone mass in kg from Body Scan
    """
    return await fetch_withings_data(measure_type=88, lookback_days=lookback_days)


@router.get("/hydration")
async def get_hydration(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch hydration percentage (measure_type=77)
    Returns body water percentage from Body Scan
    """
    return await fetch_withings_data(measure_type=77, lookback_days=lookback_days)


@router.get("/visceral-fat")
async def get_visceral_fat(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch visceral fat index (measure_type=170)
    Returns visceral fat rating from Body Scan
    """
    return await fetch_withings_data(measure_type=170, lookback_days=lookback_days)


@router.get("/nerve-health")
async def get_nerve_health(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch nerve health/ECG score (measure_type=169)
    Returns nerve health assessment from Body Scan
    """
    return await fetch_withings_data(measure_type=169, lookback_days=lookback_days)


@router.get("/vascular-age")
async def get_vascular_age(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch vascular age (measure_type=155)
    Returns estimated vascular age from Body Scan
    """
    return await fetch_withings_data(measure_type=155, lookback_days=lookback_days)


@router.get("/pulse-wave-velocity")
async def get_pulse_wave_velocity(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch pulse wave velocity (measure_type=91)
    Returns PWV in m/s - indicator of arterial stiffness
    """
    return await fetch_withings_data(measure_type=91, lookback_days=lookback_days)


@router.get("/activity")
async def get_activity(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch activity data (steps, calories, distance, heart rate zones, etc.)
    Returns activity measurements for the past N days (default 365)
    """
    return await fetch_withings_activity(lookback_days=lookback_days)


@router.get("/sleep")
async def get_sleep(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch sleep summary data (duration, quality, stages, HR, RR, snoring, etc.)
    Returns sleep measurements for the past N days (default 365)
    """
    return await fetch_withings_sleep(lookback_days=lookback_days)


@router.get("/all")
async def get_all_data(lookback_days: int = Query(365, ge=1, le=1825)):
    """
    Fetch all available health data (weight, blood pressure, body composition, activity, sleep)
    """
    weight = await fetch_withings_data(measure_type=1, lookback_days=lookback_days)
    bp = await get_blood_pressure(lookback_days=lookback_days)
    body_comp = await get_body_composition(lookback_days=lookback_days)
    activity = await fetch_withings_activity(lookback_days=lookback_days)
    sleep = await fetch_withings_sleep(lookback_days=lookback_days)
    blood_glucose = await fetch_withings_data(measure_type=148, lookback_days=lookback_days)
    
    return {
        "status": "ok",
        "data": {
            "weight": weight,
            "blood_pressure": bp,
            "body_composition": body_comp,
            "blood_glucose": blood_glucose,
            "activity": activity,
            "sleep": sleep
        },
        "lookback_days": lookback_days
    }
