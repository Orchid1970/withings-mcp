"""
Withings MCP - Main Application
FastAPI application for Withings health data integration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes.health import router as health_router
from src.routes.observations import router as observations_router
from src.routes.auth import router as auth_router

api = FastAPI(
    title="Withings MCP",
    description="Withings health data integration - Timothy's health optimization tracking",
    version="1.0.0"
)

# CORS middleware
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint for Simtheory MCP validation
@api.get("/")
def root():
    return {
        "status": "ok",
        "service": "withings-mcp",
        "version": "1.0.0",
        "description": "Withings health data integration for Timothy Escamilla"
    }

# Include routers
api.include_router(health_router, prefix="/health")
api.include_router(observations_router, prefix="/observations")
api.include_router(auth_router, prefix="/auth")

# Alias for compatibility
app = api
