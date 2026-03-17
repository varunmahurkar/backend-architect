"""
Zotero Sync Tool — Import/export references from Zotero libraries.
Uses Zotero Web API v3. Requires ZOTERO_API_KEY and ZOTERO_USER_ID env vars.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

ZOTERO_API = "https://api.zotero.org"


async def _zotero_get(path: str, params: dict = None) -> dict | list:
    """Make an authenticated Zotero API request."""
    import httpx
    import os

    api_key = os.environ.get("ZOTERO_API_KEY")
    if not api_key:
        raise ValueError("ZOTERO_API_KEY environment variable not set. Get your key at https://www.zotero.org/settings/keys/new")

    headers = {
        "Zotero-API-Key": api_key,
        "Zotero-API-Version": "3",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{ZOTERO_API}{path}", headers=headers, params=params or {})
        resp.raise_for_status()
        return resp.json()


def _format_reference(item: dict) -> dict:
    """Format a Zotero item into a clean reference object."""
    data = item.get("data", {})
    creators = data.get("creators", [])
    authors = [
        f"{c.get('lastName', '')}, {c.get('firstName', '')}" if c.get("lastName") else c.get("name", "")
        for c in creators
        if c.get("creatorType") in ("author", "editor")
    ]
    return {
        "key": item.get("key", ""),
        "type": data.get("itemType", ""),
        "title": data.get("title", ""),
        "authors": authors[:5],
        "year": data.get("date", "")[:4] if data.get("date") else "",
        "journal": data.get("publicationTitle", "") or data.get("bookTitle", ""),
        "doi": data.get("DOI", ""),
        "url": data.get("url", ""),
        "abstract": data.get("abstractNote", "")[:300],
        "tags": [t.get("tag", "") for t in data.get("tags", [])[:10]],
        "collections": data.get("collections", []),
    }


@nurav_tool(metadata=ToolMetadata(
    name="zotero_sync",
    description="Import and search references from Zotero libraries. Requires ZOTERO_API_KEY and ZOTERO_USER_ID environment variables. Set them at zotero.org/settings/keys/new",
    niche="integration",
    status=ToolStatus.ACTIVE,
    icon="bookmark",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"action": "search", "query": "deep learning"},
            output='{"references": [{"title": "Deep Learning", "authors": ["LeCun, Yann"], "year": "2015"}], "total": 5}',
            description="Search Zotero library for deep learning papers",
        ),
    ],
    input_schema={"action": "str ('search'|'list'|'collections')", "query": "str (for search)", "library_type": "str ('user'|'group')", "collection": "str (optional collection key)"},
    output_schema={"references": "array", "total": "int", "synced": "bool"},
    avg_response_ms=3000,
    success_rate=0.87,
))
@tool
async def zotero_sync(action: str = "search", query: str = "", library_type: str = "user", collection: str = "") -> str:
    """Sync and search Zotero references."""
    import os

    user_id = os.environ.get("ZOTERO_USER_ID")
    if not user_id:
        return json.dumps({
            "error": "ZOTERO_USER_ID not set.",
            "setup": "Set ZOTERO_USER_ID (find it at zotero.org/settings/keys) and ZOTERO_API_KEY",
        })

    lib_prefix = f"users/{user_id}" if library_type == "user" else f"groups/{user_id}"

    try:
        if action == "search":
            if not query.strip():
                return json.dumps({"error": "Provide a search query."})
            params = {"q": query, "limit": 25, "include": "data"}
            items = await _zotero_get(f"/{lib_prefix}/items", params)
            if not isinstance(items, list):
                items = items.get("items", [])
            references = [_format_reference(item) for item in items if item.get("data", {}).get("itemType") != "attachment"]
            return json.dumps({"references": references, "total": len(references), "query": query, "synced": True})

        elif action == "list":
            params = {"limit": 50, "include": "data", "sort": "dateModified", "direction": "desc"}
            if collection:
                items = await _zotero_get(f"/{lib_prefix}/collections/{collection}/items", params)
            else:
                items = await _zotero_get(f"/{lib_prefix}/items/top", params)
            if not isinstance(items, list):
                items = items.get("items", [])
            references = [_format_reference(item) for item in items if item.get("data", {}).get("itemType") != "attachment"]
            return json.dumps({"references": references, "total": len(references), "synced": True})

        elif action == "collections":
            collections = await _zotero_get(f"/{lib_prefix}/collections")
            if not isinstance(collections, list):
                collections = []
            cols = [
                {
                    "key": c.get("key", ""),
                    "name": c.get("data", {}).get("name", ""),
                    "parent": c.get("data", {}).get("parentCollection", None),
                    "num_items": c.get("meta", {}).get("numItems", 0),
                }
                for c in collections
            ]
            return json.dumps({"collections": cols, "total": len(cols)})

        else:
            return json.dumps({"error": f"Unknown action: '{action}'. Use: search, list, collections"})

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        msg = str(e)
        if "403" in msg or "unauthorized" in msg.lower():
            return json.dumps({"error": "Zotero authentication failed. Check your ZOTERO_API_KEY."})
        return json.dumps({"error": f"Zotero request failed: {msg}"})
