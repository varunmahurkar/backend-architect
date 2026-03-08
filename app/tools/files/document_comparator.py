"""Document Comparator Tool — COMING SOON: Compare documents and highlight differences."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="document_comparator",
    description="Compare two documents and highlight differences. Supports text, PDF, and DOCX formats. Shows additions, deletions, and modifications.",
    niche="files",
    status=ToolStatus.COMING_SOON,
    icon="diff",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"document_a": "Original text here", "document_b": "Modified text here", "granularity": "word"},
            output='{"similarity_score": 0.85, "changes": [...], "summary": "3 additions, 2 deletions"}',
            description="Compare two text documents",
        ),
    ],
    input_schema={"document_a": "str", "document_b": "str", "format": "str ('text'|'pdf'|'docx')", "granularity": "str ('word'|'line'|'paragraph')"},
    output_schema={"similarity_score": "float", "changes": "array", "summary": "str"},
    avg_response_ms=2000,
))
@tool
async def document_comparator(document_a: str, document_b: str, format: str = "text", granularity: str = "line") -> str:
    """Compare two documents. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Document comparator is under development. Will use difflib + LLM for semantic diff."})
