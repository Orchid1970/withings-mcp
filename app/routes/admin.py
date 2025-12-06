"""
Admin Routes for Token Management
==================================
Endpoints for managing Withings OAuth tokens and monitoring system health.

These endpoints should be protected in production (e.g., API key, admin auth).
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query, BackgroundTasks
from pydantic import BaseModel

from app.services.token_refresh import (
    get_token_refresh_service,
    TokenRefreshResult,
    TokenRefreshStatus
)
from app.services.railway_client import (
    get_railway_client,
    RailwayUpdateStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# Request/Response Models
class TokenRefreshRequest(BaseModel):
    """Request model for token refresh."""
    refresh_token: Optional[str] = None  # If not provided, uses env var
    update_railway: bool = True  # Whether to update Railway env vars
    trigger_deployment: bool = False  # Whether to trigger Railway redeploy


class TokenRefreshResponse(BaseModel):
    """Response model for token refresh operations."""
    success: bool
    status: str
    message: str
    access_token_masked: Optional[str] = None
    refresh_token_masked: Optional[str] = None
    expires_at: Optional[str] = None
    next_refresh_recommended: Optional[str] = None
    railway_update_status: Optional[str] = None
    deployment_status: Optional[str] = None
    timestamp: str


class TokenStatusResponse(BaseModel):
    """Response model for token status check."""
    token_configured: bool
    expires_at: Optional[str] = None
    expires_in_hours: Optional[float] = None
    should_refresh: bool
    next_refresh_recommended: Optional[str] = None
    last_refreshed: Optional[str] = None
    authorization_url: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    status: str
    withings_configured: bool
    railway_configured: bool
    token_status: str
    uptime_seconds: float
    timestamp: str


# Startup time for uptime calculation
_startup_time = datetime.now(timezone.utc)


def _verify_admin_token(x_admin_token: Optional[str]) -> bool:
    """
    Verify the admin API token.
    
    In production, set ADMIN_API_TOKEN environment variable.
    If not set, admin endpoints are disabled for security.
    """
    expected_token = os.getenv("ADMIN_API_TOKEN")
    
    if not expected_token:
        # No admin token configured - check if we're in development
        if os.getenv("ENVIRONMENT", "production") == "development":
            return True
        return False
    
    return x_admin_token == expected_token


@router.get("/health", response_model=HealthCheckResponse)
async def admin_health_check():
    """
    Admin health check endpoint.
    
    Returns detailed health status including configuration status.
    """
    token_service = get_token_refresh_service()
    railway_client = get_railway_client()
    
    # Check Withings configuration
    withings_configured = bool(
        os.getenv("WITHINGS_CLIENT_ID") and 
        os.getenv("WITHINGS_CLIENT_SECRET")
    )
    
    # Check Railway configuration
    railway_configured = bool(
        os.getenv("RAILWAY_API_TOKEN") and
        os.getenv("RAILWAY_PROJECT_ID")
    )
    
    # Check token status
    access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
    if access_token:
        if token_service.should_refresh_now():
            token_status = "refresh_recommended"
        else:
            token_status = "valid"
    else:
        token_status = "not_configured"
    
    uptime = (datetime.now(timezone.utc) - _startup_time).total_seconds()
    
    return HealthCheckResponse(
        status="healthy",
        withings_configured=withings_configured,
        railway_configured=railway_configured,
        token_status=token_status,
        uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/token/status", response_model=TokenStatusResponse)
async def get_token_status(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Get current Withings token status.
    
    Returns information about token configuration and expiration.
    """
    if not _verify_admin_token(x_admin_token):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin token. Set X-Admin-Token header."
        )
    
    token_service = get_token_refresh_service()
    
    access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
    expires_at_str = os.getenv("WITHINGS_TOKEN_EXPIRES_AT")
    last_refreshed = os.getenv("WITHINGS_TOKEN_LAST_REFRESHED")
    
    expires_at = None
    expires_in_hours = None
    should_refresh = False
    next_refresh = None
    
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now(timezone.utc)
            expires_in_hours = (expires_at - now).total_seconds() / 3600
            should_refresh = token_service.should_refresh_now(expires_at)
            next_refresh = token_service.get_next_refresh_time(expires_at)
        except ValueError:
            pass
    
    return TokenStatusResponse(
        token_configured=bool(access_token),
        expires_at=expires_at_str,
        expires_in_hours=round(expires_in_hours, 2) if expires_in_hours else None,
        should_refresh=should_refresh,
        next_refresh_recommended=next_refresh.isoformat() if next_refresh else None,
        last_refreshed=last_refreshed,
        authorization_url=token_service.get_authorization_url() if not access_token else None
    )


