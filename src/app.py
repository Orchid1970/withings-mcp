"""
Withings MCP Application
========================
Main FastAPI application for Withings health data MCP server.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import scheduler
from src.scheduler import start_scheduler, stop_scheduler, get_scheduler_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown.
    """
    # Startup
    logger.info("Withings MCP starting up...")
    
    # Start background token refresh scheduler
    auto_refresh = os.getenv("AUTO_REFRESH_ENABLED", "true").lower() == "true"
    if auto_refresh:
        start_scheduler()
        logger.info("Automatic token refresh scheduler ENABLED")
    else:
        logger.info("Automatic token refresh scheduler DISABLED (set AUTO_REFRESH_ENABLED=true to enable)")
    
    logger.info(f"Admin endpoints enabled: {bool(os.getenv('ADMIN_API_TOKEN'))}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Withings MCP...")
    stop_scheduler()


# Create FastAPI app with lifespan
app = FastAPI(
    title="Withings MCP",
    description="MCP server for Withings health data integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
try:
    logger.info("Attempting to import admin routes...")
    from src.routes.admin import router as admin_router
    logger.info("Admin routes loaded successfully")
    logger.info("Including admin router...")
    app.include_router(admin_router)
    logger.info("Admin router included successfully")
except ImportError as e:
    logger.error(f"Could not import admin routes: {e}")
except Exception as e:
    logger.error(f"Error including admin router: {e}")

try:
    from src.routes.mcp_protocol import router as mcp_router
    app.include_router(mcp_router)
    logger.info("MCP protocol router included")
except ImportError as e:
    logger.warning(f"MCP protocol routes not available: {e}")

try:
    from src.routes.auth import router as auth_router
    app.include_router(auth_router, prefix="/auth")
    logger.info("Auth router included at /auth")
except ImportError as e:
    logger.warning(f"Auth routes not available: {e}")


@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Withings MCP",
        "version": "1.0.0",
        "status": "running",
        "description": "MCP server for Withings health data integration",
        "endpoints": {
            "health": "/health",
            "admin": "/admin/*",
            "mcp": "/mcp/*",
            "scheduler": "/admin/scheduler/status"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@app.get("/admin/scheduler/status")
async def scheduler_status():
    """
    Get scheduler status.
    """
    return get_scheduler_status()


@app.post("/")
async def handle_root_post(request: Request):
    """
    Handle POST to root - likely MCP request.
    """
    try:
        from src.routes.mcp_protocol import handle_mcp_request
        body = await request.json()
        return await handle_mcp_request(body)
    except ImportError as e:
        logger.error(f"Error processing MCP request: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "MCP handler not available", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
