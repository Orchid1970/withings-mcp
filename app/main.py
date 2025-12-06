"""
Withings MCP Application
========================
FastAPI application providing MCP (Model Context Protocol) interface for Withings health data.

Features:
- OAuth token management with automatic refresh
- MCP-compliant endpoints for AI assistant integration
- Admin endpoints for token management
- Background scheduler for automatic token refresh
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routers
from app.routes import health, mcp, admin
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Withings MCP application...")
    
    # Start background token refresh scheduler
    auto_refresh = os.getenv("AUTO_REFRESH_ENABLED", "true").lower() == "true"
    if auto_refresh:
        start_scheduler()
        logger.info("Automatic token refresh scheduler enabled")
    else:
        logger.info("Automatic token refresh scheduler disabled (set AUTO_REFRESH_ENABLED=true to enable)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Withings MCP application...")
    stop_scheduler()


# Create FastAPI app
app = FastAPI(
    title="Withings MCP",
    description="MCP server for Withings health data integration with AI assistants",
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

# Include routers
app.include_router(health.router)
app.include_router(mcp.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    """
    Root endpoint.
    
    Returns:
        Basic API information
    """
    return {
        "name": "Withings MCP",
        "version": "1.0.0",
        "description": "MCP server for Withings health data",
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp",
            "admin": "/admin"
        }
    }
