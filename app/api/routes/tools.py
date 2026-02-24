"""
Tools API routes — Serves the tool manifest for the frontend.
Provides endpoints to list, filter, and execute tools.
"""

import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any

from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolManifestResponse(BaseModel):
    tools: List[dict]
    total: int
    niches: List[str]


class ToolExecuteRequest(BaseModel):
    tool_name: str
    inputs: dict


class ToolExecuteResponse(BaseModel):
    tool_name: str
    result: str
    status: str


@router.get("", response_model=ToolManifestResponse)
async def get_all_tools():
    """Get the full tool manifest with all registered tools."""
    tools = tool_registry.get_all()
    niches = tool_registry.get_niches()
    return ToolManifestResponse(tools=tools, total=len(tools), niches=niches)


@router.get("/niches")
async def get_niches():
    """Get list of all tool niches."""
    return {"niches": tool_registry.get_niches()}


@router.get("/niche/{niche}", response_model=ToolManifestResponse)
async def get_tools_by_niche(niche: str):
    """Get tools filtered by niche."""
    tools = tool_registry.get_by_niche(niche)
    if not tools:
        raise HTTPException(status_code=404, detail=f"No tools found for niche '{niche}'")
    return ToolManifestResponse(
        tools=tools,
        total=len(tools),
        niches=[niche],
    )


@router.get("/tool/{tool_name}")
async def get_tool_detail(tool_name: str):
    """Get detailed info for a single tool."""
    tool_meta = tool_registry.get_tool(tool_name)
    if not tool_meta:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return tool_meta


@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest):
    """Execute a tool with given inputs. Returns the tool's string output."""
    tool_fn = tool_registry.get_tool_function(request.tool_name)
    if not tool_fn:
        raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")

    tool_meta = tool_registry.get_tool(request.tool_name)
    if tool_meta and tool_meta.get("status") == "coming_soon":
        logger.info(f"Executing coming_soon tool '{request.tool_name}' (mock data)")

    try:
        result = await tool_fn.ainvoke(request.inputs)
        return ToolExecuteResponse(
            tool_name=request.tool_name,
            result=str(result),
            status="success",
        )
    except Exception as e:
        logger.error(f"Tool execution failed for '{request.tool_name}': {e}")
        return ToolExecuteResponse(
            tool_name=request.tool_name,
            result=json.dumps({"error": str(e)}),
            status="error",
        )
