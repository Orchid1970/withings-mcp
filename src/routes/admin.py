"""
Admin Routes for Withings MCP
=============================
Administrative endpoints for token management and system status.
Protected by ADMIN_API_TOKEN.
"""

import os
import logging
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


def verify_admin_token(x_admin_token: str = Header(None)):
    """
    Verify the admin API token.
    """
    expected_token = os.getenv("ADMIN_API_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=503, detail="Admin API not configured (ADMIN_API_TOKEN not set)")
    if x_admin_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


async def persist_tokens_to_railway(access_token: str, refresh_token: str) -> dict:
    """
    Persist tokens to Railway environment variables.
    """
    railway_token = os.getenv("RAILWAY_API_TOKEN")
    project_id = os.getenv("RAILWAY_PROJECT_ID")
    service_id = os.getenv("RAILWAY_SERVICE_ID")
    environment_id = os.getenv("RAILWAY_ENVIRONMENT_ID")
    
    if not all([railway_token, project_id, service_id, environment_id]):
        missing = []
        if not railway_token: missing.append("RAILWAY_API_TOKEN")
        if not project_id: missing.append("RAILWAY_PROJECT_ID")
        if not service_id: missing.append("RAILWAY_SERVICE_ID")
        if not environment_id: missing.append("RAILWAY_ENVIRONMENT_ID")
        return {
            "persisted": False,
            "message": f"Missing Railway config: {', '.join(missing)}"
        }
    
    # GraphQL mutation to update variables
    mutation = """
    mutation($projectId: String!, $environmentId: String!, $serviceId: String!, $name: String!, $value: String!) {
      variableUpsert(input: {
        projectId: $projectId
        environmentId: $environmentId
        serviceId: $serviceId
        name: $name
        value: $value
      })
    }
    """
    
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # Update access token
        response = await client.post(
            "https://backboard.railway.app/graphql/v2",
            headers=headers,
            json={
                "query": mutation,
                "variables": {
                    "projectId": project_id,
                    "environmentId": environment_id,
                    "serviceId": service_id,
                    "name": "WITHINGS_ACCESS_TOKEN",
                    "value": access_token
                }
            }
        )
        
        if response.status_code != 200:
            return {
                "persisted": False,
                "message": f"Failed to persist access token: {response.text}"
            }
        
        # Update refresh token
        response = await client.post(
            "https://backboard.railway.app/graphql/v2",
            headers=headers,
            json={
                "query": mutation,
                "variables": {
                    "projectId": project_id,
                    "environmentId": environment_id,
                    "serviceId": service_id,
                    "name": "WITHINGS_REFRESH_TOKEN",
                    "value": refresh_token
                }
            }
        )
        
        if response.status_code != 200:
            return {
                "persisted": False,
                "message": f"Failed to persist refresh token: {response.text}"
            }
    
    return {"persisted": True, "message": "Tokens persisted to Railway"}


@router.post("/token/refresh")
async def refresh_token(x_admin_token: str = Header(None)):
    """
    Manually refresh the Withings OAuth token.
    Requires X-Admin-Token header.
    """
    verify_admin_token(x_admin_token)
    
    refresh_token_value = os.getenv("WITHINGS_REFRESH_TOKEN")
    client_id = os.getenv("WITHINGS_CLIENT_ID")
    client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
    
    if not refresh_token_value:
        raise HTTPException(status_code=400, detail="No refresh token available")
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Withings client credentials not configured")
    
    # Call Withings OAuth2 token refresh
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://wbsapi.withings.net/v2/oauth2",
            data={
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token_value
            }
        )
    
    data = response.json()
    
    if data.get("status") != 0:
        error_msg = data.get("error", "Unknown error")
        logger.error(f"Token refresh failed: {error_msg}")
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {error_msg}")
    
    body = data.get("body", {})
    new_access_token = body.get("access_token")
    new_refresh_token = body.get("refresh_token")
    expires_in = body.get("expires_in", 10800)
    
    if not new_access_token or not new_refresh_token:
        raise HTTPException(status_code=500, detail="Invalid token response from Withings")
    
    # Update environment variables in memory
    os.environ["WITHINGS_ACCESS_TOKEN"] = new_access_token
    os.environ["WITHINGS_REFRESH_TOKEN"] = new_refresh_token
    
    # Persist to Railway
    persist_result = await persist_tokens_to_railway(new_access_token, new_refresh_token)
    
    expires_at = datetime.now(timezone.utc).timestamp() + expires_in
    
    logger.info(f"Token refreshed successfully. Persisted: {persist_result.get('persisted')}")
    
    return {
        "success": True,
        "message": "Token refreshed successfully",
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
        "expires_in_seconds": expires_in,
        "persisted": persist_result.get("persisted", False),
        "persistence_message": persist_result.get("message")
    }


@router.get("/token/status")
async def token_status(x_admin_token: str = Header(None)):
    """
    Get current token status.
    Requires X-Admin-Token header.
    """
    verify_admin_token(x_admin_token)
    
    access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
    refresh_token_value = os.getenv("WITHINGS_REFRESH_TOKEN")
    
    return {
        "has_access_token": bool(access_token),
        "has_refresh_token": bool(refresh_token_value),
        "access_token_preview": f"{access_token[:20]}..." if access_token else None,
        "railway_configured": all([
            os.getenv("RAILWAY_API_TOKEN"),
            os.getenv("RAILWAY_PROJECT_ID"),
            os.getenv("RAILWAY_SERVICE_ID"),
            os.getenv("RAILWAY_ENVIRONMENT_ID")
        ])
    }


@router.get("/config")
async def get_config(x_admin_token: str = Header(None)):
    """
    Get current configuration status (no secrets).
    Requires X-Admin-Token header.
    """
    verify_admin_token(x_admin_token)
    
    return {
        "withings": {
            "client_id_set": bool(os.getenv("WITHINGS_CLIENT_ID")),
            "client_secret_set": bool(os.getenv("WITHINGS_CLIENT_SECRET")),
            "access_token_set": bool(os.getenv("WITHINGS_ACCESS_TOKEN")),
            "refresh_token_set": bool(os.getenv("WITHINGS_REFRESH_TOKEN"))
        },
        "railway": {
            "api_token_set": bool(os.getenv("RAILWAY_API_TOKEN")),
            "project_id": os.getenv("RAILWAY_PROJECT_ID"),
            "service_id": os.getenv("RAILWAY_SERVICE_ID"),
            "environment_id": os.getenv("RAILWAY_ENVIRONMENT_ID")
        },
        "admin": {
            "admin_token_set": bool(os.getenv("ADMIN_API_TOKEN"))
        },
        "scheduler": {
            "auto_refresh_enabled": os.getenv("AUTO_REFRESH_ENABLED", "true").lower() == "true",
            "refresh_interval_seconds": int(os.getenv("TOKEN_REFRESH_INTERVAL_SECONDS", "7200"))
        }
    }
