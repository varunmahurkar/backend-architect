"""Code Explainer Tool — COMING SOON: Explain code with annotations."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="code_explainer",
    description="Explain code with line-by-line annotations, complexity analysis, and improvement suggestions. Supports all major languages.",
    niche="code",
    status=ToolStatus.COMING_SOON,
    icon="book-open-check",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"code": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)", "detail_level": "detailed"},
            output='{"language": "python", "explanation": "...", "complexity": {"time": "O(2^n)", "space": "O(n)"}}',
            description="Explain a Fibonacci function",
        ),
    ],
    input_schema={"code": "str", "language": "str (optional, auto-detected)", "detail_level": "str ('brief'|'detailed'|'beginner')"},
    output_schema={"language": "str", "explanation": "str", "annotated_lines": "array", "complexity": "dict", "suggestions": "array"},
    avg_response_ms=3000,
))
@tool
async def code_explainer(code: str, language: str = "", detail_level: str = "detailed") -> str:
    """Explain code with annotations. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Code explainer is under development. Will use LLM-based analysis."})
