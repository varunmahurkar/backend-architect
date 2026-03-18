"""
Task Extractor Tool — Extract action items and tasks from unstructured text.
Identifies assignees, deadlines, and priorities using LLM.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="task_extractor",
    description="Extract action items, tasks, and to-dos from unstructured text (meeting notes, emails, documents). Identifies assignees, deadlines, priorities, and dependencies.",
    niche="productivity",
    status=ToolStatus.ACTIVE,
    icon="list-checks",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"text": "John needs to finish the report by Friday. Sarah should review the PR. Don't forget to update the docs.", "format": "list"},
            output='{"tasks": [{"title": "Finish report", "assignee": "John", "deadline": "Friday", "priority": "high"}], "total": 3}',
            description="Extract tasks from meeting notes",
        ),
    ],
    input_schema={"text": "str", "context": "str (optional project context)", "format": "str ('list'|'kanban'|'json')"},
    output_schema={"tasks": "array", "total": "int", "by_assignee": "dict", "by_priority": "dict"},
    avg_response_ms=2500,
    success_rate=0.95,
))
@tool
async def task_extractor(text: str, context: str = "", format: str = "list") -> str:
    """Extract tasks and action items from text."""
    if not text.strip():
        return json.dumps({"error": "No text provided."})

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        context_note = f"\nProject context: {context}" if context.strip() else ""

        system = f"""You are an expert at extracting action items and tasks from text.{context_note}

Extract ALL tasks, action items, to-dos, and obligations from the text.
For each task, identify:
- The specific action to be done
- Who is responsible (if mentioned or implied)
- Any deadline (if mentioned)
- Priority (infer from language: urgent/ASAP = high, normal = medium, optional = low)
- Any dependencies on other tasks

Respond ONLY with valid JSON:
{{
  "tasks": [
    {{
      "title": "Clear, actionable task title",
      "description": "More detail if available",
      "assignee": "Person name or 'Unassigned'",
      "deadline": "Deadline string or null",
      "priority": "high|medium|low",
      "status": "todo",
      "dependencies": ["task title it depends on"],
      "category": "development|design|review|communication|research|other"
    }}
  ]
}}

Be thorough — extract implicit tasks too (e.g., 'we should look into X' = task to investigate X)."""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Extract tasks from:\n\n{text[:10000]}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        result = json.loads(result_text)
        tasks = result.get("tasks", [])

        # Group by assignee
        by_assignee: dict[str, list] = {}
        for task in tasks:
            assignee = task.get("assignee", "Unassigned")
            by_assignee.setdefault(assignee, []).append(task["title"])

        # Group by priority
        by_priority: dict[str, list] = {"high": [], "medium": [], "low": []}
        for task in tasks:
            priority = task.get("priority", "medium")
            by_priority.setdefault(priority, []).append(task["title"])

        # Format for kanban output
        if format == "kanban":
            kanban = {
                "todo": [t for t in tasks if t.get("status") == "todo"],
                "in_progress": [],
                "done": [],
            }
            return json.dumps({
                "kanban": kanban,
                "tasks": tasks,
                "total": len(tasks),
                "by_assignee": by_assignee,
                "by_priority": by_priority,
            }, ensure_ascii=False)

        return json.dumps({
            "tasks": tasks,
            "total": len(tasks),
            "by_assignee": by_assignee,
            "by_priority": by_priority,
            "format": format,
        }, ensure_ascii=False)

    except json.JSONDecodeError:
        return json.dumps({"error": "Could not parse tasks. Try providing cleaner text."})
    except Exception as e:
        return json.dumps({"error": f"Task extraction failed: {str(e)}"})
