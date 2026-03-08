"""Export Document Tool — COMING SOON: Export content as PDF/DOCX/Markdown."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="export_document",
    description="Export AI responses, research results, or any content as formatted PDF, DOCX, Markdown, or HTML documents.",
    niche="integration",
    status=ToolStatus.COMING_SOON,
    icon="download",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"content": "# Research Summary\n\nKey findings...", "format": "pdf", "title": "Research Report"},
            output='{"file_bytes": "...", "filename": "research-report.pdf", "format": "pdf", "pages": 3}',
            description="Export markdown as PDF",
        ),
    ],
    input_schema={"content": "str (markdown)", "format": "str ('pdf'|'docx'|'md'|'html')", "title": "str (optional)", "template": "str ('report'|'paper'|'notes'|'minimal')"},
    output_schema={"file_bytes": "str (base64)", "filename": "str", "format": "str", "pages": "int"},
    avg_response_ms=5000,
))
@tool
async def export_document(content: str, format: str = "pdf", title: str = "", template: str = "report") -> str:
    """Export content as a document. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Document export is under development. Will use markdown + weasyprint/python-docx."})
