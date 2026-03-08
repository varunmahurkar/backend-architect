"""JSON Explorer Tool — COMING SOON: Navigate and query JSON data."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="json_explorer",
    description="Navigate, query, and transform JSON/API responses. Supports JSONPath queries, schema extraction, and flattening.",
    niche="data",
    status=ToolStatus.COMING_SOON,
    icon="braces",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"data": '{"users": [{"name": "Alice"}, {"name": "Bob"}]}', "query": "$.users[*].name"},
            output='{"result": ["Alice", "Bob"], "paths": ["$.users[0].name", "$.users[1].name"]}',
            description="Query JSON with JSONPath",
        ),
    ],
    input_schema={"data": "str (JSON)", "query": "str (JSONPath or natural language)", "operations": "str ('explore,flatten,schema,query')"},
    output_schema={"result": "any", "schema": "dict", "paths": "array", "flattened": "dict"},
    avg_response_ms=500,
))
@tool
async def json_explorer(data: str, query: str = "", operations: str = "explore") -> str:
    """Explore and query JSON data. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "JSON explorer is under development. Will use jsonpath-ng + genson for schema."})
