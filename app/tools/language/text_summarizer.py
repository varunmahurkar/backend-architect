"""
Text Summarizer Tool — Summarize long text using LLM.
Supports paragraph, bullet points, key points, and TLDR styles.
For very long texts, uses recursive chunking.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 12000  # ~3000 tokens per chunk


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks, preferring paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars:
            if current:
                chunks.append(current.strip())
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_chars]]


async def _summarize_with_llm(text: str, style: str, focus: str, max_length: int | None) -> dict:
    """Summarize text using LLM."""
    from app.services.llm_service import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    style_prompts = {
        "paragraph": "Write a concise summary in 1-3 paragraphs.",
        "bullet_points": "Summarize as a bulleted list of key points (use - for bullets).",
        "key_points": "Extract the 5-10 most important key points, numbered.",
        "tldr": "Write a single-sentence TLDR summary.",
    }

    system = f"""You are a precise summarizer. {style_prompts.get(style, style_prompts['paragraph'])}
{"Focus on: " + focus if focus else ""}
{"Maximum length: " + str(max_length) + " words." if max_length else ""}
Only return the summary, no preamble."""

    llm = get_llm(provider="google")
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Summarize this text:\n\n{text}"),
    ])

    summary = response.content.strip()

    # Extract key points
    key_points = []
    for line in summary.split("\n"):
        line = line.strip()
        if line and (line.startswith("-") or line.startswith("•") or (len(line) > 2 and line[0].isdigit() and line[1] in ".)")):
            key_points.append(line.lstrip("-•0123456789.) ").strip())

    return {
        "summary": summary,
        "key_points": key_points if key_points else [],
    }


@nurav_tool(metadata=ToolMetadata(
    name="text_summarizer",
    description="Summarize long text into key points, bullet points, or a concise paragraph. Supports extractive and abstractive summarization with focus topics.",
    niche="language",
    status=ToolStatus.ACTIVE,
    icon="align-left",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"text": "Long article text here...", "style": "bullet_points"},
            output='{"summary": "- Point 1\\n- Point 2", "key_points": ["Point 1", "Point 2"], "word_count": {"original": 5000, "summary": 150}}',
            description="Summarize an article as bullet points",
        ),
        ToolExample(
            input={"text": "Research paper abstract...", "style": "tldr"},
            output='{"summary": "One sentence summary.", "key_points": [], "word_count": {"original": 300, "summary": 15}}',
            description="Get a TLDR of a paper",
        ),
    ],
    input_schema={"text": "str", "style": "str (paragraph|bullet_points|key_points|tldr)", "max_length": "int (optional)", "focus": "str (optional)"},
    output_schema={"summary": "str", "key_points": "array", "word_count": "dict", "compression_ratio": "float"},
    avg_response_ms=3000,
    success_rate=0.95,
))
@tool
async def text_summarizer(text: str, style: str = "paragraph", max_length: int = 0, focus: str = "") -> str:
    """Summarize long text. Choose style: paragraph, bullet_points, key_points, or tldr."""
    if not text.strip():
        return json.dumps({"error": "No text provided."})

    original_words = len(text.split())

    try:
        chunks = _chunk_text(text)
        length = max_length if max_length > 0 else None

        if len(chunks) == 1:
            result = await _summarize_with_llm(chunks[0], style, focus, length)
        else:
            # Recursive summarization for long texts
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
                chunk_result = await _summarize_with_llm(chunk, "paragraph", focus, None)
                chunk_summaries.append(chunk_result["summary"])

            # Summarize the summaries
            combined = "\n\n".join(chunk_summaries)
            result = await _summarize_with_llm(combined, style, focus, length)
            result["chunks_processed"] = len(chunks)

        summary_words = len(result["summary"].split())
        result["word_count"] = {
            "original": original_words,
            "summary": summary_words,
        }
        result["compression_ratio"] = round(summary_words / original_words, 3) if original_words > 0 else 0

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Summarization failed: {str(e)}"})
