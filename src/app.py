from fastapi import FastAPI, Depends, HTTPException
from typing import List
from pydantic import BaseModel
# You might also need imports for your database operations, e.g.,
# from .database import get_db # If you have a separate database module
import logging
from contextlib import asynccontextmanager
from src.database import init_db
from src.routes.health import router as health_router
from src.routes.auth import router as auth_router
from src.routes.workflows import router as workflows_router
from src.scheduler import start_scheduler

logging.basicConfig(
    handlers=[logging.StreamHandler()],
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(api: FastAPI): # Changed 'app' to 'api' here
    logger.info("Starting Withings MCP...")
    await init_db()
    start_scheduler()
    yield
    logger.info("Shutting down Withings MCP...")

api = FastAPI(
    title="Withings MCP",
    description="Health Data Orchestrator - Withings to FHIR",
    version="1.0.0",
    lifespan=lifespan
)

# Define your FHIR-like Observation Pydantic model
# IMPORTANT: You'll need to adjust these fields to match the
# exact structure of the FHIR-like Observation data you are storing.
class WithingsObservation(BaseModel):
    id: str
    code: str
    value: float
    unit: str
    effectiveDateTime: str
    # Add any other fields that are part of your FHIR-like Observation structure, e.g.:
    # status: str = "final"
    # subject_reference: str
    # category_code: str
    # method_code: str
    # device_id: str


# Placeholder for user authentication.
# In a real-world scenario, this function would verify credentials
# (e.g., from an API key in the request header, or a session token)
# and return the authenticated user's internal ID.
# For now, we'll use a simplified approach assuming a single user ID.
def get_current_user_id() -> str:
    # This is a critical security point. For a production system exposed publicly,
    # you MUST implement robust authentication here to ensure that a request
    # for observations only returns data for the *authenticated* user.
    # For initial testing with a single user (your Withings ID),
    # you might hardcode it or retrieve it from a secure environment variable
    # tied to user 13932981 if your MCP supports multiple users.
    # Given the previous logs, user 13932981 is the one you've authorized.
    return "13932981" # Replace with actual dynamic user ID retrieval if applicable

# --- Include API routers AFTER the 'api' instance is defined ---
api.include_router(health_router)
api.include_router(auth_router, prefix="/auth")
api.include_router(workflows_router, prefix="/workflows")

# --- Start of new /observations endpoint code ---

@api.get("/observations", response_model=List[WithingsObservation]) # Changed '@app.get' to '@api.get'
async def get_all_observations_for_user(user_id: str = Depends(get_current_user_id)):
    """
    Retrieve all FHIR-like Observation resources for the authenticated user.
    """
    # *** IMPORTANT: Replace this placeholder logic with your actual database query ***
    # This is where you connect to your SQLite database (or other storage)
    # and fetch all the observations associated with the 'user_id'.
    # Ensure the data returned from your database matches the `WithingsObservation` Pydantic model.

    try:
        # Example: Mocking database retrieval. You will replace this.
        # This is a critical part where your MCP's database integration comes in.
        # If you're using a database abstraction layer (like SQLAlchemy with an ORM),
        # your code here would look something like:
        # observations_from_db = await Session.query(ObservationModel).filter_by(user_id=user_id).all()
        
        # For a simple example, let's return some hardcoded mock data for your user ID
        # if your database isn't fully set up to serve via this endpoint yet.
        
        if user_id == "13932981": # Assuming this is the authorized user
            # Replace with actual data fetched from your database for user 13932981
            observations = [
                WithingsObservation(
                    id="weight-20251127",
                    code="8302-2", # LOINC for Body Weight
                    value=182.5,
                    unit="lbs",
                    effectiveDateTime="2025-11-27T07:00:00Z"
                ),
                WithingsObservation(
                    id="bmi-20251127",
                    code="39156-5", # LOINC for BMI (Body Mass Index)
                    value=28.1,
                    unit="kg/m2",
                    effectiveDateTime="2025-11-27T07:00:00Z"
                ),
                WithingsObservation(
                    id="heartrate-20251127",
                    code="8867-4", # LOINC for Heart rate
                    value=65.0,
                    unit="bpm",
                    effectiveDateTime="2025-11-27T07:00:00Z"
                ),
                # Add more of your actual observation data here
            ]
            return observations
        else:
            # If the user_id doesn't match, or no data is found
            raise HTTPException(status_code=404, detail="No observations found for this user.")
            
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error fetching observations for user {user_id}: {e}") # Using your existing logger
        raise HTTPException(status_code=500, detail="Internal server error while fetching observations.")

# --- End of new /observations endpoint code ---
