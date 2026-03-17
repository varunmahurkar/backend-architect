"""
Document Comparator Tool — Compare documents and highlight differences.
Uses difflib for structural diff + LLM for semantic summary.
"""

import json
import logging
import difflib

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _diff_lines(text_a: str, text_b: str) -> dict:
    """Line-level diff."""
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)

    changes = []
    additions = 0
    deletions = 0
    modifications = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "insert":
            additions += j2 - j1
            for line in lines_b[j1:j2]:
                changes.append({"type": "addition", "line": j1 + 1, "content": line.rstrip()})
        elif tag == "delete":
            deletions += i2 - i1
            for line in lines_a[i1:i2]:
                changes.append({"type": "deletion", "line": i1 + 1, "content": line.rstrip()})
        elif tag == "replace":
            modifications += max(i2 - i1, j2 - j1)
            for line in lines_a[i1:i2]:
                changes.append({"type": "deleted", "line": i1 + 1, "content": line.rstrip()})
            for line in lines_b[j1:j2]:
                changes.append({"type": "added", "line": j1 + 1, "content": line.rstrip()})

    return {"changes": changes[:100], "additions": additions, "deletions": deletions, "modifications": modifications}


def _diff_words(text_a: str, text_b: str) -> dict:
    """Word-level diff."""
    words_a = text_a.split()
    words_b = text_b.split()
    matcher = difflib.SequenceMatcher(None, words_a, words_b)

    changes = []
    additions = 0
    deletions = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "insert":
            additions += j2 - j1
            changes.append({"type": "addition", "words": " ".join(words_b[j1:j2])})
        elif tag == "delete":
            deletions += i2 - i1
            changes.append({"type": "deletion", "words": " ".join(words_a[i1:i2])})
        elif tag == "replace":
            changes.append({"type": "modification", "from": " ".join(words_a[i1:i2]), "to": " ".join(words_b[j1:j2])})
            additions += j2 - j1
            deletions += i2 - i1

    return {"changes": changes[:100], "additions": additions, "deletions": deletions}


def _diff_paragraphs(text_a: str, text_b: str) -> dict:
    """Paragraph-level diff."""
    paras_a = [p.strip() for p in text_a.split("\n\n") if p.strip()]
    paras_b = [p.strip() for p in text_b.split("\n\n") if p.strip()]
    matcher = difflib.SequenceMatcher(None, paras_a, paras_b)

    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "insert":
            for p in paras_b[j1:j2]:
                changes.append({"type": "addition", "paragraph": p[:300]})
        elif tag == "delete":
            for p in paras_a[i1:i2]:
                changes.append({"type": "deletion", "paragraph": p[:300]})
        elif tag == "replace":
            changes.append({"type": "modification", "from": paras_a[i1][:300], "to": paras_b[j1][:300]})

    return {"changes": changes[:50]}


@nurav_tool(metadata=ToolMetadata(
    name="document_comparator",
    description="Compare two documents and highlight differences. Supports text, PDF, and DOCX formats. Shows additions, deletions, and modifications.",
    niche="files",
    status=ToolStatus.ACTIVE,
    icon="diff",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"document_a": "Original text here", "document_b": "Modified text here", "granularity": "word"},
            output='{"similarity_score": 0.85, "changes": [...], "summary": "3 additions, 2 deletions"}',
            description="Compare two text documents",
        ),
    ],
    input_schema={"document_a": "str", "document_b": "str", "format": "str ('text'|'pdf'|'docx')", "granularity": "str ('word'|'line'|'paragraph')"},
    output_schema={"similarity_score": "float", "changes": "array", "summary": "str"},
    avg_response_ms=1000,
    success_rate=0.95,
))
@tool
async def document_comparator(document_a: str, document_b: str, format: str = "text", granularity: str = "line") -> str:
    """Compare two documents and highlight differences."""
    if not document_a.strip() or not document_b.strip():
        return json.dumps({"error": "Both documents must be provided."})

    try:
        text_a = document_a
        text_b = document_b

        # If URLs provided for PDF/DOCX, download and extract
        if format in ("pdf", "docx") or document_a.startswith("http"):
            import httpx
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                if document_a.startswith("http"):
                    resp = await client.get(document_a)
                    resp.raise_for_status()
                    try:
                        import fitz
                        doc = fitz.open(stream=resp.content, filetype="pdf")
                        text_a = "\n\n".join(page.get_text() for page in doc)
                        doc.close()
                    except Exception:
                        text_a = resp.text
                if document_b.startswith("http"):
                    resp = await client.get(document_b)
                    resp.raise_for_status()
                    try:
                        import fitz
                        doc = fitz.open(stream=resp.content, filetype="pdf")
                        text_b = "\n\n".join(page.get_text() for page in doc)
                        doc.close()
                    except Exception:
                        text_b = resp.text

        # Compute similarity
        similarity = difflib.SequenceMatcher(None, text_a, text_b).ratio()

        # Compute diff based on granularity
        if granularity == "word":
            diff_result = _diff_words(text_a, text_b)
        elif granularity == "paragraph":
            diff_result = _diff_paragraphs(text_a, text_b)
        else:
            diff_result = _diff_lines(text_a, text_b)

        total_changes = len(diff_result["changes"])
        additions = diff_result.get("additions", sum(1 for c in diff_result["changes"] if c["type"] in ("addition", "added")))
        deletions = diff_result.get("deletions", sum(1 for c in diff_result["changes"] if c["type"] in ("deletion", "deleted")))
        modifications = diff_result.get("modifications", sum(1 for c in diff_result["changes"] if c["type"] == "modification"))

        summary = f"{additions} addition(s), {deletions} deletion(s), {modifications} modification(s)"
        if similarity > 0.95:
            summary = "Documents are nearly identical. " + summary
        elif similarity < 0.3:
            summary = "Documents are significantly different. " + summary

        # Generate unified diff preview
        unified = list(difflib.unified_diff(
            text_a.splitlines(), text_b.splitlines(),
            fromfile="Document A", tofile="Document B", lineterm=""
        ))

        return json.dumps({
            "similarity_score": round(similarity, 4),
            "changes": diff_result["changes"],
            "summary": summary,
            "total_changes": total_changes,
            "unified_diff": "\n".join(unified[:200]),
            "granularity": granularity,
            "doc_a_length": len(text_a),
            "doc_b_length": len(text_b),
        })
    except Exception as e:
        return json.dumps({"error": f"Document comparison failed: {str(e)}"})
