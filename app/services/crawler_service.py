"""
Crawler service for web crawling with smart crawler selection.
Uses Crawlee with BeautifulSoup (static) and Playwright (JS) crawlers.
"""

import asyncio
import re
import time
from datetime import timedelta
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.api.models.crawler import (
    CrawlerType,
    CrawledPage,
    CrawlResult,
    Citation,
)
from app.config.settings import settings


# === Smart Crawler Selection ===

# Domains known to require JavaScript rendering
JS_HEAVY_DOMAINS = {
    "twitter.com", "x.com",
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "reddit.com",
    "medium.com",
    "substack.com",
    "notion.so",
    "figma.com",
    "miro.com",
    "airtable.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "discord.com",
    "slack.com",
    "trello.com",
    "canva.com",
}

# File extensions that indicate static content
STATIC_EXTENSIONS = {".html", ".htm", ".txt", ".md", ".xml", ".json", ".pdf"}


async def detect_crawler_type(url: str) -> CrawlerType:
    """
    Detect whether a URL needs BeautifulSoup (static) or Playwright (JS).

    Detection strategy:
    1. Check known JS-heavy domains
    2. Check file extension
    3. Probe URL with GET request and check for JS framework markers
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    # Check known JS-heavy domains
    if any(js_domain in domain for js_domain in JS_HEAVY_DOMAINS):
        return CrawlerType.PLAYWRIGHT

    # Check file extension
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in STATIC_EXTENSIONS):
        return CrawlerType.BEAUTIFULSOUP

    # Probe the URL
    try:
        async with httpx.AsyncClient(
            timeout=5.0,
            headers={"User-Agent": settings.crawler_user_agent},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            content_type = response.headers.get("content-type", "")

            # If not HTML, use BeautifulSoup
            if "text/html" not in content_type:
                return CrawlerType.BEAUTIFULSOUP

            html_sample = response.text[:15000]  # First 15KB
            html_lower = html_sample.lower()

            # Check for SPA framework markers
            js_markers = [
                "react", "__react",
                "angular", "ng-app", "ng-controller",
                "vue", "v-app", "v-cloak",
                "__next_data__", "__nuxt__",
                "window.__initial_state__",
                "data-reactroot", "data-reactid",
                "_app", "hydrate",
            ]

            if any(marker in html_lower for marker in js_markers):
                return CrawlerType.PLAYWRIGHT

            # Check if body is mostly empty (common for SPAs)
            body_match = re.search(
                r"<body[^>]*>(.*?)</body>",
                html_sample,
                re.DOTALL | re.IGNORECASE
            )
            if body_match:
                body_content = body_match.group(1).strip()
                # Remove scripts and styles
                body_text = re.sub(
                    r"<script[^>]*>.*?</script>",
                    "",
                    body_content,
                    flags=re.DOTALL | re.IGNORECASE
                )
                body_text = re.sub(
                    r"<style[^>]*>.*?</style>",
                    "",
                    body_text,
                    flags=re.DOTALL | re.IGNORECASE
                )
                body_text = re.sub(r"<[^>]+>", "", body_text).strip()

                if len(body_text) < 100:  # Mostly empty body = likely SPA
                    return CrawlerType.PLAYWRIGHT

    except Exception:
        pass  # On error, default to BeautifulSoup

    return CrawlerType.BEAUTIFULSOUP


def extract_root_url(url: str) -> str:
    """Extract root domain from URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


# === BeautifulSoup Crawler ===

