"""
Railway API Client
===================
Client for updating Railway environment variables via GraphQL API.
"""

import os
import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)


class RailwayClient:
    """
    Client for Railway's GraphQL API.
    
    Used to update environment variables in production without redeployment.
    """
    
    RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"
    
    def __init__(self):
        self.api_token = os.getenv("RAILWAY_API_TOKEN")
        self.project_id = os.getenv("RAILWAY_PROJECT_ID")
        self.service_id = os.getenv("RAILWAY_SERVICE_ID")
        self.environment_id = os.getenv("RAILWAY_ENVIRONMENT_ID", "production")
        
    def _validate_config(self) -> bool:
        """Validate Railway configuration."""
        if not self.api_token:
            raise ValueError("RAILWAY_API_TOKEN not configured")
        if not self.project_id:
            raise ValueError("RAILWAY_PROJECT_ID not configured")
        if not self.service_id:
            raise ValueError("RAILWAY_SERVICE_ID not configured")
        return True
    
    async def update_variables(self, variables: Dict[str, str]) -> Dict[str, Any]:
        """
        Update multiple environment variables on Railway.
        
        Args:
            variables: Dict of variable names to values.
            
        Returns:
            Dict with success status and details.
        """
        self._validate_config()
        
        # Railway uses variableUpsert mutation
        results = []
        
        for name, value in variables.items():
            try:
                result = await self._upsert_variable(name, value)
                results.append({"name": name, "success": True})
            except Exception as e:
                logger.error(f"Failed to update {name}: {e}")
                results.append({"name": name, "success": False, "error": str(e)})
        
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "success": success_count == len(variables),
            "updated": success_count,
            "total": len(variables),
            "results": results
        }
    
    async def _upsert_variable(self, name: str, value: str) -> Dict[str, Any]:
        """
        Upsert a single environment variable.
        
        Args:
            name: Variable name.
            value: Variable value.
            
        Returns:
            API response.
        """
        mutation = """
        mutation VariableUpsert($input: VariableUpsertInput!) {
            variableUpsert(input: $input)
        }
        """
        
        variables = {
            "input": {
                "projectId": self.project_id,
                "serviceId": self.service_id,
                "environmentId": self.environment_id,
                "name": name,
                "value": value
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.RAILWAY_API_URL,
                json={"query": mutation, "variables": variables},
                headers=headers,
                timeout=30.0
            )
            
        data = response.json()
        
        if "errors" in data:
            raise Exception(f"Railway API error: {data['errors']}")
            
        logger.debug(f"Updated Railway variable: {name}")
        return data
    
    async def get_variables(self) -> Dict[str, Any]:
        """
        Get current environment variables from Railway.
        
        Returns:
            Dict of variable names (values are not exposed for security).
        """
        self._validate_config()
        
        query = """
        query GetVariables($projectId: String!, $serviceId: String!, $environmentId: String!) {
            variables(projectId: $projectId, serviceId: $serviceId, environmentId: $environmentId)
        }
        """
        
        variables = {
            "projectId": self.project_id,
            "serviceId": self.service_id,
            "environmentId": self.environment_id
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.RAILWAY_API_URL,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=30.0
            )
            
        data = response.json()
        
        if "errors" in data:
            raise Exception(f"Railway API error: {data['errors']}")
            
        return data.get("data", {}).get("variables", {})
