"""
Railway API Client for Environment Variable Management
=======================================================
Integrates with Railway's API to update environment variables
and trigger deployments after token refresh.

Reference: https://docs.railway.app/reference/public-api

Security Notes:
- Never log actual token values
- Use RAILWAY_API_TOKEN for authentication
- All API calls use HTTPS
"""

import os
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RailwayUpdateStatus(Enum):
    """Status codes for Railway operations."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"  # Some vars updated but not all
    AUTHENTICATION_ERROR = "authentication_error"
    PROJECT_NOT_FOUND = "project_not_found"
    SERVICE_NOT_FOUND = "service_not_found"
    API_ERROR = "api_error"
    CONFIGURATION_ERROR = "configuration_error"
    DEPLOYMENT_PENDING = "deployment_pending"
    DEPLOYMENT_FAILED = "deployment_failed"


@dataclass
class RailwayUpdateResult:
    """Result of a Railway update operation."""
    status: RailwayUpdateStatus
    variables_updated: List[str] = None
    deployment_id: Optional[str] = None
    deployment_url: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        if self.variables_updated is None:
            self.variables_updated = []
    
    @property
    def is_success(self) -> bool:
        return self.status in (RailwayUpdateStatus.SUCCESS, RailwayUpdateStatus.PARTIAL_SUCCESS)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "variables_updated": self.variables_updated,
            "deployment_id": self.deployment_id,
            "deployment_url": self.deployment_url,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat()
        }


class RailwayClient:
    """
    Client for Railway API operations.
    
    Handles:
    - Environment variable updates
    - Deployment triggers
    - Deployment status monitoring
    """
    
    RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"
    
    def __init__(
        self,
        api_token: Optional[str] = None,
        project_id: Optional[str] = None,
        service_id: Optional[str] = None,
        environment_id: Optional[str] = None
    ):
        """
        Initialize the Railway client.
        
        Args:
            api_token: Railway API token (defaults to RAILWAY_API_TOKEN env var)
            project_id: Railway project ID (defaults to RAILWAY_PROJECT_ID env var)
            service_id: Railway service ID (defaults to RAILWAY_SERVICE_ID env var)
            environment_id: Railway environment ID (defaults to RAILWAY_ENVIRONMENT_ID env var)
        """
        self.api_token = api_token or os.getenv("RAILWAY_API_TOKEN")
        self.project_id = project_id or os.getenv("RAILWAY_PROJECT_ID")
        self.service_id = service_id or os.getenv("RAILWAY_SERVICE_ID")
        self.environment_id = environment_id or os.getenv("RAILWAY_ENVIRONMENT_ID", "production")
        
        if not self.api_token:
            logger.warning("RAILWAY_API_TOKEN not configured - Railway updates will be skipped")
    
    def _validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate required configuration is present."""
        if not self.api_token:
            return False, "RAILWAY_API_TOKEN not configured"
        if not self.project_id:
            return False, "RAILWAY_PROJECT_ID not configured"
        if not self.service_id:
            return False, "RAILWAY_SERVICE_ID not configured"
        return True, None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Railway API requests."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    async def update_environment_variables(
        self,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        additional_vars: Optional[Dict[str, str]] = None
    ) -> RailwayUpdateResult:
        """
        Update Withings token environment variables in Railway.
        
        Updates:
        - WITHINGS_ACCESS_TOKEN
        - WITHINGS_REFRESH_TOKEN  
        - WITHINGS_TOKEN_EXPIRES_AT
        - WITHINGS_TOKEN_LAST_REFRESHED
        
        Args:
            access_token: New Withings access token
            refresh_token: New Withings refresh token
            expires_at: Token expiration datetime
            additional_vars: Optional additional variables to update
        
        Returns:
            RailwayUpdateResult with operation status
        """
        # Validate configuration
        is_valid, error_msg = self._validate_configuration()
        if not is_valid:
            logger.warning(f"Railway configuration incomplete: {error_msg}")
            return RailwayUpdateResult(
                status=RailwayUpdateStatus.CONFIGURATION_ERROR,
                error_message=error_msg
            )
        
        # Prepare variables to update
        variables = {
            "WITHINGS_ACCESS_TOKEN": access_token,
            "WITHINGS_REFRESH_TOKEN": refresh_token,
            "WITHINGS_TOKEN_EXPIRES_AT": expires_at.isoformat(),
            "WITHINGS_TOKEN_LAST_REFRESHED": datetime.now(timezone.utc).isoformat()
        }
        
        if additional_vars:
            variables.update(additional_vars)
        
        logger.info(f"Updating {len(variables)} environment variables in Railway")
        
        # GraphQL mutation for updating variables
        mutation = """
        mutation VariablesUpsert($input: VariableCollectionUpsertInput!) {
            variableCollectionUpsert(input: $input)
        }
        """
        
        # Format variables for Railway API
        variables_input = {key: value for key, value in variables.items()}
        
        payload = {
            "query": mutation,
            "variables": {
                "input": {
                    "projectId": self.project_id,
                    "serviceId": self.service_id,
                    "environmentId": self.environment_id,
                    "variables": variables_input
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.RAILWAY_API_URL,
                    json=payload,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
            
            if "errors" in data:
                error_messages = [e.get("message", "Unknown error") for e in data["errors"]]
                logger.error(f"Railway API errors: {error_messages}")
                return RailwayUpdateResult(
                    status=RailwayUpdateStatus.API_ERROR,
                    error_message="; ".join(error_messages)
                )
            
            logger.info("Railway environment variables updated successfully")
            
            # Variable names only (not values) for logging
            return RailwayUpdateResult(
                status=RailwayUpdateStatus.SUCCESS,
                variables_updated=list(variables.keys())
            )
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Railway API authentication failed")
                return RailwayUpdateResult(
                    status=RailwayUpdateStatus.AUTHENTICATION_ERROR,
                    error_message="Invalid or expired RAILWAY_API_TOKEN"
                )
            logger.error(f"Railway API HTTP error: {e.response.status_code}")
            return RailwayUpdateResult(
                status=RailwayUpdateStatus.API_ERROR,
                error_message=f"HTTP {e.response.status_code}"
            )
        except Exception as e:
            logger.exception("Unexpected error updating Railway variables")
            return RailwayUpdateResult(
                status=RailwayUpdateStatus.API_ERROR,
                error_message=str(e)
            )
    
    async def trigger_deployment(self) -> RailwayUpdateResult:
        """
        Trigger a new deployment on Railway to pick up environment variable changes.
        
        Note: Railway often auto-deploys when variables change, but this ensures
        the deployment happens immediately.
        
        Returns:
            RailwayUpdateResult with deployment information
        """
        is_valid, error_msg = self._validate_configuration()
        if not is_valid:
            return RailwayUpdateResult(
                status=RailwayUpdateStatus.CONFIGURATION_ERROR,
                error_message=error_msg
            )
        
        logger.info("Triggering Railway deployment")
        
        mutation = """
        mutation DeploymentTrigger($input: DeploymentTriggerInput!) {
            deploymentTrigger(input: $input) {
                id
                url
                status
            }
        }
        """
        
        payload = {
            "query": mutation,
            "variables": {
                "input": {
                    "projectId": self.project_id,
                    "serviceId": self.service_id,
                    "environmentId": self.environment_id
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.RAILWAY_API_URL,
                    json=payload,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
            
            if "errors" in data:
                error_messages = [e.get("message", "Unknown error") for e in data["errors"]]
                return RailwayUpdateResult(
                    status=RailwayUpdateStatus.API_ERROR,
                    error_message="; ".join(error_messages)
                )
            
            deployment = data.get("data", {}).get("deploymentTrigger", {})
            
            logger.info(f"Deployment triggered: {deployment.get('id')}")
            
            return RailwayUpdateResult(
                status=RailwayUpdateStatus.DEPLOYMENT_PENDING,
                deployment_id=deployment.get("id"),
                deployment_url=deployment.get("url")
            )
            
        except Exception as e:
            logger.exception("Error triggering Railway deployment")
            return RailwayUpdateResult(
                status=RailwayUpdateStatus.DEPLOYMENT_FAILED,
                error_message=str(e)
            )
    
    async def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        Get the status of a specific deployment.
        
        Args:
            deployment_id: The Railway deployment ID
        
        Returns:
            Dictionary with deployment status information
        """
        query = """
        query Deployment($id: String!) {
            deployment(id: $id) {
                id
                status
                createdAt
                url
            }
        }
        """
        
        payload = {
            "query": query,
            "variables": {"id": deployment_id}
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.RAILWAY_API_URL,
                    json=payload,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
            
            return data.get("data", {}).get("deployment", {})
            
        except Exception as e:
            logger.exception("Error fetching deployment status")
            return {"error": str(e)}


# Singleton instance
_railway_client: Optional[RailwayClient] = None


def get_railway_client() -> RailwayClient:
    """Get or create the Railway client singleton."""
    global _railway_client
    if _railway_client is None:
        _railway_client = RailwayClient()
    return _railway_client
