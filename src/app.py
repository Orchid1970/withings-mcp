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

# Log Python path for debugging
logger.info(f"Python path: {sys.path}")
logger.info(f"Current working directory: {os.getcwd()}")

# Import existing routes
from src.routes import auth, health, mcp_protocol

# Track admin status
ADMIN_ENABLED = False
admin_router = None
admin_import_error = None

# Import token refresh admin routes (with detailed error logging)
try:
    logger.info("Attempting to import admin routes...")
    from app.routes.admin import router as admin_router
    logger.info(f"Admin router imported: {admin_router}")
    logger.info(f"Admin router routes: {admin_router.routes}")
    ADMIN_ENABLED = True
    logger.info("Admin routes loaded successfully")
except ImportError as e:
    admin_import_error = str(e)
    logger.error(f"Admin routes import failed: {e}")
    import traceback
    logger.error(traceback.format_exc())
except Exception as e:
    admin_import_error = str(e)
    logger.error(f"Admin routes unexpected error: {e}")
    import traceback
    logger.error(traceback.format_exc())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    logger.info("Withings MCP starting up...")
    logger.info(f"Admin endpoints enabled: {ADMIN_ENABLED}")
    if admin_import_error:
        logger.warning(f"Admin import error was: {admin_import_error}")
    
    # Log all registered routes
    logger.info("Registered routes:")
    for route in app.routes:
        if hasattr(route, 'path'):
            methods = getattr(route, 'methods', ['N/A'])
            logger.info(f"  {methods} {route.path}")
    
    yield
    logger.info("Withings MCP shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Withings MCP",
    description="Timothy's health optimization tracking via Withings API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include existing routers
logger.info("Including auth router...")
app.include_router(auth.router)
logger.info("Including health router...")
app.include_router(health.router)
logger.info("Including mcp_protocol router...")
app.include_router(mcp_protocol.router)

# Include admin router if available
if ADMIN_ENABLED and admin_router is not None:
    logger.info(f"Including admin router with prefix: {admin_router.prefix}")
    app.include_router(admin_router)
    logger.info("Admin router included successfully")
else:
    logger.warning(f"Admin router NOT included. ADMIN_ENABLED={ADMIN_ENABLED}, admin_router={admin_router}")


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
            "admin": "/admin/*" if ADMIN_ENABLED else "disabled"
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
