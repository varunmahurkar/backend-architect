"""
arXiv Source Integration
Searches and retrieves academic papers from arXiv.
Returns structured paper metadata including title, authors, abstract, and PDF URL.
fetch_full_text() downloads the PDF and extracts text via PyMuPDF (fitz) — used for deep research mode.
"""

import logging
import asyncio
from typing import List, Dict

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.debug("PyMuPDF not installed — full paper text extraction unavailable")


async def search_arxiv(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search arXiv for academic papers matching the query.

    Args:
        query: Search query string
        max_results: Maximum number of papers to return

    Returns:
        List of paper dictionaries with title, authors, summary, pdf_url, etc.
    """
    try:
        import arxiv
    except ImportError:
        logger.error("arxiv package not installed. Run: pip install arxiv")
        return []

    logger.info(f"Searching arXiv: '{query}' (max_results={max_results})")

    try:
        # Run the synchronous arxiv client in a thread pool
        results = await asyncio.to_thread(_sync_arxiv_search, query, max_results)
        logger.info(f"arXiv returned {len(results)} papers")
        return results

    except Exception as e:
        logger.error(f"arXiv search failed: {e}")
        return []


async def fetch_full_text(pdf_url: str, max_chars: int = 20_000) -> str:
    """Download an arXiv PDF and extract plain text (first max_chars characters).

    Uses PyMuPDF (fitz) for extraction. Falls back to a clear error message if
    the package is unavailable or the download fails.

    Args:
        pdf_url: Direct PDF URL (e.g. https://arxiv.org/pdf/2401.12345)
        max_chars: Maximum characters to return (default 20k ≈ ~3k tokens)

    Returns:
        Extracted text string, or error description.
    """
    if not FITZ_AVAILABLE:
        return "[Full text unavailable — install PyMuPDF: pip install PyMuPDF]"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(pdf_url, headers={"User-Agent": "Nurav-AI/1.0 (research)"})
            resp.raise_for_status()
            pdf_bytes = resp.content

        # Extract text in thread pool (CPU-bound)
        def _extract(data: bytes) -> str:
            doc = fitz.open(stream=data, filetype="pdf")
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text("text"))
            doc.close()
            return "\n".join(pages_text)

        text = await asyncio.to_thread(_extract, pdf_bytes)
        return text[:max_chars].strip()

    except Exception as exc:
        logger.error(f"fetch_full_text failed for {pdf_url}: {exc}")
        return f"[Full text extraction failed: {exc}]"


def _sync_arxiv_search(query: str, max_results: int) -> List[Dict]:
    """Synchronous arXiv search (runs in thread pool)."""
    import arxiv

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    results = []
    for paper in client.results(search):
        results.append({
            "title": paper.title,
            "authors": [author.name for author in paper.authors],
            "summary": paper.summary,
            "pdf_url": paper.pdf_url,
            "arxiv_id": paper.entry_id.split("/")[-1],
            "published": paper.published.isoformat() if paper.published else "",
            "categories": list(paper.categories) if paper.categories else [],
            "source": "arxiv",
        })

    return results
