"""
Python Executor Tool — FUTURE: Sandboxed Python code execution.
Currently returns mock data demonstrating expected output format.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="python_executor",
    description="Execute Python code in a sandboxed environment. Returns stdout, stderr, and execution metadata.",
    niche="code",
    status=ToolStatus.COMING_SOON,
    icon="terminal",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"code": "print('Hello World!')"},
            output='{"output": "Hello World!", "execution_time_ms": 42, "status": "success"}',
            description="Execute a simple print statement",
        ),
    ],
    input_schema={"code": "str", "timeout_seconds": "int (default 10)"},
    output_schema={"output": "str", "execution_time_ms": "int", "status": "str", "error": "str|null"},
    avg_response_ms=500,
))
@tool
async def python_executor(code: str, timeout_seconds: int = 10) -> str:
    """Execute Python code in a sandboxed environment. Currently returns mock data (coming soon)."""
    return json.dumps({
        "output": "Hello World!",
        "execution_time_ms": 42,
        "status": "success",
        "error": None,
        "note": "This tool is coming soon. Showing mock output.",
    })
