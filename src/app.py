"""
Withings MCP - FastAPI Application
===================================
Main application entry point with MCP protocol support.

Timothy's health optimization tracking via Withings API.
Deployed on Railway with Simtheory.ai MCP integration.
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track admin status
ADMIN_ENABLED = False
admin_router = None
admin_import_error = None

# Import token refresh admin routes (with detailed error logging)
try:
    logger.info("Attempting to import admin routes...")
    from app.routes.admin import router as admin_router
    ADMIN_ENABLED = True
    logger.info("Admin routes loaded successfully")
except ImportError as e:
    admin_import_error = str(e)
    logger.error(f"Admin routes import failed: {e}")
except Exception as e:
    admin_import_error = str(e)
    logger.error(f"Admin routes unexpected error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    logger.info("Withings MCP starting up...")
    logger.info(f"Admin endpoints enabled: {ADMIN_ENABLED}")
    yield
    logger.info("Withings MCP shutting down...")


# Create FastAPI application - DISABLE redirect_slashes to prevent 307 redirects
app = FastAPI(
    title="Withings MCP",
    description="Timothy's health optimization tracking via Withings API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False  # Prevent 307 redirects
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Define root endpoint FIRST before including any routers
@app.get("/")
async def root():
    """Root endpoint - service information."""
    return {
        "service": "withings-mcp",
        "version": "1.0.0",
        "description": "Timothy's health optimization tracking",
        "status": "operational",
        "admin_endpoints": ADMIN_ENABLED,
        "admin_import_error": admin_import_error,
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp",
            "auth": "/auth/callback",
            "admin_health": "/admin/health" if ADMIN_ENABLED else "disabled",
            "admin_token_status": "/admin/token/status" if ADMIN_ENABLED else "disabled",
            "admin_token_refresh": "/admin/token/refresh" if ADMIN_ENABLED else "disabled",
            "admin_config": "/admin/config" if ADMIN_ENABLED else "disabled"
        }
    }


@app.post("/")
async def root_post(request: Request):
    """Root POST handler for MCP protocol."""
    try:
        body = await request.json()
        logger.debug(f"MCP request received: {body.get('method', 'unknown')}")
        from src.routes.mcp_protocol import handle_mcp_request
        return await handle_mcp_request(body)
    except Exception as e:
        logger.error(f"Error processing MCP request: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy", "service": "withings-mcp"}


# Include admin router if available (without any prefix - routes have full paths)
if ADMIN_ENABLED and admin_router is not None:
    logger.info("Including admin router...")
    app.include_router(admin_router)
    logger.info("Admin router included successfully")


# Import and include other routers AFTER defining root endpoints
# Only include routers that don't conflict with our root endpoint
try:
    from src.routes import mcp_protocol
    # Only include the /mcp endpoint, not any root endpoints from this router
    app.include_router(mcp_protocol.router, tags=["mcp"])
    logger.info("MCP protocol router included")
except ImportError as e:
    logger.warning(f"Could not import mcp_protocol router: {e}")

try:
    from src.routes import auth
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    logger.info("Auth router included at /auth")
except ImportError as e:
    logger.warning(f"Could not import auth router: {e}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
