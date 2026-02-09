"""
arXiv Source Integration
Searches and retrieves academic papers from arXiv.
Returns structured paper metadata including title, authors, abstract, and PDF URL.
"""

import logging
import asyncio
from typing import List, Dict

logger = logging.getLogger(__name__)


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
