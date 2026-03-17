"""
GitHub Search Tool — Search GitHub repos, code, issues, and users.
Uses GitHub REST API v3 (unauthenticated: 60 req/hr, authenticated: 5000 req/hr).
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


async def _github_get(path: str, params: dict) -> dict:
    """Make a GitHub API request."""
    import httpx
    import os

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{GITHUB_API}{path}", params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


@nurav_tool(metadata=ToolMetadata(
    name="github_search",
    description="Search GitHub repositories, code, issues, and users. Returns repository metadata, code snippets, and issue details. Set GITHUB_TOKEN env var for higher rate limits (5000/hr vs 60/hr).",
    niche="integration",
    status=ToolStatus.ACTIVE,
    icon="github",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "langchain agents python", "search_type": "repositories", "max_results": 5},
            output='[{"name": "langchain", "stars": 85000, "url": "...", "description": "..."}]',
            description="Search for LangChain agent repos",
        ),
    ],
    input_schema={"query": "str", "search_type": "str ('repositories'|'code'|'issues'|'users')", "max_results": "int (default 10)", "language": "str (optional)", "sort": "str ('stars'|'updated'|'relevance')"},
    output_schema={"results": "array", "total_count": "int", "search_type": "str"},
    avg_response_ms=2000,
    success_rate=0.93,
))
@tool
async def github_search(query: str, search_type: str = "repositories", max_results: int = 10, language: str = "", sort: str = "stars") -> str:
    """Search GitHub repositories, code, issues, or users."""
    if not query.strip():
        return json.dumps({"error": "No search query provided."})

    max_results = max(1, min(30, max_results))
    search_type = search_type.lower().strip()

    try:
        q = query.strip()
        if language and search_type in ("repositories", "code"):
            q += f" language:{language}"

        params = {"q": q, "per_page": max_results}
        if sort != "relevance":
            params["sort"] = sort
            params["order"] = "desc"

        if search_type == "repositories":
            data = await _github_get("/search/repositories", params)
            results = [
                {
                    "name": r.get("full_name", ""),
                    "description": r.get("description", ""),
                    "stars": r.get("stargazers_count", 0),
                    "forks": r.get("forks_count", 0),
                    "language": r.get("language", ""),
                    "url": r.get("html_url", ""),
                    "topics": r.get("topics", [])[:5],
                    "updated_at": r.get("updated_at", ""),
                    "open_issues": r.get("open_issues_count", 0),
                    "license": (r.get("license") or {}).get("spdx_id", ""),
                }
                for r in data.get("items", [])
            ]

        elif search_type == "code":
            data = await _github_get("/search/code", params)
            results = [
                {
                    "name": r.get("name", ""),
                    "path": r.get("path", ""),
                    "repository": r.get("repository", {}).get("full_name", ""),
                    "url": r.get("html_url", ""),
                    "score": round(r.get("score", 0), 3),
                }
                for r in data.get("items", [])
            ]

        elif search_type == "issues":
            params["q"] = q  # Issues search doesn't use language filter same way
            data = await _github_get("/search/issues", params)
            results = [
                {
                    "title": r.get("title", ""),
                    "state": r.get("state", ""),
                    "url": r.get("html_url", ""),
                    "repository": r.get("repository_url", "").replace("https://api.github.com/repos/", ""),
                    "comments": r.get("comments", 0),
                    "created_at": r.get("created_at", ""),
                    "labels": [l.get("name", "") for l in r.get("labels", [])],
                    "type": "pull_request" if r.get("pull_request") else "issue",
                }
                for r in data.get("items", [])
            ]

        elif search_type == "users":
            data = await _github_get("/search/users", params)
            results = [
                {
                    "login": r.get("login", ""),
                    "url": r.get("html_url", ""),
                    "type": r.get("type", ""),
                    "avatar": r.get("avatar_url", ""),
                    "score": round(r.get("score", 0), 3),
                }
                for r in data.get("items", [])
            ]

        else:
            return json.dumps({"error": f"Unknown search_type: '{search_type}'. Use: repositories, code, issues, users"})

        return json.dumps({
            "results": results,
            "total_count": data.get("total_count", len(results)),
            "returned": len(results),
            "search_type": search_type,
            "query": query,
        })

    except Exception as e:
        msg = str(e)
        if "rate limit" in msg.lower() or "403" in msg:
            return json.dumps({"error": "GitHub API rate limit exceeded. Set GITHUB_TOKEN env var for 5000 req/hr.", "details": msg})
        return json.dumps({"error": f"GitHub search failed: {msg}"})
