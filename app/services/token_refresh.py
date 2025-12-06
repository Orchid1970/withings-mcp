"""
Withings OAuth Token Refresh Service
=====================================
Automated token refresh following Withings OAuth 2.0 specifications.

Reference: https://developer.withings.com/developer-guide/v3/integration-guide/dropship-cellular/get-access/access-and-refresh-tokens/

Key behaviors:
- Access tokens expire after ~14 days (1,209,600 seconds)
- Refresh tokens may rotate on each use (Withings recommendation)
- After ~6 months of inactivity, full re-authorization required
- All API calls must use HTTPS
"""

import os
import httpx
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TokenRefreshStatus(Enum):
    """Status codes for token refresh operations."""
    SUCCESS = "success"
    INVALID_REFRESH_TOKEN = "invalid_refresh_token"  # Status 26 - requires re-auth
    INVALID_GRANT = "invalid_grant"  # Status 29 - invalid authorization code
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"
    CONFIGURATION_ERROR = "configuration_error"


@dataclass
class TokenRefreshResult:
    """Result of a token refresh operation."""
    status: TokenRefreshStatus
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None
    user_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    @property
    def is_success(self) -> bool:
        return self.status == TokenRefreshStatus.SUCCESS
    
    @property
    def requires_reauthorization(self) -> bool:
        return self.status == TokenRefreshStatus.INVALID_REFRESH_TOKEN
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with masked tokens for logging."""
        return {
            "status": self.status.value,
            "access_token": self._mask_token(self.access_token),
            "refresh_token": self._mask_token(self.refresh_token),
            "expires_in": self.expires_in,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "user_id": self.user_id,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "requires_reauthorization": self.requires_reauthorization
        }
    
    @staticmethod
    def _mask_token(token: Optional[str]) -> Optional[str]:
        """Mask token for secure logging: token_*****xyz"""
        if not token or len(token) < 10:
            return "[MASKED]" if token else None
        return f"token_*****{token[-3:]}"


class WithingsTokenRefreshService:
    """
    Handles Withings OAuth 2.0 token refresh operations.
    
    This service implements the token refresh flow per Withings documentation:
    https://developer.withings.com/developer-guide/v3/integration-guide/dropship-cellular/get-access/access-and-refresh-tokens/
    """
    
    TOKEN_ENDPOINT = "https://wbsapi.withings.com/v2/oauth2"
    AUTHORIZATION_ENDPOINT = "https://account.withings.com/oauth2_user/authorize2"
    
    # Withings API status codes
    STATUS_SUCCESS = 0
    STATUS_INVALID_REFRESH_TOKEN = 26
    STATUS_INVALID_AUTHORIZATION_CODE = 29
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ):
        """
        Initialize the token refresh service.
        
        Args:
            client_id: Withings OAuth client ID (defaults to env var)
            client_secret: Withings OAuth client secret (defaults to env var)
            redirect_uri: OAuth redirect URI (defaults to env var)
        """
        self.client_id = client_id or os.getenv("WITHINGS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("WITHINGS_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv(
            "WITHINGS_REDIRECT_URI",
            "https://withings-mcp-production.up.railway.app/auth/callback"
        )
        
        if not self.client_id or not self.client_secret:
            logger.error("Missing Withings OAuth credentials in environment")
    
    def _validate_configuration(self) -> Tuple[bool, Optional[str]]:
        """Validate required configuration is present."""
        if not self.client_id:
            return False, "WITHINGS_CLIENT_ID not configured"
        if not self.client_secret:
            return False, "WITHINGS_CLIENT_SECRET not configured"
        return True, None
    
    async def refresh_token(self, refresh_token: Optional[str] = None) -> TokenRefreshResult:
        """
        Refresh the Withings access token using a refresh token.
        
        Per Withings documentation, the refresh token may be rotated on each use.
        Always store and use the new refresh token from the response.
        
        Args:
            refresh_token: The refresh token to use. Defaults to WITHINGS_REFRESH_TOKEN env var.
        
        Returns:
            TokenRefreshResult with new tokens or error information.
        """
        # Validate configuration
        is_valid, error_msg = self._validate_configuration()
        if not is_valid:
            logger.error(f"Configuration error: {error_msg}")
            return TokenRefreshResult(
                status=TokenRefreshStatus.CONFIGURATION_ERROR,
                error_message=error_msg
            )
        
        # Get refresh token
        refresh_token = refresh_token or os.getenv("WITHINGS_REFRESH_TOKEN")
        if not refresh_token:
            logger.error("No refresh token available")
            return TokenRefreshResult(
                status=TokenRefreshStatus.CONFIGURATION_ERROR,
                error_message="WITHINGS_REFRESH_TOKEN not configured"
            )
        
        logger.info(f"Initiating token refresh at {datetime.now(timezone.utc).isoformat()}")
        
        # Prepare request payload
        payload = {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.TOKEN_ENDPOINT,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                data = response.json()
            
            return self._parse_token_response(data)
            
        except httpx.TimeoutException:
            logger.error("Token refresh request timed out")
            return TokenRefreshResult(
                status=TokenRefreshStatus.NETWORK_ERROR,
                error_message="Request timed out after 30 seconds"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during token refresh: {e.response.status_code}")
            return TokenRefreshResult(
                status=TokenRefreshStatus.API_ERROR,
                error_message=f"HTTP {e.response.status_code}: {str(e)}"
            )
        except Exception as e:
            logger.exception("Unexpected error during token refresh")
            return TokenRefreshResult(
                status=TokenRefreshStatus.API_ERROR,
                error_message=str(e)
            )
    
    async def exchange_authorization_code(self, authorization_code: str) -> TokenRefreshResult:
        """
        Exchange an authorization code for access and refresh tokens.
        
        This is used after the user completes the OAuth flow and is redirected
        back to the callback URL with an authorization code.
        
        Args:
            authorization_code: The code received from Withings OAuth redirect.
        
        Returns:
            TokenRefreshResult with new tokens or error information.
        """
        is_valid, error_msg = self._validate_configuration()
        if not is_valid:
            return TokenRefreshResult(
                status=TokenRefreshStatus.CONFIGURATION_ERROR,
                error_message=error_msg
            )
        
        logger.info("Exchanging authorization code for tokens")
        
        payload = {
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "redirect_uri": self.redirect_uri
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.TOKEN_ENDPOINT,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                data = response.json()
            
            return self._parse_token_response(data)
            
        except Exception as e:
            logger.exception("Error exchanging authorization code")
            return TokenRefreshResult(
                status=TokenRefreshStatus.API_ERROR,
                error_message=str(e)
            )
    
    def _parse_token_response(self, data: Dict[str, Any]) -> TokenRefreshResult:
        """
        Parse the Withings token API response.
        
        Withings API returns status 0 for success, various codes for errors.
        """
        status = data.get("status", -1)
        
        if status == self.STATUS_SUCCESS:
            body = data.get("body", {})
            expires_in = body.get("expires_in", 1209600)  # Default 14 days
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            logger.info(
                f"Token refresh successful. "
                f"Expires at: {expires_at.isoformat()}"
            )
            
            return TokenRefreshResult(
                status=TokenRefreshStatus.SUCCESS,
                access_token=body.get("access_token"),
                refresh_token=body.get("refresh_token"),
                expires_in=expires_in,
                expires_at=expires_at,
                user_id=str(body.get("userid", ""))
            )
        
        elif status == self.STATUS_INVALID_REFRESH_TOKEN:
            logger.warning("Refresh token invalid - user re-authorization required")
            return TokenRefreshResult(
                status=TokenRefreshStatus.INVALID_REFRESH_TOKEN,
                error_message="Refresh token is invalid or expired. User must re-authorize the application."
            )
        
        elif status == self.STATUS_INVALID_AUTHORIZATION_CODE:
            logger.warning("Authorization code invalid")
            return TokenRefreshResult(
                status=TokenRefreshStatus.INVALID_GRANT,
                error_message="Authorization code is invalid or expired."
            )
        
        else:
            error_msg = data.get("error", f"Unknown error (status: {status})")
            logger.error(f"Token refresh failed: {error_msg}")
            return TokenRefreshResult(
                status=TokenRefreshStatus.API_ERROR,
                error_message=error_msg
            )
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate the Withings OAuth authorization URL.
        
        Use this when the user needs to (re-)authorize the application.
        
        Args:
            state: Optional state parameter for CSRF protection.
        
        Returns:
            The full authorization URL to redirect the user to.
        """
        from urllib.parse import urlencode
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user.metrics,user.activity,user.sleepevents",
            "state": state or "withings_oauth"
        }
        
        return f"{self.AUTHORIZATION_ENDPOINT}?{urlencode(params)}"
    
    def get_next_refresh_time(
        self,
        expires_at: Optional[datetime] = None,
        buffer_hours: int = 24
    ) -> datetime:
        """
        Calculate recommended next token refresh time.
        
        Recommends refreshing 24 hours before expiration by default.
        
        Args:
            expires_at: Token expiration time. Defaults to env var WITHINGS_TOKEN_EXPIRES_AT.
            buffer_hours: Hours before expiration to trigger refresh.
        
        Returns:
            Recommended refresh datetime.
        """
        if expires_at is None:
            expires_at_str = os.getenv("WITHINGS_TOKEN_EXPIRES_AT")
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
            else:
                # Default to 14 days from now if unknown
                expires_at = datetime.now(timezone.utc) + timedelta(days=14)
        
        return expires_at - timedelta(hours=buffer_hours)
    
    def should_refresh_now(
        self,
        expires_at: Optional[datetime] = None,
        buffer_hours: int = 24
    ) -> bool:
        """
        Check if token should be refreshed now.
        
        Returns True if current time is past the recommended refresh time.
        """
        next_refresh = self.get_next_refresh_time(expires_at, buffer_hours)
        return datetime.now(timezone.utc) >= next_refresh


# Singleton instance for application-wide use
_token_service: Optional[WithingsTokenRefreshService] = None


def get_token_refresh_service() -> WithingsTokenRefreshService:
    """Get or create the token refresh service singleton."""
    global _token_service
    if _token_service is None:
        _token_service = WithingsTokenRefreshService()
    return _token_service
