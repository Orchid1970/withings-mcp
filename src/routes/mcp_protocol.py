"""
MCP Protocol Handler for Simtheory.ai integration.
Implements JSON-RPC style MCP protocol for tool discovery and execution.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Any, Dict, Optional
import httpx
import os

router = APIRouter()

# Define available tools that Simtheory can discover
TOOLS = [
    {
        "name": "get_weight",
        "description": "Get Timothy's weight measurements from Withings scale. Returns weight in kg and lbs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history to retrieve (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_body_composition",
        "description": "Get Timothy's full body composition: weight, body fat %, muscle mass, hydration, bone mass, visceral fat, nerve health, vascular age.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_blood_pressure",
        "description": "Get Timothy's blood pressure readings: systolic, diastolic, and heart rate from Withings BPM Connect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_heart_rate",
        "description": "Get Timothy's heart rate measurements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_activity",
        "description": "Get Timothy's daily activity data: steps, distance, calories, active minutes, heart rate zones.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_spo2",
        "description": "Get Timothy's blood oxygen (SpO2) measurements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_sleep",
        "description": "Get Timothy's sleep data from Withings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_all_health_data",
        "description": "Get all of Timothy's health data at once: weight, body composition, blood pressure, activity, heart rate, SpO2, temperature, sleep.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30)",
                    "default": 30
                }
            },
            "required": []
        }
    }
]

# Map tool names to internal endpoints
TOOL_ENDPOINTS = {
    "get_weight": "/withings/weight",
    "get_body_composition": "/withings/body-composition",
    "get_blood_pressure": "/withings/blood-pressure",
    "get_heart_rate": "/withings/heart-rate",
    "get_activity": "/withings/activity",
    "get_spo2": "/withings/spo2",
    "get_sleep": "/withings/sleep",
    "get_all_health_data": "/withings/all"
}


async def call_internal_endpoint(endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call an internal API endpoint and return the result."""
    base_url = os.getenv("BASE_URL", "https://withings-mcp-production.up.railway.app")
    url = f"{base_url}{endpoint}"
    
    if params and "days" in params:
        url += f"?days={params['days']}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        return response.json()


@router.post("/")
@router.post("/mcp")
async def mcp_handler(request: Request):
    """
    MCP Protocol handler for JSON-RPC style requests.
    Handles: initialize, tools/list, tools/call
    """
    try:
        body = await request.json()
    except:
        body = {}
    
    method = body.get("method", "")
    params = body.get("params", {})
    request_id = body.get("id", 1)
    
    # Handle different MCP methods
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "withings-mcp",
                    "version": "1.0.0",
                    "description": "Timothy's Withings health data integration"
                }
            }
        })
    
    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": TOOLS
            }
        })
    
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        
        if tool_name not in TOOL_ENDPOINTS:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            })
        
        try:
            endpoint = TOOL_ENDPOINTS[tool_name]
            result = await call_internal_endpoint(endpoint, tool_args)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result)
                        }
                    ]
                }
            })
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error executing tool: {str(e)}"
                }
            })
    
    # Default response for unknown methods or GET requests
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "status": "ok",
            "service": "withings-mcp",
            "version": "1.0.0",
            "available_methods": ["initialize", "tools/list", "tools/call"]
        }
    })


@router.get("/")
@router.get("/mcp")
async def mcp_info():
    """GET endpoint for MCP info and health check."""
    return {
        "service": "withings-mcp",
        "version": "1.0.0",
        "protocol": "MCP JSON-RPC",
        "description": "Timothy's Withings health data integration for Simtheory.ai",
        "available_tools": [t["name"] for t in TOOLS],
        "endpoints": {
            "mcp_protocol": "POST /mcp",
            "tools_list": "POST /mcp with {\"method\": \"tools/list\"}",
            "tool_call": "POST /mcp with {\"method\": \"tools/call\", \"params\": {\"name\": \"tool_name\"}}"
        }
    }
