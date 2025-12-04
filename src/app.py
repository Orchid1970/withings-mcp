"""
FastAPI application for Withings MCP service.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import auth, health, observations, workflows, export

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
app.include_router(auth.router)
app.include_router(observations.router)
app.include_router(workflows.router)
app.include_router(export.router)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Withings MCP",
        "version": "1.0.0",
        "description": "Timothy's health optimization tracking",
        "endpoints": {
            "health": "/health/",
            "auth": "/auth/",
            "data": "/data/",
            "export": "/export/excel"
        }
    }
