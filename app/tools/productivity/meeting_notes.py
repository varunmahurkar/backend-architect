"""
Meeting Notes Tool — Generate structured meeting notes from transcripts.
Uses LLM to extract decisions, action items, topics, and attendees.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="meeting_notes",
    description="Generate structured meeting notes from transcripts or raw meeting text. Extracts key decisions, action items with owners and deadlines, attendees, topics discussed, and a concise summary.",
    niche="productivity",
    status=ToolStatus.ACTIVE,
    icon="mic",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"transcript": "Alice: We should launch by Q2. Bob: Agreed, let's assign Sarah to testing.", "format": "structured"},
            output='{"summary": "...", "action_items": [{"task": "...", "owner": "Sarah", "deadline": "Q2"}], "key_decisions": [...]}',
            description="Extract meeting notes from transcript",
        ),
    ],
    input_schema={"transcript": "str", "format": "str ('structured'|'summary'|'action_items_only')", "attendees": "str (optional, comma-separated)"},
    output_schema={"title": "str", "summary": "str", "topics": "array", "action_items": "array", "key_decisions": "array", "attendees": "array"},
    avg_response_ms=4000,
    success_rate=0.94,
))
@tool
async def meeting_notes(transcript: str, format: str = "structured", attendees: str = "") -> str:
    """Generate structured meeting notes from a transcript."""
    if not transcript.strip():
        return json.dumps({"error": "No transcript provided."})

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        attendees_note = f"Known attendees: {attendees}." if attendees.strip() else "Extract attendees from the transcript."
        format_note = {
            "summary": "Focus on a concise 2-3 paragraph summary.",
            "action_items_only": "Focus exclusively on extracting action items.",
            "structured": "Provide full structured notes with all sections.",
        }.get(format, "Provide full structured notes.")

        system = f"""You are an expert meeting notes assistant.
{attendees_note} {format_note}

Analyze the meeting transcript and respond ONLY with valid JSON:
{{
  "title": "Meeting title (inferred from context)",
  "date": "Date if mentioned, otherwise null",
  "duration": "Duration if mentioned, otherwise null",
  "attendees": ["Person 1", "Person 2"],
  "summary": "Concise 2-3 paragraph summary of the meeting",
  "topics": [
    {{"topic": "Topic name", "discussion": "Brief summary of discussion"}}
  ],
  "action_items": [
    {{"task": "Task description", "owner": "Person responsible or 'TBD'", "deadline": "Deadline or 'TBD'", "priority": "high|medium|low"}}
  ],
  "key_decisions": ["Decision 1", "Decision 2"],
  "open_questions": ["Unresolved question 1"],
  "next_steps": "What happens next"
}}"""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Generate meeting notes from this transcript:\n\n{transcript[:12000]}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        result = json.loads(result_text)
        result["format"] = format
        result["transcript_length"] = len(transcript)
        return json.dumps(result, ensure_ascii=False)

    except json.JSONDecodeError:
        return json.dumps({"error": "Could not parse meeting notes. Try a shorter or clearer transcript."})
    except Exception as e:
        return json.dumps({"error": f"Meeting notes generation failed: {str(e)}"})
