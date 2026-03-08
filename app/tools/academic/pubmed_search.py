"""
PubMed Search Tool — Search 37M+ biomedical papers via NCBI E-utilities API.
Free, no API key required (rate limit: 3 req/sec without key, 10 req/sec with key).
"""

import json
import logging
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


async def _search_pmids(query: str, max_results: int, sort: str) -> list[str]:
    """Search PubMed and return list of PMIDs."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": sort,
        "retmode": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(ESEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


async def _fetch_details(pmids: list[str]) -> list[dict]:
    """Fetch article details for given PMIDs."""
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(EFETCH_URL, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    articles = []

    for article_el in root.findall(".//PubmedArticle"):
        try:
            medline = article_el.find(".//MedlineCitation")
            pmid = medline.findtext("PMID", "")
            art = medline.find("Article")

            title = art.findtext("ArticleTitle", "") if art is not None else ""

            # Authors
            authors = []
            author_list = art.find("AuthorList") if art is not None else None
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last = author.findtext("LastName", "")
                    fore = author.findtext("ForeName", "")
                    if last:
                        authors.append(f"{fore} {last}".strip())

            # Abstract
            abstract_el = art.find("Abstract") if art is not None else None
            abstract = ""
            if abstract_el is not None:
                parts = [t.text or "" for t in abstract_el.findall("AbstractText")]
                abstract = " ".join(parts)

            # Journal
            journal_el = art.find("Journal") if art is not None else None
            journal = journal_el.findtext("Title", "") if journal_el is not None else ""

            # DOI
            doi = ""
            for id_el in article_el.findall(".//ArticleIdList/ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text or ""
                    break

            # MeSH terms
            mesh_terms = []
            for mesh in medline.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
                if mesh.text:
                    mesh_terms.append(mesh.text)

            # Published date
            pub_date_el = art.find(".//PubDate") if art is not None else None
            published = ""
            if pub_date_el is not None:
                year = pub_date_el.findtext("Year", "")
                month = pub_date_el.findtext("Month", "")
                published = f"{year} {month}".strip()

            articles.append({
                "pmid": pmid,
                "title": title,
                "authors": authors[:10],
                "abstract": abstract[:2000],
                "journal": journal,
                "doi": doi,
                "mesh_terms": mesh_terms[:10],
                "published": published,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        except Exception as e:
            logger.warning(f"Failed to parse PubMed article: {e}")
            continue

    return articles


@nurav_tool(metadata=ToolMetadata(
    name="pubmed_search",
    description="Search PubMed's 37M+ biomedical and life science papers. Returns titles, abstracts, authors, MeSH terms, and DOIs.",
    niche="academic",
    status=ToolStatus.ACTIVE,
    icon="heart-pulse",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "CRISPR gene therapy cancer", "max_results": 3},
            output='[{"pmid": "...", "title": "...", "authors": [...], "abstract": "...", "journal": "...", "doi": "..."}]',
            description="Search for CRISPR cancer therapy papers",
        ),
    ],
    input_schema={"query": "str", "max_results": "int (default 5)", "sort": "str ('relevance' | 'date')"},
    output_schema={"type": "array", "items": {"pmid": "str", "title": "str", "authors": "array", "abstract": "str", "journal": "str", "doi": "str"}},
    avg_response_ms=3000,
    success_rate=0.93,
))
@tool
async def pubmed_search(query: str, max_results: int = 5, sort: str = "relevance") -> str:
    """Search PubMed for biomedical papers. Returns JSON array of paper metadata with abstracts."""
    try:
        pmids = await _search_pmids(query, max_results, sort)
        if not pmids:
            return json.dumps({"results": [], "message": f"No PubMed articles found for '{query}'."})
        articles = await _fetch_details(pmids)
        return json.dumps(articles, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"PubMed search failed: {str(e)}"})
