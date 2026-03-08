"""
PDF Parser Tool — Extract text, metadata, and tables from PDF documents.
Primary: PyMuPDF (fitz). Fallback: pdfplumber (better for table-heavy PDFs).
"""

import json
import logging
import tempfile
import os
from typing import Any

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _download_pdf(file_url: str) -> bytes:
    """Download PDF from URL with timeout and validation."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(file_url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if resp.content[:4] != b"%PDF" and "pdf" not in content_type.lower():
            raise ValueError("URL does not point to a valid PDF file")

        return resp.content


def _extract_with_pymupdf(pdf_bytes: bytes, extract_tables: bool) -> dict[str, Any]:
    """Extract text and metadata using PyMuPDF (fitz)."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    metadata = doc.metadata or {}
    pages = []
    full_text_parts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        full_text_parts.append(text)

        page_data: dict[str, Any] = {
            "page_num": page_num + 1,
            "text": text,
        }

        if extract_tables:
            try:
                tables = page.find_tables()
                page_tables = []
                for table in tables:
                    extracted = table.extract()
                    if extracted:
                        page_tables.append(extracted)
                page_data["tables"] = page_tables
            except Exception:
                page_data["tables"] = []

        pages.append(page_data)

    doc.close()

    full_text = "\n\n".join(full_text_parts)

    return {
        "text": full_text,
        "pages": pages,
        "metadata": {
            "title": metadata.get("title", "") or "",
            "author": metadata.get("author", "") or "",
            "pages": len(pages),
            "created": metadata.get("creationDate", "") or "",
            "producer": metadata.get("producer", "") or "",
        },
        "total_chars": len(full_text),
        "method": "pymupdf",
    }


def _extract_with_pdfplumber(pdf_bytes: bytes, extract_tables: bool) -> dict[str, Any]:
    """Fallback extraction using pdfplumber (better for tables)."""
    import pdfplumber
    import io

    pages = []
    full_text_parts = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pdf_metadata = pdf.metadata or {}

        for page_num, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()
            full_text_parts.append(text)

            page_data: dict[str, Any] = {
                "page_num": page_num + 1,
                "text": text,
            }

            if extract_tables:
                try:
                    raw_tables = page.extract_tables() or []
                    page_data["tables"] = raw_tables
                except Exception:
                    page_data["tables"] = []

            pages.append(page_data)

    full_text = "\n\n".join(full_text_parts)

    return {
        "text": full_text,
        "pages": pages,
        "metadata": {
            "title": pdf_metadata.get("Title", "") or "",
            "author": pdf_metadata.get("Author", "") or "",
            "pages": len(pages),
            "created": pdf_metadata.get("CreationDate", "") or "",
            "producer": pdf_metadata.get("Producer", "") or "",
        },
        "total_chars": len(full_text),
        "method": "pdfplumber",
    }


@nurav_tool(metadata=ToolMetadata(
    name="pdf_parser",
    description="Extract text, metadata, and tables from PDF documents. Supports multi-page documents with automatic fallback for table-heavy PDFs.",
    niche="files",
    status=ToolStatus.ACTIVE,
    icon="file-text",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"file_url": "https://arxiv.org/pdf/1706.03762", "extract_tables": True},
            output='{"text": "Attention Is All You Need...", "pages": [...], "metadata": {"title": "...", "pages": 15}, "total_chars": 45000, "method": "pymupdf"}',
            description="Parse a PDF paper from arXiv",
        ),
    ],
    input_schema={"file_url": "str", "extract_tables": "bool (default true)"},
    output_schema={"text": "str", "pages": "array", "metadata": "dict", "total_chars": "int", "method": "str"},
    avg_response_ms=5000,
    success_rate=0.90,
))
@tool
async def pdf_parser(file_url: str, extract_tables: bool = True) -> str:
    """Extract text, metadata, and tables from a PDF document at the given URL."""
    try:
        pdf_bytes = await _download_pdf(file_url)
    except httpx.TimeoutException:
        return json.dumps({"error": "Timeout downloading PDF. The file may be too large or the server is slow."})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP error {e.response.status_code} downloading PDF."})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to download PDF: {str(e)}"})

    # Primary: PyMuPDF
    try:
        result = _extract_with_pymupdf(pdf_bytes, extract_tables)

        # If PyMuPDF got very little text, try pdfplumber as fallback
        if result["total_chars"] < 100 and len(pdf_bytes) > 1000:
            logger.info("PyMuPDF returned minimal text, falling back to pdfplumber")
            try:
                result = _extract_with_pdfplumber(pdf_bytes, extract_tables)
            except Exception:
                pass  # Keep PyMuPDF result if pdfplumber also fails

        return json.dumps(result, ensure_ascii=False, default=str)

    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e}, trying pdfplumber")

    # Fallback: pdfplumber
    try:
        result = _extract_with_pdfplumber(pdf_bytes, extract_tables)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": f"Failed to parse PDF with both engines: {str(e)}"})
