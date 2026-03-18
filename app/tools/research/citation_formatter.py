"""
Citation Formatter Tool — Format citations in APA, MLA, Chicago, Harvard, IEEE, BibTeX.
Uses CrossRef API for DOI-based metadata auto-fill.
"""

import json
import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

CROSSREF_API = "https://api.crossref.org/works"


async def _lookup_doi(doi: str) -> dict | None:
    """Look up metadata for a DOI via CrossRef API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{CROSSREF_API}/{doi}")
            if resp.status_code != 200:
                return None
            data = resp.json()
            msg = data.get("message", {})

            authors = []
            for a in msg.get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                authors.append({"first": given, "last": family})

            date_parts = msg.get("published-print", msg.get("published-online", {})).get("date-parts", [[]])
            year = date_parts[0][0] if date_parts and date_parts[0] else ""

            return {
                "title": msg.get("title", [""])[0],
                "authors": authors,
                "year": str(year),
                "journal": msg.get("container-title", [""])[0],
                "volume": msg.get("volume", ""),
                "issue": msg.get("issue", ""),
                "pages": msg.get("page", ""),
                "doi": doi,
                "url": msg.get("URL", ""),
                "publisher": msg.get("publisher", ""),
            }
    except Exception as e:
        logger.warning(f"CrossRef lookup failed for {doi}: {e}")
        return None


def _format_authors_apa(authors: list[dict]) -> str:
    """Format author names in APA style."""
    if not authors:
        return ""
    parts = []
    for a in authors[:7]:
        last = a.get("last", "")
        first = a.get("first", "")
        initials = ". ".join(c[0].upper() for c in first.split() if c) + "." if first else ""
        parts.append(f"{last}, {initials}")
    if len(authors) > 7:
        parts = parts[:6] + ["..."] + [parts[-1]]
    return ", ".join(parts[:-1]) + ", & " + parts[-1] if len(parts) > 1 else parts[0] if parts else ""


def _format_apa(ref: dict) -> str:
    """Format a single reference in APA 7th style."""
    authors = _format_authors_apa(ref.get("authors", []))
    year = ref.get("year", "n.d.")
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    pages = ref.get("pages", "")
    doi = ref.get("doi", "")

    citation = f"{authors} ({year}). {title}."
    if journal:
        citation += f" *{journal}*"
        if volume:
            citation += f", *{volume}*"
        if issue:
            citation += f"({issue})"
        if pages:
            citation += f", {pages}"
        citation += "."
    if doi:
        citation += f" https://doi.org/{doi}"
    return citation


def _format_mla(ref: dict) -> str:
    """Format in MLA 9th style."""
    authors = ref.get("authors", [])
    if not authors:
        author_str = ""
    elif len(authors) == 1:
        a = authors[0]
        author_str = f"{a.get('last', '')}, {a.get('first', '')}"
    elif len(authors) == 2:
        a1, a2 = authors[0], authors[1]
        author_str = f"{a1.get('last', '')}, {a1.get('first', '')}, and {a2.get('first', '')} {a2.get('last', '')}"
    else:
        a = authors[0]
        author_str = f"{a.get('last', '')}, {a.get('first', '')}, et al."

    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    year = ref.get("year", "")
    pages = ref.get("pages", "")

    citation = f'{author_str}. "{title}."'
    if journal:
        citation += f" *{journal}*"
        if volume:
            citation += f", vol. {volume}"
        if issue:
            citation += f", no. {issue}"
        if year:
            citation += f", {year}"
        if pages:
            citation += f", pp. {pages}"
        citation += "."
    return citation


def _format_chicago(ref: dict) -> str:
    """Format in Chicago style."""
    authors = ref.get("authors", [])
    if authors:
        a = authors[0]
        author_str = f"{a.get('last', '')}, {a.get('first', '')}"
        for a2 in authors[1:3]:
            author_str += f", and {a2.get('first', '')} {a2.get('last', '')}"
        if len(authors) > 3:
            author_str += ", et al."
    else:
        author_str = ""

    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    year = ref.get("year", "")
    pages = ref.get("pages", "")

    citation = f'{author_str}. "{title}."'
    if journal:
        citation += f" *{journal}* {volume}"
        if issue:
            citation += f", no. {issue}"
        if year:
            citation += f" ({year})"
        if pages:
            citation += f": {pages}"
        citation += "."
    return citation


def _format_bibtex(ref: dict) -> str:
    """Format as BibTeX entry."""
    authors = ref.get("authors", [])
    author_str = " and ".join(f"{a.get('last', '')}, {a.get('first', '')}" for a in authors)

    # Generate a key
    first_author = authors[0].get("last", "unknown") if authors else "unknown"
    year = ref.get("year", "0000")
    key = f"{first_author.lower()}{year}"

    lines = [f"@article{{{key},"]
    if ref.get("title"):
        lines.append(f'  title = {{{ref["title"]}}},')
    if author_str:
        lines.append(f"  author = {{{author_str}}},")
    if ref.get("journal"):
        lines.append(f'  journal = {{{ref["journal"]}}},')
    if ref.get("year"):
        lines.append(f'  year = {{{ref["year"]}}},')
    if ref.get("volume"):
        lines.append(f'  volume = {{{ref["volume"]}}},')
    if ref.get("issue"):
        lines.append(f'  number = {{{ref["issue"]}}},')
    if ref.get("pages"):
        lines.append(f'  pages = {{{ref["pages"]}}},')
    if ref.get("doi"):
        lines.append(f'  doi = {{{ref["doi"]}}},')
    lines.append("}")
    return "\n".join(lines)


def _format_ieee(ref: dict) -> str:
    """Format in IEEE style."""
    authors = ref.get("authors", [])
    author_parts = []
    for a in authors[:6]:
        first = a.get("first", "")
        initials = " ".join(c[0].upper() + "." for c in first.split() if c) if first else ""
        author_parts.append(f"{initials} {a.get('last', '')}")
    if len(authors) > 6:
        author_parts = author_parts[:5] + ["et al."]
    author_str = ", ".join(author_parts)

    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    pages = ref.get("pages", "")
    year = ref.get("year", "")

    citation = f'{author_str}, "{title},"'
    if journal:
        citation += f" *{journal}*"
        if volume:
            citation += f", vol. {volume}"
        if pages:
            citation += f", pp. {pages}"
        if year:
            citation += f", {year}"
        citation += "."
    return citation


FORMATTERS = {
    "apa": _format_apa,
    "mla": _format_mla,
    "chicago": _format_chicago,
    "bibtex": _format_bibtex,
    "ieee": _format_ieee,
}


@nurav_tool(metadata=ToolMetadata(
    name="citation_formatter",
    description="Format citations and bibliographies in APA 7th, MLA 9th, Chicago, IEEE, or BibTeX. Auto-fills metadata from DOI via CrossRef.",
    niche="research",
    status=ToolStatus.ACTIVE,
    icon="quote",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"references": '[{"title": "Attention Is All You Need", "authors": [{"first": "Ashish", "last": "Vaswani"}], "year": "2017", "journal": "NeurIPS"}]', "style": "apa"},
            output='{"formatted": ["Vaswani, A. (2017). Attention Is All You Need. *NeurIPS*."], "bibliography": "..."}',
            description="Format a paper citation in APA",
        ),
        ToolExample(
            input={"references": '[{"doi": "10.1038/s41586-021-03819-2"}]', "style": "bibtex"},
            output='{"formatted": ["@article{...}"], "bibliography": "..."}',
            description="Generate BibTeX from DOI",
        ),
    ],
    input_schema={"references": "str (JSON array of reference objects)", "style": "str (apa|mla|chicago|ieee|bibtex)", "doi_lookup": "bool (default true)"},
    output_schema={"formatted": "array", "bibliography": "str"},
    avg_response_ms=2000,
    success_rate=0.93,
))
@tool
async def citation_formatter(references: str, style: str = "apa", doi_lookup: bool = True) -> str:
    """Format citations in academic styles. Provide references as JSON array. Auto-fills metadata from DOI."""
    try:
        refs = json.loads(references)
        if not isinstance(refs, list):
            refs = [refs]
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON. Provide references as a JSON array of objects."})

    formatter = FORMATTERS.get(style.lower())
    if not formatter:
        return json.dumps({"error": f"Unsupported style '{style}'. Supported: apa, mla, chicago, ieee, bibtex"})

    # Auto-fill from DOI if needed
    enriched_refs = []
    for ref in refs:
        if doi_lookup and ref.get("doi") and not ref.get("title"):
            looked_up = await _lookup_doi(ref["doi"])
            if looked_up:
                ref = {**looked_up, **{k: v for k, v in ref.items() if v}}
        enriched_refs.append(ref)

    formatted = [formatter(ref) for ref in enriched_refs]
    bibliography = "\n\n".join(formatted)

    return json.dumps({
        "formatted": formatted,
        "bibliography": bibliography,
        "style": style,
        "count": len(formatted),
    }, ensure_ascii=False)
