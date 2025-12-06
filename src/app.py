"""
Withings MCP - FastAPI Application
===================================
Main application entry point with MCP protocol support.

Timothy's health optimization tracking via Withings API.
Deployed on Railway with Simtheory.ai MCP integration.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import token refresh admin routes (optional - graceful fallback if not available)
try:
    from app.routes.admin import router as admin_router
    from app.utils.logging_config import setup_logging
    ADMIN_ENABLED = True
    logger.info("Admin routes loaded successfully")
except ImportError as e:
    ADMIN_ENABLED = False
    logger.warning(f"Admin routes not available: {e}")

# Import existing routes - CORRECTED: mcp_protocol not mcp
from src.routes import auth, health, mcp_protocol
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Withings MCP starting up...")
    
    # Setup structured logging if admin module is available
    if ADMIN_ENABLED:
        setup_logging()
        logger.info("Structured logging configured")
    
    logger.info(f"Admin endpoints enabled: {ADMIN_ENABLED}")
    yield
    
    # Shutdown
    logger.info("Withings MCP shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Withings MCP",
    description="Timothy's health optimization tracking via Withings API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - allow all origins for MCP compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include existing routers
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(mcp_protocol.router)

# Include admin router for token management (if available)
if ADMIN_ENABLED:
    app.include_router(admin_router)
    logger.info("Admin router included at /admin/*")


@app.get("/")
async def root():
    """
    Root endpoint - service information.
    
    Returns basic service info and status.
    """
    return {
        "service": "withings-mcp",
        "version": "1.0.0",
        "description": "Timothy's health optimization tracking",
        "status": "operational",
        "admin_endpoints": ADMIN_ENABLED,
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp",
            "auth": "/auth/callback",
            "admin": "/admin/*" if ADMIN_ENABLED else "disabled"
        }
    }


@app.post("/")
async def root_post(request: Request):
    """
    Root POST handler for MCP protocol.
    
    Simtheory.ai sends MCP requests to the root endpoint.
    This handler forwards them to the MCP router.
    """
    try:
        body = await request.json()
        logger.debug(f"MCP request received: {body.get('method', 'unknown')}")
        
        # Forward to MCP handler
        from src.routes.mcp_protocol import handle_mcp_request
        return await handle_mcp_request(body)
        
    except Exception as e:
        logger.error(f"Error processing MCP request: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("ENVIRONMENT") == "development" else None
        }
    )
