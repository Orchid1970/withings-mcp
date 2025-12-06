"""
Token Refresh Service
=====================
Handles Withings OAuth token refresh and Railway environment variable updates.
"""

import os
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TokenRefreshService:
    """
    Service for refreshing Withings OAuth tokens.
    
    Handles:
    - Calling Withings OAuth API to refresh tokens
    - Updating Railway environment variables with new tokens
    - Tracking token expiration
    """
    
    WITHINGS_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
    
    def __init__(self):
        self.client_id = os.getenv("WITHINGS_CLIENT_ID")
        self.client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
        self.refresh_token = os.getenv("WITHINGS_REFRESH_TOKEN")
        
    def _validate_config(self) -> Optional[str]:
        """Validate required configuration. Returns error message if invalid."""
        if not self.client_id:
            return "WITHINGS_CLIENT_ID not configured"
        if not self.client_secret:
            return "WITHINGS_CLIENT_SECRET not configured"
        if not self.refresh_token:
            return "WITHINGS_REFRESH_TOKEN not configured"
        return None
    
    async def refresh_token_from_withings(self) -> Dict[str, Any]:
        """
        Call Withings API to refresh the OAuth token.
        
        Returns:
            Dict with success status and token data or error message
        """
        validation_error = self._validate_config()
        if validation_error:
            return {"success": False, "error": validation_error}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.WITHINGS_TOKEN_URL,
                    data={
                        "action": "requesttoken",
                        "grant_type": "refresh_token",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self.refresh_token
                    }
                )
                
                response_data = response.json()
                logger.info(f"Withings API response status: {response_data.get('status')}")
                
                # Withings returns status 0 for success
                if response_data.get("status") == 0:
                    body = response_data.get("body", {})
                    
                    # Calculate expiration time
                    expires_in = body.get("expires_in", 10800)  # Default 3 hours
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    
                    return {
                        "success": True,
                        "access_token": body.get("access_token"),
                        "refresh_token": body.get("refresh_token"),
                        "expires_in": expires_in,
                        "expires_at": expires_at.isoformat(),
                        "token_type": body.get("token_type", "Bearer"),
                        "scope": body.get("scope"),
                        "userid": body.get("userid")
                    }
                else:
                    error_msg = f"Withings API error: status={response_data.get('status')}, error={response_data.get('error')}"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                    
        except httpx.TimeoutException:
            logger.error("Withings API timeout")
            return {"success": False, "error": "Withings API timeout"}
        except httpx.RequestError as e:
            logger.error(f"Withings API request error: {e}")
            return {"success": False, "error": f"Request error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_railway_variables(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update Railway environment variables with new token data.
        
        Args:
            token_data: Dict containing access_token, refresh_token, expires_at
            
        Returns:
            Dict with success status
        """
        try:
            from app.services.railway_client import RailwayClient
            
            railway_client = RailwayClient()
            
            if not railway_client.is_configured():
                logger.warning("Railway client not configured - tokens not persisted")
                return {
                    "success": True,
                    "persisted": False,
                    "message": "Tokens refreshed but Railway not configured for persistence"
                }
            
            # Update environment variables
            variables_to_update = {
                "WITHINGS_ACCESS_TOKEN": token_data.get("access_token"),
                "WITHINGS_REFRESH_TOKEN": token_data.get("refresh_token"),
                "WITHINGS_TOKEN_EXPIRES_AT": token_data.get("expires_at"),
                "WITHINGS_TOKEN_LAST_REFRESHED": datetime.now(timezone.utc).isoformat()
            }
            
            result = await railway_client.update_variables(variables_to_update)
            
            if result.get("success"):
                logger.info("Railway environment variables updated successfully")
                return {"success": True, "persisted": True}
            else:
                logger.error(f"Failed to update Railway variables: {result.get('error')}")
                return {
                    "success": True,
                    "persisted": False,
                    "message": f"Tokens refreshed but failed to persist: {result.get('error')}"
                }
                
        except ImportError as e:
            logger.error(f"Railway client not available: {e}")
            return {
                "success": True,
                "persisted": False,
                "message": "Railway client not available"
            }
        except Exception as e:
            logger.error(f"Error updating Railway variables: {e}")
            return {
                "success": True,
                "persisted": False,
                "message": str(e)
            }
    
    async def refresh_token(self) -> Dict[str, Any]:
        """
        Main method to refresh token and update Railway.
        
        Returns:
            Dict with success status, new expiration, and persistence status
        """
        logger.info("Starting token refresh process...")
        
        # Step 1: Refresh token from Withings
        token_result = await self.refresh_token_from_withings()
        
        if not token_result.get("success"):
            return token_result
        
        logger.info(f"Token refreshed successfully, expires at: {token_result.get('expires_at')}")
        
        # Step 2: Update Railway environment variables
        railway_result = await self.update_railway_variables(token_result)
        
        return {
            "success": True,
            "expires_at": token_result.get("expires_at"),
            "expires_in": token_result.get("expires_in"),
            "persisted": railway_result.get("persisted", False),
            "persistence_message": railway_result.get("message")
        }