async def crawl_with_beautifulsoup(urls: List[str]) -> List[CrawledPage]:
    """Crawl URLs using BeautifulSoup (for static HTML)."""
    from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

    results: List[CrawledPage] = []
    errors: List[str] = []

    crawler = BeautifulSoupCrawler(
        max_requests_per_crawl=len(urls),
        request_handler_timeout=timedelta(seconds=settings.crawler_timeout),
    )

    @crawler.router.default_handler
    async def handler(context: BeautifulSoupCrawlingContext) -> None:
        start_time = time.time()
        soup = context.soup

        try:
            # Extract title
            title = None
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            # Extract meta description
            meta_desc = None
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = str(meta_tag["content"])

            # Try og:description if no meta description
            if not meta_desc:
                og_tag = soup.find("meta", attrs={"property": "og:description"})
                if og_tag and og_tag.get("content"):
                    meta_desc = str(og_tag["content"])

            # Extract main content (prioritize main/article tags)
            main_content = (
                soup.find("main") or
                soup.find("article") or
                soup.find(attrs={"role": "main"}) or
                soup.find("body")
            )

            # Remove unwanted elements
            if main_content:
                for tag in main_content.find_all([
                    "script", "style", "nav", "footer", "header",
                    "aside", "noscript", "iframe", "form"
                ]):
                    tag.decompose()
                content = main_content.get_text(separator="\n", strip=True)
            else:
                content = soup.get_text(separator="\n", strip=True)

            # Clean up content - remove excessive whitespace
            content = re.sub(r'\n\s*\n', '\n\n', content)
            content = content[:settings.crawler_max_content_length]

            crawl_time = int((time.time() - start_time) * 1000)

            page = CrawledPage(
                url=context.request.url,
                root_url=extract_root_url(context.request.url),
                title=title,
                content=content,
                meta_description=meta_desc,
                crawl_time_ms=crawl_time,
                crawler_used=CrawlerType.BEAUTIFULSOUP,
            )
            results.append(page)

        except Exception as e:
            errors.append(f"{context.request.url}: {str(e)}")

    await crawler.run(urls)
    return results


# === Playwright Crawler ===

