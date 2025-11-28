import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
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
async def lifespan(app: FastAPI):
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

api.include_router(health_router)
api.include_router(auth_router, prefix="/auth")
api.include_router(workflows_router, prefix="/workflows")