"""
PDF Parser Tool — FUTURE: Extract text and metadata from PDF files.
Currently returns mock data demonstrating expected output format.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="pdf_parser",
    description="Extract text, metadata, and structure from PDF documents. Supports tables, headers, and multi-page documents.",
    niche="files",
    status=ToolStatus.COMING_SOON,
    icon="file-text",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"file_url": "https://example.com/paper.pdf"},
            output='{"text": "Sample extracted text...", "pages": 5, "title": "Document"}',
            description="Parse a PDF document",
        ),
    ],
    input_schema={"file_url": "str"},
    output_schema={"text": "str", "pages": "int", "title": "str", "metadata": "dict"},
    avg_response_ms=3000,
))
@tool
async def pdf_parser(file_url: str) -> str:
    """Extract text and metadata from a PDF document. Currently returns mock data (coming soon)."""
    return json.dumps({
        "text": "Sample extracted text from the document. This demonstrates the expected output format for PDF parsing.",
        "pages": 5,
        "title": "Sample Document",
        "metadata": {"author": "Unknown", "created": "2026-01-01"},
        "note": "This tool is coming soon. Showing mock output.",
    })
