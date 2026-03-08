"""GitHub Search Tool — COMING SOON: Search GitHub repos, issues, code."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="github_search",
    description="Search GitHub repositories, issues, code, and users. Returns repository metadata, code snippets, and issue details.",
    niche="integration",
    status=ToolStatus.COMING_SOON,
    icon="github",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"query": "langchain agents", "search_type": "repositories", "max_results": 5},
            output='[{"name": "...", "stars": 1000, "url": "...", "description": "..."}]',
            description="Search for LangChain agent repos",
        ),
    ],
    input_schema={"query": "str", "search_type": "str ('repositories'|'code'|'issues'|'users')", "max_results": "int (default 10)", "language": "str (optional)", "sort": "str ('stars'|'updated'|'relevance')"},
    output_schema={"type": "array"},
    avg_response_ms=2000,
))
@tool
async def github_search(query: str, search_type: str = "repositories", max_results: int = 10, language: str = "", sort: str = "stars") -> str:
    """Search GitHub. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "GitHub search is under development. Will use GitHub REST API v3."})
