"""
FastAPI application for Withings MCP service.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.routes import auth, health, observations, workflows, export, data, mcp_protocol

app = FastAPI(
    title="Withings MCP Service",
    description="Timothy's health optimization tracking via Withings API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(auth.router, prefix="/auth")
app.include_router(observations.router)
app.include_router(workflows.router)
app.include_router(export.router)
app.include_router(data.router, prefix="/withings")
app.include_router(mcp_protocol.router, prefix="/mcp", tags=["MCP Protocol"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Withings MCP",
        "version": "1.0.0",
        "description": "Timothy's health optimization tracking",
        "protocol": "MCP JSON-RPC compatible",
        "endpoints": {
            "health": "/health/",
            "auth": "/auth/",
            "withings": "/withings/",
            "mcp": "/mcp/",
            "export": "/export/excel"
        }
    }


@app.post("/")
async def root_mcp_handler(request: Request):
    """
    Root POST handler for MCP protocol.
    Simtheory may POST directly to root URL.
    """
    from src.routes.mcp_protocol import mcp_handler
    return await mcp_handler(request)
