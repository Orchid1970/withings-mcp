"""
Admin Routes for Token Management
==================================
Secured endpoints for Withings OAuth token refresh and status monitoring.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends

logger = logging.getLogger(__name__)

# Router WITHOUT prefix - routes define their own paths
router = APIRouter(tags=["admin"])

# Admin token for securing endpoints
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN")


def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin API token for secured endpoints."""
    if not ADMIN_API_TOKEN:
        logger.warning("ADMIN_API_TOKEN not configured - endpoints unsecured")
        return True
    
    if x_admin_token != ADMIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")
    return True


@router.get("/admin/health")
async def admin_health():
    """
    Admin health check endpoint (no auth required).
    """
    return {
        "status": "healthy",
        "module": "admin",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "secured": bool(ADMIN_API_TOKEN)
    }


@router.get("/admin/token/status")
async def get_token_status(authorized: bool = Depends(verify_admin_token)):
    """
    Get current Withings OAuth token status.
    """
    access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
    expires_at_str = os.getenv("WITHINGS_TOKEN_EXPIRES_AT")
    last_refreshed = os.getenv("WITHINGS_TOKEN_LAST_REFRESHED")
    
    if not access_token:
        return {
            "status": "not_configured",
            "token_exists": False,
            "is_expired": True
        }
    
    is_expired = False
    expires_in_hours = None
    
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            is_expired = expires_at < now
            if not is_expired:
                delta = expires_at - now
                expires_in_hours = round(delta.total_seconds() / 3600, 2)
        except ValueError as e:
            logger.error(f"Invalid expires_at format: {expires_at_str} - {e}")
    
    return {
        "status": "expired" if is_expired else "valid",
        "token_exists": True,
        "expires_at": expires_at_str,
        "last_refreshed": last_refreshed,
        "is_expired": is_expired,
        "expires_in_hours": expires_in_hours
    }


@router.post("/admin/token/refresh")
async def refresh_token(authorized: bool = Depends(verify_admin_token)):
    """
    Manually trigger Withings OAuth token refresh.
    """
    try:
        from app.services.token_refresh import TokenRefreshService
        
        service = TokenRefreshService()
        result = await service.refresh_token()
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Token refreshed successfully",
                "new_expires_at": result.get("expires_at")
            }
        else:
            return {
                "success": False,
                "message": result.get("error", "Unknown error during refresh")
            }
            
    except ImportError as e:
        logger.error(f"Token refresh service not available: {e}")
        return {"success": False, "message": "Token refresh service not available"}
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        return {"success": False, "message": str(e)}


@router.get("/admin/config")
async def get_config(authorized: bool = Depends(verify_admin_token)):
    """
    Get current configuration status (sanitized).
    """
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
            "service_id_configured": bool(os.getenv("RAILWAY_SERVICE_ID"))
        },
        "admin": {
            "admin_token_configured": bool(ADMIN_API_TOKEN)
        }
    }
