"""
Code Generator Tool — Generate code from natural language specs using LLM.
Includes tests, documentation, and dependency lists.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="code_generator",
    description="Generate code from natural language specifications. Supports multiple languages, includes tests and documentation.",
    niche="code",
    status=ToolStatus.ACTIVE,
    icon="wand-2",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"spec": "Create a function that checks if a string is a palindrome", "language": "python", "include_tests": True},
            output='{"code": "def is_palindrome(s): ...", "tests": "def test_palindrome(): ...", "documentation": "..."}',
            description="Generate a palindrome checker",
        ),
    ],
    input_schema={"spec": "str", "language": "str (default 'python')", "include_tests": "bool (default true)", "style": "str ('functional'|'oop'|'auto')"},
    output_schema={"code": "str", "tests": "str", "documentation": "str", "language": "str", "dependencies": "array"},
    avg_response_ms=5000,
    success_rate=0.92,
))
@tool
async def code_generator(spec: str, language: str = "python", include_tests: bool = True, style: str = "auto") -> str:
    """Generate code from a natural language specification."""
    if not spec.strip():
        return json.dumps({"error": "No specification provided."})
    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        test_instruction = "Include comprehensive unit tests." if include_tests else "Do not include tests."
        system = f"""You are an expert software engineer. Generate production-quality {language} code.
Style preference: {style}. {test_instruction}
Respond ONLY with valid JSON:
{{
  "code": "the implementation code",
  "tests": "test code (empty string if not requested)",
  "documentation": "docstring/JSDoc explaining usage, parameters, return values",
  "language": "{language}",
  "dependencies": ["any required packages/libraries"]
}}
Write clean, well-structured, idiomatic {language} code."""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=f"Generate code for:\n\n{spec}")])
        text = resp.content.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        return text
    except Exception as e:
        return json.dumps({"error": f"Code generation failed: {str(e)}"})
