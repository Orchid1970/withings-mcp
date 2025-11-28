from fastapi import FastAPI # Removed redundant import of Depends, HTTPException, List, BaseModel
import logging
from contextlib import asynccontextmanager
from src.database import init_db
from src.routes.health import router as health_router
from src.routes.auth import router as auth_router
from src.routes.workflows import router as workflows_router
from src.routes.observations import router as observations_router # NEW: Import observations router
from src.scheduler import start_scheduler

logging.basicConfig(
    handlers=[logging.StreamHandler()],
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(api: FastAPI):
    logger.info("Starting Withings MCP...")
    #await init_db() # Still commented out for now
    #start_scheduler() # Still commented out for now
    yield
    logger.info("Shutting down Withings MCP...")

api = FastAPI(
    title="Withings MCP",
    description="Health Data Orchestrator - Withings to FHIR",
    version="1.0.0",
    lifespan=lifespan
)

# --- Router Inclusions ---
api.include_router(health_router)
api.include_router(auth_router, prefix="/auth")
api.include_router(workflows_router, prefix="/workflows")
api.include_router(observations_router) # NEW: Include observations router
