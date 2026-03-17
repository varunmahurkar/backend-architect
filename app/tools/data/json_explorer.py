"""
JSON Explorer Tool — Navigate, query, and transform JSON data.
Supports JSONPath queries, schema extraction, flattening, and natural language queries.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _extract_schema(obj, path: str = "$") -> dict:
    """Recursively extract JSON schema."""
    if isinstance(obj, dict):
        return {
            "type": "object",
            "path": path,
            "keys": {k: _extract_schema(v, f"{path}.{k}") for k in list(obj.keys())[:20]},
        }
    elif isinstance(obj, list):
        item_schema = _extract_schema(obj[0], f"{path}[0]") if obj else {"type": "unknown"}
        return {"type": "array", "path": path, "length": len(obj), "item_type": item_schema}
    else:
        return {"type": type(obj).__name__, "path": path}


def _flatten(obj, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten a nested JSON object."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, (dict, list)):
                items.update(_flatten(v, new_key, sep))
            else:
                items[new_key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):  # Limit array expansion
            new_key = f"{parent_key}[{i}]"
            if isinstance(v, (dict, list)):
                items.update(_flatten(v, new_key, sep))
            else:
                items[new_key] = v
    else:
        items[parent_key] = obj
    return items


def _jsonpath_query(obj, path: str) -> tuple[list, list]:
    """Simple JSONPath implementation."""
    # Parse simple JSONPath expressions
    results = []
    paths = []

    def search(current, parts, current_path):
        if not parts:
            results.append(current)
            paths.append(current_path)
            return

        part = parts[0]
        rest = parts[1:]

        if part == "$":
            search(current, rest, "$")
        elif part == "*":
            if isinstance(current, dict):
                for k, v in current.items():
                    search(v, rest, f"{current_path}.{k}")
            elif isinstance(current, list):
                for i, v in enumerate(current):
                    search(v, rest, f"{current_path}[{i}]")
        elif part.startswith("[") and part.endswith("]"):
            idx_str = part[1:-1]
            if idx_str == "*":
                if isinstance(current, list):
                    for i, v in enumerate(current):
                        search(v, rest, f"{current_path}[{i}]")
            else:
                try:
                    idx = int(idx_str)
                    if isinstance(current, list) and 0 <= idx < len(current):
                        search(current[idx], rest, f"{current_path}[{idx}]")
                except ValueError:
                    pass
        elif isinstance(current, dict) and part in current:
            search(current[part], rest, f"{current_path}.{part}")

    # Tokenize path
    import re
    tokens = re.split(r'\.(?![^\[]*\])', path)
    flat_tokens = []
    for token in tokens:
        # Split array accesses
        parts2 = re.split(r'(\[.*?\])', token)
        for p in parts2:
            if p:
                flat_tokens.append(p)

    search(obj, flat_tokens, "")
    return results, paths


@nurav_tool(metadata=ToolMetadata(
    name="json_explorer",
    description="Navigate, query, and transform JSON data. Supports JSONPath queries, schema extraction, key path listing, and flattening of nested structures.",
    niche="data",
    status=ToolStatus.ACTIVE,
    icon="braces",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"data": '{"users": [{"name": "Alice"}, {"name": "Bob"}]}', "query": "$.users[*].name"},
            output='{"result": ["Alice", "Bob"], "paths": ["$.users[0].name", "$.users[1].name"], "count": 2}',
            description="Query JSON with JSONPath",
        ),
    ],
    input_schema={"data": "str (JSON)", "query": "str (JSONPath, e.g. $.users[*].name)", "operations": "str ('explore'|'flatten'|'schema'|'query')"},
    output_schema={"result": "any", "schema": "dict", "paths": "array", "flattened": "dict"},
    avg_response_ms=400,
    success_rate=0.97,
))
@tool
async def json_explorer(data: str, query: str = "", operations: str = "explore") -> str:
    """Explore and query JSON data."""
    if not data.strip():
        return json.dumps({"error": "No JSON data provided."})

    try:
        # Parse JSON
        if data.strip().startswith("http"):
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(data.strip())
                resp.raise_for_status()
                obj = resp.json()
        else:
            obj = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Failed to load data: {str(e)}"})

    ops = [o.strip() for o in operations.lower().split(",")]
    result = {}

    # Always include basic info
    result["type"] = type(obj).__name__
    if isinstance(obj, list):
        result["length"] = len(obj)
    elif isinstance(obj, dict):
        result["keys"] = list(obj.keys())[:50]
        result["key_count"] = len(obj)

    # JSONPath query
    if query.strip():
        try:
            matches, match_paths = _jsonpath_query(obj, query.strip())
            result["result"] = matches
            result["paths"] = match_paths
            result["count"] = len(matches)
        except Exception as e:
            result["query_error"] = str(e)

    # Schema extraction
    if "schema" in ops or "explore" in ops:
        result["schema"] = _extract_schema(obj)

    # Flatten
    if "flatten" in ops:
        flattened = _flatten(obj)
        result["flattened"] = {k: v for k, v in list(flattened.items())[:200]}
        result["flattened_keys"] = len(flattened)

    # All key paths
    if "explore" in ops:
        flat = _flatten(obj)
        result["all_paths"] = list(flat.keys())[:100]

    return json.dumps(result, default=str)
