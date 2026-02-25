"""
Calculator Tool — FUTURE: Symbolic math solver.
Currently returns mock data demonstrating expected output format.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="calculator",
    description="Solve mathematical expressions and equations with step-by-step solutions. Supports algebra, calculus, and symbolic math.",
    niche="math",
    status=ToolStatus.COMING_SOON,
    icon="calculator",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"expression": "6 * 7"},
            output='{"result": "42", "expression": "6 * 7", "steps": ["6 × 7 = 42"]}',
            description="Evaluate a simple multiplication",
        ),
    ],
    input_schema={"expression": "str"},
    output_schema={"result": "str", "expression": "str", "steps": "array"},
    avg_response_ms=100,
))
@tool
async def calculator(expression: str) -> str:
    """Solve a mathematical expression with step-by-step working. Currently returns mock data (coming soon)."""
    return json.dumps({
        "result": "42",
        "expression": expression,
        "steps": [f"{expression} = 42"],
        "note": "This tool is coming soon. Showing mock output.",
    })
