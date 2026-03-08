"""Code Generator Tool — COMING SOON: Generate code from specs."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="code_generator",
    description="Generate code from natural language specifications. Supports multiple languages, includes tests and documentation.",
    niche="code",
    status=ToolStatus.COMING_SOON,
    icon="wand-2",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"spec": "Create a function that checks if a string is a palindrome", "language": "python"},
            output='{"code": "def is_palindrome(s): ...", "tests": "...", "documentation": "..."}',
            description="Generate a palindrome checker",
        ),
    ],
    input_schema={"spec": "str", "language": "str (default 'python')", "include_tests": "bool (default true)", "style": "str ('functional'|'oop'|'auto')"},
    output_schema={"code": "str", "tests": "str", "documentation": "str", "language": "str", "dependencies": "array"},
    avg_response_ms=5000,
))
@tool
async def code_generator(spec: str, language: str = "python", include_tests: bool = True, style: str = "auto") -> str:
    """Generate code from a specification. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Code generator is under development. Will use LLM with structured output."})
