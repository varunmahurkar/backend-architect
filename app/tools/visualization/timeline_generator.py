"""
Timeline Generator Tool — Create chronological timelines from events or text.
Produces Mermaid Gantt/timeline code + structured event JSON.
"""

import json
import logging
import re

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _events_to_mermaid_timeline(events: list[dict]) -> str:
    """Generate Mermaid timeline diagram."""
    lines = ["timeline"]
    # Group by year/period if possible
    current_period = None
    for ev in events:
        date = str(ev.get("date", ""))
        title = ev.get("title", "")
        desc = ev.get("description", "")
        year_match = re.search(r'\b(1[0-9]{3}|2[0-9]{3})\b', date)
        period = year_match.group(0) if year_match else date

        if period != current_period:
            lines.append(f"    section {period}")
            current_period = period

        entry = title
        if desc:
            entry += f" : {desc[:60]}"
        lines.append(f"        {entry}")

    return "\n".join(lines)


def _events_to_mermaid_gantt(events: list[dict]) -> str:
    """Generate Mermaid Gantt chart for timeline."""
    lines = [
        "gantt",
        "    title Timeline",
        "    dateFormat YYYY",
        "    axisFormat %Y",
        "    section Events",
    ]
    for ev in events:
        date = str(ev.get("date", "2000"))
        title = ev.get("title", "Event").replace(":", "")
        year_match = re.search(r'\b(1[0-9]{3}|2[0-9]{3})\b', date)
        year = year_match.group(0) if year_match else "2000"
        lines.append(f"    {title} : {year}, 1y")
    return "\n".join(lines)


@nurav_tool(metadata=ToolMetadata(
    name="timeline_generator",
    description="Create chronological timelines from events, text, or topics. Extracts dates and events from free text, visualizes sequences with Mermaid diagrams and structured JSON.",
    niche="visualization",
    status=ToolStatus.ACTIVE,
    icon="calendar-range",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"events": '[{"date": "2017", "title": "Transformers", "description": "Attention is All You Need"}]', "format": "mermaid"},
            output='{"mermaid_code": "timeline\\n    section 2017\\n        Transformers : ...", "events": [...]}',
            description="Create AI milestones timeline",
        ),
    ],
    input_schema={"events": "str (JSON array or free text)", "style": "str ('timeline'|'gantt')", "format": "str ('mermaid'|'json')"},
    output_schema={"mermaid_code": "str", "events": "array", "total_events": "int", "date_range": "str"},
    avg_response_ms=3500,
    success_rate=0.92,
))
@tool
async def timeline_generator(events: str, style: str = "timeline", format: str = "mermaid") -> str:
    """Create a chronological timeline from events or free text."""
    if not events.strip():
        return json.dumps({"error": "No events or text provided."})

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        # Try to parse as JSON first
        parsed_events = None
        try:
            parsed_events = json.loads(events)
            if not isinstance(parsed_events, list):
                parsed_events = None
        except (json.JSONDecodeError, ValueError):
            parsed_events = None

        if parsed_events is None:
            # Extract events from free text using LLM
            system = """You are an expert at extracting chronological events from text.
Extract all events with dates and create a structured timeline.
Respond ONLY with valid JSON array:
[
  {
    "date": "year or date string",
    "title": "event title (short, 2-6 words)",
    "description": "brief description (optional)",
    "significance": "high|medium|low"
  }
]
Sort events chronologically. Include all events with clear dates."""

            llm = get_llm(provider="google")
            resp = await llm.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content=f"Extract timeline events from:\n\n{events[:6000]}"),
            ])
            result_text = resp.content.strip()
            if result_text.startswith("```"):
                result_text = "\n".join(result_text.split("\n")[1:-1])
            parsed_events = json.loads(result_text)

        # Sort by date (best effort)
        def date_sort_key(ev):
            date_str = str(ev.get("date", "0"))
            match = re.search(r'\b(1[0-9]{3}|2[0-9]{3})\b', date_str)
            return int(match.group(0)) if match else 0

        parsed_events.sort(key=date_sort_key)

        # Generate Mermaid
        if style == "gantt":
            mermaid_code = _events_to_mermaid_gantt(parsed_events)
        else:
            mermaid_code = _events_to_mermaid_timeline(parsed_events)

        # Date range
        years = []
        for ev in parsed_events:
            m = re.search(r'\b(1[0-9]{3}|2[0-9]{3})\b', str(ev.get("date", "")))
            if m:
                years.append(int(m.group(0)))
        date_range = f"{min(years)}–{max(years)}" if years else "Unknown"

        return json.dumps({
            "mermaid_code": mermaid_code,
            "events": parsed_events,
            "total_events": len(parsed_events),
            "date_range": date_range,
            "style": style,
        })
    except json.JSONDecodeError:
        return json.dumps({"error": "Could not parse events. Provide a JSON array or free text with dates."})
    except Exception as e:
        return json.dumps({"error": f"Timeline generation failed: {str(e)}"})
