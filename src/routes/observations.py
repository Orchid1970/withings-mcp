import logging
from typing import List
from fastapi import APIRouter, HTTPException
import httpx
from datetime import datetime, timedelta, timezone
from src.schemas import WithingsObservation # Assuming WithingsObservation schema is defined
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Withings API Base URL for measures
WITHINGS_MEASURE_API_URL = "https://wbsapi.withings.net/measure"

@router.get("/observations", response_model=List[WithingsObservation])
async def get_all_observations_for_user():
    settings = get_settings()
    access_token = settings.WITHINGS_ACCESS_TOKEN
    
    if not access_token:
        logger.error("WITHINGS_ACCESS_TOKEN not found in environment variables.")
        raise HTTPException(status_code=401, detail="Withings access token not configured.")

    # Define the types of measures we want to fetch and their FHIR codes
    # Withings measure types: 1=Weight, 9=BMI, 12=Heart Rate
    measure_type_map = {
        1: {"code": "8302-2"},  # Weight (LOINC: Body weight)
        9: {"code": "39156-5"}, # BMI (LOINC: Body mass index (BMI) [Ratio])
        12: {"code": "8867-4"}  # Heart Rate (LOINC: Heart rate)
    }

    # Fetch data for the last 7 days to ensure recent data is available
    end_timestamp = int(datetime.now(timezone.utc).timestamp())
    start_timestamp = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    
    all_withings_observations: List[WithingsObservation] = []

    async with httpx.AsyncClient() as client:
        for withings_meastype_id, fhir_info in measure_type_map.items():
            params = {
                "action": "getmeas",
                "meastype": withings_meastype_id,
                "category": 1, # Fetch real measures
                "startdate": start_timestamp,
                "enddate": end_timestamp,
                "limit": 50 # Retrieve up to 50 recent measurements for each type
            }
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            try:
                response = await client.post(WITHINGS_MEASURE_API_URL, headers=headers, data=params)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                withings_data_json = response.json()

                if withings_data_json.get("status") != 0:
                    error_message = withings_data_json.get("error", {}).get("message", "Unknown Withings API error")
                    logger.error(f"Withings API error for meastype {withings_meastype_id}: {error_message} (Status: {withings_data_json.get('status')})")
                    # In a production system, you might want to handle specific errors like token expiry here
                    continue 
                
                measure_groups = withings_data_json["body"].get("measuregrps", [])
                
                for group in measure_groups:
                    group_date_time = datetime.fromtimestamp(group["date"], timezone.utc)
                    for measure in group["measures"]:
                        # Ensure the measure type matches what we requested (in case Withings returns other types in a group)
                        if measure["type"] == withings_meastype_id:
                            # Withings often scales values by 10^unit (e.g., weight in kg * 10^-3 for grams)
                            value = measure["value"] * (10**measure["unit"])
                            
                            observation_unit = ""
                            if withings_meastype_id == 1: # Weight
                                # Withings returns weight in kg; converting to lbs for consistency with previous mock data
                                value = value * 2.20462 # 1 kg = 2.20462 lbs
                                observation_unit = "lbs"
                            elif withings_meastype_id == 9: # BMI
                                # BMI is typically direct, unit is kg/m2
                                observation_unit = "kg/m2"
                            elif withings_meastype_id == 12: # Heart Rate
                                # Heart Rate is typically direct, unit is bpm
                                observation_unit = "bpm"
                                
                            all_withings_observations.append(
                                WithingsObservation(
                                    id=f"{fhir_info['code']}-{group_date_time.isoformat()}", # Generate a unique ID
                                    code=fhir_info["code"],
                                    value=round(value, 1), # Round value for cleaner output
                                    unit=observation_unit,
                                    effectiveDateTime=group_date_time.isoformat(timespec='seconds') + 'Z'
                                )
                            )
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching Withings data for meastype {withings_meastype_id}: {e} - Response: {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail=f"Withings API error: {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Network error fetching Withings data for meastype {withings_meastype_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Network error communicating with Withings: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing Withings data for meastype {withings_meastype_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    # Sort observations by date, most recent first
    all_withings_observations.sort(key=lambda obs: obs.effectiveDateTime, reverse=True)
    
    return all_withings_observations