async def crawl_with_playwright(urls: List[str]) -> List[CrawledPage]:
    """Crawl URLs using Playwright (for JavaScript-heavy sites)."""
    from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

    results: List[CrawledPage] = []

    crawler = PlaywrightCrawler(
        max_requests_per_crawl=len(urls),
        request_handler_timeout=timedelta(seconds=settings.crawler_timeout + 15),
        browser_type=settings.playwright_browser,
        headless=settings.playwright_headless,
    )

    @crawler.router.default_handler
    async def handler(context: PlaywrightCrawlingContext) -> None:
        start_time = time.time()
        page = context.page

        try:
            # Wait for content to load
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Extract title
            title = await page.title()

            # Extract meta description via JS
            meta_desc = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[name="description"]') ||
                                document.querySelector('meta[property="og:description"]');
                    return meta ? meta.content : null;
                }
            """)

            # Extract main content via JS
            content = await page.evaluate("""
                () => {
                    const main = document.querySelector('main') ||
                                document.querySelector('article') ||
                                document.querySelector('[role="main"]') ||
                                document.body;

                    if (!main) return '';

                    // Clone to avoid modifying the page
                    const clone = main.cloneNode(true);

                    // Remove unwanted elements
                    const removeSelectors = [
                        'script', 'style', 'nav', 'footer', 'header',
                        'aside', 'noscript', 'iframe', 'form', '[role="navigation"]',
                        '[role="banner"]', '[role="contentinfo"]'
                    ];
                    removeSelectors.forEach(sel => {
                        clone.querySelectorAll(sel).forEach(el => el.remove());
                    });

                    return clone.innerText || clone.textContent || '';
                }
            """)

            # Clean up content
            content = re.sub(r'\n\s*\n', '\n\n', content or "")
            content = content[:settings.crawler_max_content_length]

            crawl_time = int((time.time() - start_time) * 1000)

            crawled_page = CrawledPage(
                url=context.request.url,
                root_url=extract_root_url(context.request.url),
                title=title,
                content=content,
                meta_description=meta_desc,
                crawl_time_ms=crawl_time,
                crawler_used=CrawlerType.PLAYWRIGHT,
            )
            results.append(crawled_page)

        except Exception as e:
            # Add page with error
            crawled_page = CrawledPage(
                url=context.request.url,
                root_url=extract_root_url(context.request.url),
                title=None,
                content="",
                error=str(e),
                crawler_used=CrawlerType.PLAYWRIGHT,
            )
            results.append(crawled_page)

    await crawler.run(urls)
    return results


# === Main Crawl Function ===

async def crawl_urls(
    urls: List[str],
    crawler_type: CrawlerType = CrawlerType.AUTO,
) -> CrawlResult:
    """
    Crawl a list of URLs with smart crawler selection.

    Args:
        urls: List of URLs to crawl
        crawler_type: Crawler to use (AUTO detects per URL)

    Returns:
        CrawlResult with crawled pages
    """
    start_time = time.time()
    all_pages: List[CrawledPage] = []

    if crawler_type == CrawlerType.AUTO:
        # Group URLs by detected crawler type
        bs_urls: List[str] = []
        pw_urls: List[str] = []

        detection_tasks = [detect_crawler_type(url) for url in urls]
        detected_types = await asyncio.gather(*detection_tasks)

        for url, detected in zip(urls, detected_types):
            if detected == CrawlerType.PLAYWRIGHT:
                pw_urls.append(url)
            else:
                bs_urls.append(url)

        # Crawl in parallel
        tasks = []
        if bs_urls:
            tasks.append(crawl_with_beautifulsoup(bs_urls))
        if pw_urls:
            tasks.append(crawl_with_playwright(pw_urls))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    pass  # Log error but continue
                else:
                    all_pages.extend(result)

    elif crawler_type == CrawlerType.BEAUTIFULSOUP:
        all_pages = await crawl_with_beautifulsoup(urls)

    elif crawler_type == CrawlerType.PLAYWRIGHT:
        all_pages = await crawl_with_playwright(urls)

    total_time = int((time.time() - start_time) * 1000)

    # Count successful vs failed
    successful = sum(1 for p in all_pages if not p.error and p.content)
    failed = len(urls) - successful

    return CrawlResult(
        pages=all_pages,
        total_pages=len(urls),
        successful_pages=successful,
        failed_pages=failed,
        total_crawl_time_ms=total_time,
    )


# === Web Search ===

async def search_web(
    query: str,
    max_results: int = 5,
    search_engine: str = "duckduckgo",
) -> List[str]:
    """
    Search the web and return URLs for crawling.

    Args:
        query: Search query
        max_results: Maximum number of results
        search_engine: Which search engine to use

    Returns:
        List of URLs to crawl
    """
    if search_engine == "duckduckgo":
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [r["href"] for r in results if r.get("href")]

    raise ValueError(f"Search engine '{search_engine}' not implemented")


async def search_and_crawl(
    query: str,
    max_results: int = 5,
    crawler_type: CrawlerType = CrawlerType.AUTO,
    search_engine: str = "duckduckgo",
) -> Tuple[CrawlResult, List[str]]:
    """
    Search web for query and crawl top results.

    Returns:
        Tuple of (CrawlResult, search_urls)
    """
    urls = await search_web(query, max_results, search_engine)
    if not urls:
        return CrawlResult(
            pages=[],
            total_pages=0,
            successful_pages=0,
            failed_pages=0,
            total_crawl_time_ms=0,
        ), []

    result = await crawl_urls(urls, crawler_type)
    return result, urls


# === Citation Generation ===

def generate_citations(pages: List[CrawledPage]) -> List[Citation]:
    """Generate citation objects from crawled pages."""
    citations = []
    for idx, page in enumerate(pages, start=1):
        if page.error or not page.content:
            continue  # Skip failed pages

        # Create snippet from meta description or content
        snippet = page.meta_description
        if not snippet and page.content:
            snippet = page.content[:200].strip()
            if len(page.content) > 200:
                snippet += "..."

        citation = Citation(
            id=idx,
            url=page.url,
            root_url=page.root_url,
            title=page.title or f"Source {idx}",
            snippet=snippet,
            favicon_url=f"{page.root_url}/favicon.ico",
            crawler_type=page.crawler_used,
        )
        citations.append(citation)

    return citations


def extract_domain(url: str) -> str:
    """Extract clean domain from URL (e.g., 'openai.com' from 'https://www.openai.com/path')."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def build_context_for_llm(pages: List[CrawledPage], citations: List[Citation]) -> str:
    """
    Build context string for LLM prompt with source attribution.

    Format includes domain for citation markers:
    [Source: example.com - Title]
    URL: https://example.com/page
    Content...

    The LLM should cite using 【example.com】 format.
    """
    context_parts = []

    # Create a mapping of URL to citation ID
    url_to_citation = {c.url: c for c in citations}

    for page in pages:
        if page.error or not page.content:
            continue

        citation = url_to_citation.get(page.url)
        if not citation:
            continue

        # Extract domain for citation marker
        domain = extract_domain(page.url)

        # Truncate content per source
        content = page.content[:settings.crawler_content_per_source]
        if len(page.content) > settings.crawler_content_per_source:
            content += "\n[Content truncated...]"

        # Include domain prominently so LLM can use it for 【domain】 citations
        context_parts.append(f"[Source: {domain} - {citation.title}]")
        context_parts.append(f"Domain for citation: {domain}")
        context_parts.append(f"Full URL: {page.url}")
        context_parts.append(content)
        context_parts.append("")  # Empty line separator

    return "\n".join(context_parts)
