"""
Code Explainer Tool — LLM-powered code analysis with annotations, complexity, and suggestions.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="code_explainer",
    description="Explain code with line-by-line annotations, time/space complexity analysis, and improvement suggestions. Supports all major programming languages.",
    niche="code",
    status=ToolStatus.ACTIVE,
    icon="book-open-check",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"code": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)", "detail_level": "detailed"},
            output='{"language": "python", "explanation": "...", "complexity": {"time": "O(2^n)", "space": "O(n)"}, "suggestions": ["Use memoization"]}',
            description="Explain a Fibonacci function",
        ),
    ],
    input_schema={"code": "str", "language": "str (optional, auto-detected)", "detail_level": "str ('brief'|'detailed'|'beginner')"},
    output_schema={"language": "str", "explanation": "str", "annotated_lines": "array", "complexity": "dict", "suggestions": "array"},
    avg_response_ms=3000,
    success_rate=0.95,
))
@tool
async def code_explainer(code: str, language: str = "", detail_level: str = "detailed") -> str:
    """Explain code with annotations, complexity analysis, and suggestions."""
    if not code.strip():
        return json.dumps({"error": "No code provided."})
    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        lang_hint = f"The code is written in {language}." if language else "Auto-detect the programming language."
        detail_map = {
            "brief": "Give a concise 2-3 sentence explanation.",
            "detailed": "Give a thorough explanation with line-by-line annotations.",
            "beginner": "Explain as if to someone who just started programming. Use simple language and analogies.",
        }

        system = f"""You are an expert code analyst. {lang_hint} {detail_map.get(detail_level, detail_map['detailed'])}
Respond ONLY with valid JSON:
{{
  "language": "detected language",
  "explanation": "overall explanation of what the code does",
  "annotated_lines": [{{"line": 1, "code": "...", "annotation": "explanation"}}],
  "complexity": {{"time": "O(...)", "space": "O(...)"}},
  "suggestions": ["improvement suggestion 1", "..."],
  "potential_issues": ["any bugs or edge cases"]
}}"""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=f"Explain this code:\n\n```\n{code[:8000]}\n```")])
        text = resp.content.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        return text
    except Exception as e:
        return json.dumps({"error": f"Code explanation failed: {str(e)}"})
