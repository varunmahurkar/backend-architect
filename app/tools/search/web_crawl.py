"""
Web Crawl Tool — Wraps crawler_service.crawl_urls() and search_and_crawl()
Crawls web pages and extracts content using smart crawler selection.
"""

import json
from typing import Optional
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="web_crawl",
    description="Crawl web pages to extract their full content. Supports both static and JavaScript-heavy sites with auto-detection.",
    niche="search",
    status=ToolStatus.ACTIVE,
    icon="globe",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "machine learning tutorial"},
            output='{"pages": [{"url": "...", "title": "...", "content": "..."}], "successful_pages": 3}',
            description="Search and crawl pages about ML tutorials",
        ),
    ],
    input_schema={"query": "str (optional)", "urls": "str - comma-separated URLs (optional)"},
    output_schema={"pages": "array", "successful_pages": "int", "total_pages": "int"},
    avg_response_ms=8000,
    success_rate=0.85,
))
@tool
async def web_crawl(query: str = "", urls: str = "") -> str:
    """Crawl web pages for content. Provide either a search query or comma-separated URLs to crawl."""
    from app.services.crawler_service import crawl_urls, search_and_crawl
    from app.api.models.crawler import CrawlerType

    if urls:
        url_list = [u.strip() for u in urls.split(",") if u.strip()]
        result = await crawl_urls(url_list, CrawlerType.AUTO)
    elif query:
        result, _ = await search_and_crawl(query=query, max_results=5, crawler_type=CrawlerType.AUTO)
    else:
        return json.dumps({"error": "Provide either 'query' or 'urls' parameter"})

    pages = []
    for page in result.pages:
        pages.append({
            "url": page.url,
            "title": page.title,
            "content": page.content[:3000] if page.content else "",
            "error": page.error,
        })

    return json.dumps({
        "pages": pages,
        "total_pages": result.total_pages,
        "successful_pages": result.successful_pages,
        "failed_pages": result.failed_pages,
        "total_crawl_time_ms": result.total_crawl_time_ms,
    }, ensure_ascii=False)