@router.post("/token/refresh", response_model=TokenRefreshResponse)
async def refresh_tokens(
    request: TokenRefreshRequest,
    background_tasks: BackgroundTasks,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Manually trigger Withings token refresh.
    
    This endpoint:
    1. Refreshes the Withings access token using the refresh token
    2. Optionally updates Railway environment variables
    3. Optionally triggers a Railway deployment
    
    Headers:
        X-Admin-Token: Admin API token (required in production)
    
    Body:
        refresh_token: Optional custom refresh token (uses env var if not provided)
        update_railway: Whether to update Railway env vars (default: true)
        trigger_deployment: Whether to trigger Railway redeploy (default: false)
    """
    if not _verify_admin_token(x_admin_token):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin token. Set X-Admin-Token header."
        )
    
    token_service = get_token_refresh_service()
    railway_client = get_railway_client()
    
    logger.info("Manual token refresh initiated via admin endpoint")
    
    # Step 1: Refresh the token
    result = await token_service.refresh_token(request.refresh_token)
    
    response = TokenRefreshResponse(
        success=result.is_success,
        status=result.status.value,
        message="",
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    if not result.is_success:
        if result.requires_reauthorization:
            response.message = (
                "Refresh token is invalid or expired. "
                "User must re-authorize at: " + token_service.get_authorization_url()
            )
        else:
            response.message = f"Token refresh failed: {result.error_message}"
        return response
    
    # Token refresh successful
    response.access_token_masked = result.to_dict()["access_token"]
    response.refresh_token_masked = result.to_dict()["refresh_token"]
    response.expires_at = result.expires_at.isoformat() if result.expires_at else None
    response.next_refresh_recommended = token_service.get_next_refresh_time(
        result.expires_at
    ).isoformat() if result.expires_at else None
    
    # Step 2: Update Railway (if requested and configured)
    if request.update_railway:
        railway_result = await railway_client.update_environment_variables(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_at=result.expires_at
        )
        response.railway_update_status = railway_result.status.value
        
        if not railway_result.is_success:
            response.message = (
                f"Token refreshed but Railway update failed: {railway_result.error_message}. "
                "You may need to manually update Railway environment variables."
            )
            return response
        
        # Step 3: Trigger deployment (if requested)
        if request.trigger_deployment:
            deploy_result = await railway_client.trigger_deployment()
            response.deployment_status = deploy_result.status.value
    
    response.message = "Token refresh completed successfully"
    logger.info(f"Token refresh completed. Expires at: {response.expires_at}")
    
    return response


@router.get("/authorization-url")
async def get_authorization_url(
    state: Optional[str] = Query(None, description="Optional state parameter for CSRF protection"),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Get the Withings OAuth authorization URL.
    
    Use this URL when the user needs to (re-)authorize the application.
    After authorization, the user will be redirected to the callback URL
    with an authorization code.
    """
    if not _verify_admin_token(x_admin_token):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin token"
        )
    
    token_service = get_token_refresh_service()
    
    return {
        "authorization_url": token_service.get_authorization_url(state),
        "instructions": [
            "1. Open the authorization URL in a browser",
            "2. Log in to Withings and authorize the application",
            "3. You will be redirected to the callback URL with an authorization code",
            "4. The callback endpoint will exchange the code for tokens automatically"
        ]
    }


@router.post("/token/exchange")
async def exchange_authorization_code(
    code: str = Query(..., description="Authorization code from Withings OAuth redirect"),
    update_railway: bool = Query(True, description="Whether to update Railway env vars"),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Exchange an authorization code for access and refresh tokens.
    
    This endpoint is typically called after the user completes the OAuth flow
    and is redirected back with an authorization code.
    """
    if not _verify_admin_token(x_admin_token):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin token"
        )
    
    token_service = get_token_refresh_service()
    railway_client = get_railway_client()
    
    logger.info("Exchanging authorization code for tokens")
    
    result = await token_service.exchange_authorization_code(code)
    
    if not result.is_success:
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed: {result.error_message}"
        )
    
    response = {
        "success": True,
        "access_token_masked": result.to_dict()["access_token"],
        "refresh_token_masked": result.to_dict()["refresh_token"],
        "expires_at": result.expires_at.isoformat() if result.expires_at else None,
        "user_id": result.user_id
    }
    
    if update_railway:
        railway_result = await railway_client.update_environment_variables(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_at=result.expires_at
        )
        response["railway_update_status"] = railway_result.status.value
    
    logger.info(f"Authorization code exchanged successfully for user {result.user_id}")
    
    return response
