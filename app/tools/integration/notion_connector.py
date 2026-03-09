"""Notion Connector Tool — COMING SOON: Read and search Notion pages."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="notion_connector",
    description="Read and search Notion pages, databases, and blocks. Import knowledge from Notion workspaces.",
    niche="integration",
    status=ToolStatus.COMING_SOON,
    icon="book-copy",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"action": "search", "query": "project roadmap"},
            output='{"results": [{"title": "Q1 Roadmap", "url": "..."}]}',
            description="Search Notion for project docs",
        ),
    ],
    input_schema={"action": "str ('search'|'read_page'|'read_database')", "query": "str", "page_id": "str (optional)", "database_id": "str (optional)"},
    output_schema={"results": "array", "content": "str", "properties": "dict"},
    avg_response_ms=3000,
))
@tool
async def notion_connector(action: str = "search", query: str = "", page_id: str = "", database_id: str = "") -> str:
    """Connect to Notion. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Notion connector is under development. Will use Notion API v1 with OAuth."})
