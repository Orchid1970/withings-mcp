"""
Railway API Client
==================
Client for interacting with Railway's GraphQL API to update environment variables.
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RailwayClient:
    """
    Client for Railway GraphQL API.
    
    Used to update environment variables when tokens are refreshed.
    """
    
    RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"
    
    def __init__(self):
        self._api_token = os.getenv("RAILWAY_API_TOKEN")
        self._project_id = os.getenv("RAILWAY_PROJECT_ID")
        self._environment_id = os.getenv("RAILWAY_ENVIRONMENT_ID")
        self._service_id = os.getenv("RAILWAY_SERVICE_ID")
    
    def is_configured(self) -> bool:
        """
        Check if Railway client is properly configured.
        
        Returns:
            True if all required environment variables are set
        """
        return all([
            self._api_token,
            self._project_id,
            self._environment_id,
            self._service_id
        ])
    
    def get_missing_config(self) -> list:
        """
        Get list of missing configuration variables.
        
        Returns:
            List of missing variable names
        """
        missing = []
        if not self._api_token:
            missing.append("RAILWAY_API_TOKEN")
        if not self._project_id:
            missing.append("RAILWAY_PROJECT_ID")
        if not self._environment_id:
            missing.append("RAILWAY_ENVIRONMENT_ID")
        if not self._service_id:
            missing.append("RAILWAY_SERVICE_ID")
        return missing
    
    async def update_variables(self, variables: Dict[str, str]) -> Dict[str, Any]:
        """
        Update environment variables in Railway.
        
        Args:
            variables: Dict of variable names and values to update
            
        Returns:
            Dict with success status and any error details
        """
        if not self.is_configured():
            missing = self.get_missing_config()
            return {
                "success": False,
                "error": f"Railway client not configured. Missing: {', '.join(missing)}"
            }
        
        try:
            # Railway uses a GraphQL mutation to upsert variables
            mutation = """
            mutation VariablesUpsert($input: VariableCollectionUpsertInput!) {
                variableCollectionUpsert(input: $input)
            }
            """
            
            # Format variables for Railway API
            variables_input = {}
            for key, value in variables.items():
                if value is not None:
                    variables_input[key] = str(value)
            
            payload = {
                "query": mutation,
                "variables": {
                    "input": {
                        "projectId": self._project_id,
                        "environmentId": self._environment_id,
                        "serviceId": self._service_id,
                        "variables": variables_input
                    }
                }
            }
            
            headers = {
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.RAILWAY_API_URL,
                    json=payload,
                    headers=headers
                )
                
                response_data = response.json()
                
                if response.status_code == 200 and "errors" not in response_data:
                    logger.info(f"Successfully updated {len(variables_input)} Railway variables")
                    return {"success": True, "updated_count": len(variables_input)}
                else:
                    errors = response_data.get("errors", [])
                    error_msg = errors[0].get("message") if errors else "Unknown error"
                    logger.error(f"Railway API error: {error_msg}")
                    return {"success": False, "error": error_msg}
                    
        except httpx.TimeoutException:
            logger.error("Railway API timeout")
            return {"success": False, "error": "Railway API timeout"}
        except httpx.RequestError as e:
            logger.error(f"Railway API request error: {e}")
            return {"success": False, "error": f"Request error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error updating Railway variables: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_variables(self) -> Dict[str, Any]:
        """
        Get current environment variables from Railway.
        
        Returns:
            Dict with success status and variables or error
        """
        if not self.is_configured():
            missing = self.get_missing_config()
            return {
                "success": False,
                "error": f"Railway client not configured. Missing: {', '.join(missing)}"
            }
        
        try:
            query = """
            query Variables($projectId: String!, $environmentId: String!, $serviceId: String!) {
                variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId)
            }
            """
            
            payload = {
                "query": query,
                "variables": {
                    "projectId": self._project_id,
                    "environmentId": self._environment_id,
                    "serviceId": self._service_id
                }
            }
            
            headers = {
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.RAILWAY_API_URL,
                    json=payload,
                    headers=headers
                )
                
                response_data = response.json()
                
                if response.status_code == 200 and "errors" not in response_data:
                    variables = response_data.get("data", {}).get("variables", {})
                    return {"success": True, "variables": variables}
                else:
                    errors = response_data.get("errors", [])
                    error_msg = errors[0].get("message") if errors else "Unknown error"
                    return {"success": False, "error": error_msg}
                    
        except Exception as e:
            logger.error(f"Error getting Railway variables: {e}")
            return {"success": False, "error": str(e)}
