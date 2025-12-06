"""
Admin Routes
============
Administrative endpoints for token management and system health.

Secured by ADMIN_API_TOKEN environment variable.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Header

logger = logging.getLogger(__name__)

router = APIRouter()

# Admin token for securing endpoints
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN")


def verify_admin_token(x_admin_token: Optional[str] = Header(None)) -> bool:
    """
    Verify the admin token from request header.
    
    Args:
        x_admin_token: Token from X-Admin-Token header
        
    Returns:
        True if valid, raises HTTPException if invalid
    """
    if not ADMIN_API_TOKEN:
        # No token configured = endpoints are open (not recommended for production)
        logger.warning("ADMIN_API_TOKEN not configured - admin endpoints are unsecured")
        return True
    
    if not x_admin_token or x_admin_token != ADMIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")
    
    return True


@router.get("/admin/health")
async def admin_health():
    """
    Admin module health check.
    
    Returns:
        Health status of admin module
    """
    return {
        "status": "healthy",
        "module": "admin",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "secured": bool(ADMIN_API_TOKEN)
    }


@router.get("/admin/token/status")
async def get_token_status(x_admin_token: Optional[str] = Header(None)):
    """
    Get current Withings token status.
    
    Returns:
        Token validity, expiration time, and last refresh timestamp
    """
    verify_admin_token(x_admin_token)
    
    access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
    expires_at = os.getenv("WITHINGS_TOKEN_EXPIRES_AT")
    last_refreshed = os.getenv("WITHINGS_TOKEN_LAST_REFRESHED")
    
    # Calculate if token is expired
    is_expired = False
    expires_in_hours = None
    
    if expires_at:
        try:
            expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            is_expired = now > expiry_time
            if not is_expired:
                delta = expiry_time - now
                expires_in_hours = round(delta.total_seconds() / 3600, 2)
        except Exception as e:
            logger.error(f"Error parsing expiration time: {e}")
    
    return {
        "status": "valid" if access_token and not is_expired else "expired" if is_expired else "unknown",
        "token_exists": bool(access_token),
        "expires_at": expires_at,
        "last_refreshed": last_refreshed,
        "is_expired": is_expired,
        "expires_in_hours": expires_in_hours
    }


@router.post("/admin/token/refresh")
async def refresh_token(x_admin_token: Optional[str] = Header(None)):
    """
    Manually trigger token refresh.
    
    This endpoint:
    1. Calls Withings API to refresh the OAuth token
    2. Updates Railway environment variables with new tokens
    
    Returns:
        Refresh result with new expiration time
    """
    verify_admin_token(x_admin_token)
    
    try:
        from app.services.token_refresh import TokenRefreshService
        
        service = TokenRefreshService()
        result = await service.do_refresh()
        
        if result.get("success"):
            logger.info(f"Token refresh successful, expires at: {result.get('expires_at')}")
            return {
                "success": True,
                "message": "Token refreshed successfully",
                "expires_at": result.get("expires_at"),
                "expires_in_seconds": result.get("expires_in"),
                "persisted": result.get("persisted", False),
                "persistence_message": result.get("persistence_message")
            }
        else:
            logger.error(f"Token refresh failed: {result.get('error')}")
            return {
                "success": False,
                "message": result.get("error", "Unknown error during refresh")
            }
            
    except ImportError as e:
        logger.error(f"Token refresh service not available: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Token refresh service not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@router.get("/admin/scheduler/status")
async def get_scheduler_status(x_admin_token: Optional[str] = Header(None)):
    """
    Get automatic refresh scheduler status.
    
    Returns:
        Scheduler status information
    """
    verify_admin_token(x_admin_token)
    
    try:
        from app.services.scheduler import get_scheduler_status as get_status
        return get_status()
    except ImportError:
        return {"error": "Scheduler module not available"}


@router.get("/admin/config")
async def get_config(x_admin_token: Optional[str] = Header(None)):
    """
    Get current configuration status (without exposing secrets).
    
    Returns:
        Configuration status for debugging
    """
    verify_admin_token(x_admin_token)
    
    return {
        "withings": {
            "client_id_configured": bool(os.getenv("WITHINGS_CLIENT_ID")),
            "client_secret_configured": bool(os.getenv("WITHINGS_CLIENT_SECRET")),
            "access_token_configured": bool(os.getenv("WITHINGS_ACCESS_TOKEN")),
            "refresh_token_configured": bool(os.getenv("WITHINGS_REFRESH_TOKEN"))
        },
        "railway": {
            "api_token_configured": bool(os.getenv("RAILWAY_API_TOKEN")),
            "project_id_configured": bool(os.getenv("RAILWAY_PROJECT_ID")),
            "environment_id_configured": bool(os.getenv("RAILWAY_ENVIRONMENT_ID")),
            "service_id_configured": bool(os.getenv("RAILWAY_SERVICE_ID"))
        },
        "admin": {
            "admin_token_configured": bool(ADMIN_API_TOKEN)
        },
        "scheduler": {
            "auto_refresh_enabled": os.getenv("AUTO_REFRESH_ENABLED", "true").lower() == "true",
            "refresh_interval_seconds": int(os.getenv("TOKEN_REFRESH_INTERVAL_SECONDS", "7200"))
        }
    }
