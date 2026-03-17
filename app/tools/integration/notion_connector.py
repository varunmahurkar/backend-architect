"""
Notion Connector Tool — Read and search Notion pages and databases.
Requires NOTION_TOKEN env var (Notion Integration Token).
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


async def _notion_request(method: str, path: str, body: dict = None) -> dict:
    """Make an authenticated Notion API request."""
    import httpx
    import os

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise ValueError("NOTION_TOKEN environment variable not set. Create a Notion integration at https://www.notion.so/my-integrations")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        if method.upper() == "POST":
            resp = await client.post(f"{NOTION_API}{path}", headers=headers, json=body or {})
        else:
            resp = await client.get(f"{NOTION_API}{path}", headers=headers)
        resp.raise_for_status()
        return resp.json()


def _extract_page_text(page: dict) -> str:
    """Extract plain text from a Notion page object."""
    title = ""
    props = page.get("properties", {})
    for prop_name, prop_val in props.items():
        if prop_val.get("type") == "title":
            title_items = prop_val.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_items)
            break
    return title


def _extract_block_text(blocks: list) -> str:
    """Extract text from Notion blocks."""
    lines = []
    for block in blocks:
        bt = block.get("type", "")
        content = block.get(bt, {})
        rich_text = content.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rich_text)
        if text:
            if bt.startswith("heading"):
                level = bt[-1]
                lines.append(f"{'#' * int(level)} {text}")
            elif bt == "bulleted_list_item":
                lines.append(f"• {text}")
            elif bt == "numbered_list_item":
                lines.append(f"1. {text}")
            else:
                lines.append(text)
    return "\n".join(lines)


@nurav_tool(metadata=ToolMetadata(
    name="notion_connector",
    description="Read and search Notion pages, databases, and blocks. Requires NOTION_TOKEN env var (set up at notion.so/my-integrations). Supports page reading, database querying, and workspace search.",
    niche="integration",
    status=ToolStatus.ACTIVE,
    icon="book-copy",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"action": "search", "query": "project roadmap"},
            output='{"results": [{"title": "Q1 Roadmap", "url": "..."}], "total": 3}',
            description="Search Notion for project docs",
        ),
    ],
    input_schema={"action": "str ('search'|'read_page'|'list_databases')", "query": "str", "page_id": "str (optional)", "database_id": "str (optional)"},
    output_schema={"results": "array", "content": "str", "properties": "dict"},
    avg_response_ms=3000,
    success_rate=0.85,
))
@tool
async def notion_connector(action: str = "search", query: str = "", page_id: str = "", database_id: str = "") -> str:
    """Read and search Notion workspaces."""
    try:
        if action == "search":
            if not query.strip():
                return json.dumps({"error": "Provide a search query."})
            data = await _notion_request("POST", "/search", {
                "query": query,
                "page_size": 20,
            })
            results = []
            for obj in data.get("results", []):
                obj_type = obj.get("object", "")
                title = _extract_page_text(obj) if obj_type == "page" else obj.get("title", [{}])[0].get("plain_text", "") if obj.get("title") else ""
                results.append({
                    "id": obj.get("id", ""),
                    "type": obj_type,
                    "title": title,
                    "url": obj.get("url", ""),
                    "last_edited": obj.get("last_edited_time", ""),
                })
            return json.dumps({"results": results, "total": len(results), "query": query})

        elif action == "read_page":
            if not page_id.strip():
                return json.dumps({"error": "Provide a page_id."})
            page = await _notion_request("GET", f"/pages/{page_id.strip()}")
            title = _extract_page_text(page)

            # Get blocks
            blocks_data = await _notion_request("GET", f"/blocks/{page_id.strip()}/children")
            blocks = blocks_data.get("results", [])
            content = _extract_block_text(blocks)

            return json.dumps({
                "title": title,
                "content": content,
                "url": page.get("url", ""),
                "created_time": page.get("created_time", ""),
                "last_edited_time": page.get("last_edited_time", ""),
                "block_count": len(blocks),
            })

        elif action == "list_databases":
            data = await _notion_request("POST", "/search", {
                "filter": {"property": "object", "value": "database"},
                "page_size": 20,
            })
            dbs = []
            for db in data.get("results", []):
                title_items = db.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_items)
                dbs.append({
                    "id": db.get("id", ""),
                    "title": title,
                    "url": db.get("url", ""),
                    "last_edited": db.get("last_edited_time", ""),
                })
            return json.dumps({"databases": dbs, "total": len(dbs)})

        else:
            return json.dumps({"error": f"Unknown action: '{action}'. Use: search, read_page, list_databases"})

    except ValueError as e:
        return json.dumps({"error": str(e), "setup": "Create a Notion integration at https://www.notion.so/my-integrations and set NOTION_TOKEN"})
    except Exception as e:
        msg = str(e)
        if "401" in msg or "unauthorized" in msg.lower():
            return json.dumps({"error": "Notion authentication failed. Check your NOTION_TOKEN.", "details": msg})
        return json.dumps({"error": f"Notion request failed: {msg}"})
