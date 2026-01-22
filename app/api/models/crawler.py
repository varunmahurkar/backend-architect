"""
Crawler models for web crawling with LLM citation support.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class CrawlerType(str, Enum):
    """Crawler engine type."""
    BEAUTIFULSOUP = "beautifulsoup"
    PLAYWRIGHT = "playwright"
    AUTO = "auto"


class TriggerMode(str, Enum):
    """How the crawl was triggered."""
    EXPLICIT_URLS = "explicit_urls"
    AUTO_SEARCH = "auto_search"


# === Citation Models ===

class Citation(BaseModel):
    """Single citation reference."""
    id: int = Field(..., description="Citation number (1, 2, 3...)")
    url: str = Field(..., description="Full URL of the cited page")
    root_url: str = Field(..., description="Root domain (e.g., https://example.com)")
    title: str = Field(..., description="Page title")
    snippet: Optional[str] = Field(None, description="Relevant text snippet from source")
    favicon_url: Optional[str] = Field(None, description="Site favicon URL")
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    crawler_type: CrawlerType = Field(default=CrawlerType.AUTO)


class CitationList(BaseModel):
    """Collection of citations for a response."""
    citations: List[Citation] = Field(default_factory=list)
    total_count: int = Field(default=0)


# === Crawled Content Models ===

class CrawledPage(BaseModel):
    """Single crawled page content."""
    url: str
    root_url: str
    title: Optional[str] = None
    content: str = Field(..., description="Extracted text content")
    html_snippet: Optional[str] = Field(None, description="Relevant HTML if needed")
    meta_description: Optional[str] = None
    crawl_time_ms: int = Field(default=0)
    crawler_used: CrawlerType = CrawlerType.AUTO
    error: Optional[str] = None


class CrawlResult(BaseModel):
    """Result of a crawl operation."""
    pages: List[CrawledPage] = Field(default_factory=list)
    total_pages: int = Field(default=0)
    successful_pages: int = Field(default=0)
    failed_pages: int = Field(default=0)
    total_crawl_time_ms: int = Field(default=0)


# === Request Models ===

class CrawlRequest(BaseModel):
    """Request to crawl specific URLs."""
    urls: List[str] = Field(..., min_length=1, max_length=10, description="URLs to crawl")
    crawler_type: CrawlerType = Field(default=CrawlerType.AUTO)
    extract_links: bool = Field(default=False, description="Also extract outbound links")
    max_depth: int = Field(default=1, ge=1, le=3, description="Max crawl depth")


class SearchAndCrawlRequest(BaseModel):
    """Request to search web and crawl results (Perplexity-style)."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    max_results: int = Field(default=5, ge=1, le=10, description="Max search results to crawl")
    crawler_type: CrawlerType = Field(default=CrawlerType.AUTO)
    search_engine: Literal["google", "duckduckgo", "brave"] = Field(default="duckduckgo")


class ChatMessage(BaseModel):
    """Chat message for history."""
    role: Literal["user", "assistant", "system"]
    content: str


class WebChatRequest(BaseModel):
    """Chat request with web crawling support."""
    message: str = Field(..., min_length=1, max_length=10000)
    provider: Optional[Literal["google", "openai", "anthropic"]] = "google"
    chat_history: Optional[List[ChatMessage]] = None
    system_prompt: Optional[str] = None
    stream: bool = False

    # Web crawling options
    web_search_enabled: bool = Field(default=False, description="Enable Perplexity-style search")
    urls: Optional[List[str]] = Field(None, max_length=10, description="Explicit URLs to crawl")
    crawler_type: CrawlerType = Field(default=CrawlerType.AUTO)
    include_citations: bool = Field(default=True)


# === Response Models ===

class CrawlResponse(BaseModel):
    """Response from a crawl operation."""
    success: bool
    result: Optional[CrawlResult] = None
    error: Optional[str] = None


class WebChatResponse(BaseModel):
    """Chat response with citations."""
    success: bool
    message: str = Field(..., description="LLM response with inline citation markers [1], [2]")
    provider: str
    model: Optional[str] = None

    # Citation data for frontend tab
    citations: CitationList = Field(default_factory=CitationList)
    trigger_mode: Optional[TriggerMode] = None
    search_query: Optional[str] = Field(None, description="Query used if auto-search was triggered")


class StreamChunk(BaseModel):
    """Streaming response chunk."""
    type: Literal["content", "citation", "done", "error"]
    content: Optional[str] = None
    citation: Optional[Citation] = None
    error: Optional[str] = None
