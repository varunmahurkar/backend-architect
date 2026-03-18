"""
Video Summarizer Tool — Summarize YouTube videos from transcripts.
Uses existing YouTube transcript extraction + LLM summarization.
"""

import json
import logging
import re

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pat in patterns:
        match = re.search(pat, url)
        if match:
            return match.group(1)
    return None


async def _get_transcript(video_id: str) -> list[dict]:
    """Get YouTube transcript."""
    from youtube_transcript_api import YouTubeTranscriptApi

    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    return transcript


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


async def _summarize_transcript(transcript: list[dict], style: str, include_timestamps: bool) -> dict:
    """Summarize transcript using LLM."""
    from app.services.llm_service import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    # Build full text with timestamps
    full_text = ""
    for entry in transcript:
        ts = _format_timestamp(entry["start"])
        full_text += f"[{ts}] {entry['text']}\n"

    # Chunk if too long (keep under ~10K chars)
    if len(full_text) > 12000:
        full_text = full_text[:12000] + "\n[... transcript truncated ...]"

    style_instructions = {
        "brief": "Provide a 2-3 sentence summary of the key takeaway.",
        "detailed": "Provide a comprehensive summary covering all main topics discussed, organized by theme.",
        "bullet_points": "Summarize as a bulleted list of key points (10-15 bullets). Use - for each bullet.",
    }

    timestamp_instruction = ""
    if include_timestamps:
        timestamp_instruction = "\nAlso identify 5-8 key moments with their timestamps in format [MM:SS] - description."

    system_prompt = f"""You are a video content summarizer. {style_instructions.get(style, style_instructions['detailed'])}
{timestamp_instruction}

Respond in JSON format:
{{
  "summary": "the summary text",
  "key_points": ["point 1", "point 2", ...],
  "topics": ["topic1", "topic2", ...],
  "key_moments": [{{"timestamp": "MM:SS", "description": "..."}}]
}}"""

    llm = get_llm(provider="google")
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Summarize this video transcript:\n\n{full_text}"),
    ])

    text = response.content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": text,
            "key_points": [],
            "topics": [],
            "key_moments": [],
        }


@nurav_tool(metadata=ToolMetadata(
    name="video_summarizer",
    description="Summarize YouTube videos from their transcripts. Returns key points, timestamps, topics, and a structured summary powered by AI.",
    niche="media",
    status=ToolStatus.ACTIVE,
    icon="video",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "summary_style": "bullet_points"},
            output='{"summary": "...", "key_points": [...], "topics": [...], "key_moments": [...], "duration_seconds": 212}',
            description="Summarize a YouTube video",
        ),
    ],
    input_schema={"video_url": "str", "summary_style": "str ('brief'|'detailed'|'bullet_points')", "include_timestamps": "bool (default true)"},
    output_schema={"summary": "str", "key_points": "array", "topics": "array", "key_moments": "array", "duration_seconds": "float"},
    avg_response_ms=8000,
    success_rate=0.85,
))
@tool
async def video_summarizer(video_url: str, summary_style: str = "detailed", include_timestamps: bool = True) -> str:
    """Summarize a YouTube video from its transcript."""
    video_id = _extract_video_id(video_url)
    if not video_id:
        return json.dumps({"error": "Invalid YouTube URL. Provide a valid youtube.com or youtu.be link."})

    try:
        transcript = await _get_transcript(video_id)
    except Exception as e:
        return json.dumps({"error": f"Could not get transcript: {str(e)}. The video may not have captions."})

    if not transcript:
        return json.dumps({"error": "No transcript available for this video."})

    # Calculate duration
    last_entry = transcript[-1]
    duration = last_entry["start"] + last_entry.get("duration", 0)

    try:
        result = await _summarize_transcript(transcript, summary_style, include_timestamps)
        result["video_id"] = video_id
        result["duration_seconds"] = round(duration, 1)
        result["transcript_entries"] = len(transcript)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Summarization failed: {str(e)}"})
