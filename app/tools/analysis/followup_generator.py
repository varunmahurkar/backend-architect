"""
Follow-up Generator Tool — Wraps followup.py question generation
Generates follow-up question suggestions based on a query and response.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="followup_generator",
    description="Generate 5 relevant follow-up questions that a user might want to ask next, based on the original query and response.",
    niche="analysis",
    status=ToolStatus.ACTIVE,
    icon="message-circle-question",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "What is machine learning?", "response_text": "Machine learning is a subset of AI..."},
            output='["What are the types of ML?", "How does deep learning differ?", ...]',
            description="Generate follow-up questions for an ML query",
        ),
    ],
    input_schema={"query": "str", "response_text": "str"},
    output_schema={"type": "array", "items": "str"},
    avg_response_ms=2000,
    success_rate=0.90,
))
@tool
async def followup_generator(query: str, response_text: str) -> str:
    """Generate 5 follow-up question suggestions based on a query and response."""
    from app.services.agents.nodes.followup import generate_followup_questions

    questions = await generate_followup_questions(query=query, response_text=response_text)
    return json.dumps(questions, ensure_ascii=False)
