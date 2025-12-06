"""
Withings OAuth Token Refresh Service
=====================================
Handles automatic token refresh for Withings API integration.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class TokenRefreshService:
    """
    Service for refreshing Withings OAuth tokens.
    
    Handles the OAuth2 refresh flow and optionally updates
    Railway environment variables with new tokens.
    """
    
    WITHINGS_TOKEN_URL = "https://wbsapi.withings.com/v2/oauth2"
    
    def __init__(self):
        self.client_id = os.getenv("WITHINGS_CLIENT_ID")
        self.client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
        self.refresh_token = os.getenv("WITHINGS_REFRESH_TOKEN")
        
    def _validate_config(self) -> bool:
        """Validate required configuration exists."""
        if not self.client_id:
            raise ValueError("WITHINGS_CLIENT_ID not configured")
        if not self.client_secret:
            raise ValueError("WITHINGS_CLIENT_SECRET not configured")
        if not self.refresh_token:
            raise ValueError("WITHINGS_REFRESH_TOKEN not configured")
        return True
    
    async def refresh_token(self) -> Dict[str, Any]:
        """
        Refresh the Withings OAuth token.
        
        Returns:
            Dict with success status, new tokens, and expiration info.
        """
        try:
            self._validate_config()
            
            # Prepare refresh request
            data = {
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token
            }
            
            logger.info("Requesting token refresh from Withings API")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.WITHINGS_TOKEN_URL,
                    data=data,
                    timeout=30.0
                )
                
            response_data = response.json()
            
            if response_data.get("status") != 0:
                error_msg = f"Withings API error: {response_data}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            body = response_data.get("body", {})
            new_access_token = body.get("access_token")
            new_refresh_token = body.get("refresh_token")
            expires_in = body.get("expires_in", 10800)  # Default 3 hours
            
            if not new_access_token:
                return {"success": False, "error": "No access token in response"}
            
            # Calculate expiration time
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            expires_at_str = expires_at.isoformat() + "Z"
            
            # Update local environment (for current process)
            os.environ["WITHINGS_ACCESS_TOKEN"] = new_access_token
            if new_refresh_token:
                os.environ["WITHINGS_REFRESH_TOKEN"] = new_refresh_token
            os.environ["WITHINGS_TOKEN_EXPIRES_AT"] = expires_at_str
            os.environ["WITHINGS_TOKEN_LAST_REFRESHED"] = datetime.utcnow().isoformat() + "Z"
            
            logger.info(f"Token refreshed successfully, expires at {expires_at_str}")
            
            # Try to update Railway environment variables
            railway_updated = await self._update_railway_env(
                new_access_token,
                new_refresh_token,
                expires_at_str
            )
            
            return {
                "success": True,
                "expires_at": expires_at_str,
                "expires_in_seconds": expires_in,
                "railway_updated": railway_updated
            }
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_railway_env(self, access_token: str, refresh_token: Optional[str], expires_at: str) -> bool:
        """
        Update Railway environment variables with new tokens.
        
        Returns:
            True if Railway update succeeded, False otherwise.
        """
        try:
            from app.services.railway_client import RailwayClient
            
            client = RailwayClient()
            
            variables = {
                "WITHINGS_ACCESS_TOKEN": access_token,
                "WITHINGS_TOKEN_EXPIRES_AT": expires_at,
                "WITHINGS_TOKEN_LAST_REFRESHED": datetime.utcnow().isoformat() + "Z"
            }
            
            if refresh_token:
                variables["WITHINGS_REFRESH_TOKEN"] = refresh_token
            
            await client.update_variables(variables)
            logger.info("Railway environment variables updated")
            return True
            
        except ImportError:
            logger.warning("Railway client not available")
            return False
        except Exception as e:
            logger.error(f"Failed to update Railway env vars: {e}")
            return False
    
    def check_token_expiry(self) -> Dict[str, Any]:
        """
        Check if the current token is expired or expiring soon.
        
        Returns:
            Dict with expiry status and time until expiration.
        """
        expires_at_str = os.getenv("WITHINGS_TOKEN_EXPIRES_AT")
        
        if not expires_at_str:
            return {"status": "unknown", "needs_refresh": True}
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            now = datetime.utcnow()
            
            if expires_at < now:
                return {"status": "expired", "needs_refresh": True}
            
            time_until_expiry = expires_at - now
            hours_remaining = time_until_expiry.total_seconds() / 3600
            
            # Refresh if less than 24 hours remaining
            needs_refresh = hours_remaining < 24
            
            return {
                "status": "valid" if not needs_refresh else "expiring_soon",
                "needs_refresh": needs_refresh,
                "hours_remaining": round(hours_remaining, 2),
                "expires_at": expires_at_str
            }
            
        except ValueError as e:
            logger.error(f"Invalid expires_at format: {e}")
            return {"status": "invalid", "needs_refresh": True}
