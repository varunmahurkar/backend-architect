"""
Chart Generator Tool — FUTURE: Generate charts and graphs from data.
Currently returns mock data demonstrating expected output format.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="chart_generator",
    description="Generate charts and graphs from structured data. Supports bar, line, pie, scatter, and more.",
    niche="visualization",
    status=ToolStatus.COMING_SOON,
    icon="bar-chart-3",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"data": {"labels": ["A", "B", "C"], "values": [10, 20, 30]}, "chart_type": "bar"},
            output='{"chart_url": "data:image/svg+xml;...", "chart_type": "bar", "data_points": 3}',
            description="Generate a bar chart",
        ),
    ],
    input_schema={"data": "dict (labels + values)", "chart_type": "str (bar, line, pie, scatter)"},
    output_schema={"chart_url": "str", "chart_type": "str", "data_points": "int"},
    avg_response_ms=1500,
))
@tool
async def chart_generator(data: str = '{"labels": ["A", "B", "C"], "values": [10, 20, 30]}', chart_type: str = "bar") -> str:
    """Generate a chart from data. Currently returns mock data (coming soon)."""
    return json.dumps({
        "chart_url": "data:image/svg+xml;base64,PHN2Zy8+",
        "chart_type": chart_type,
        "data_points": 3,
        "note": "This tool is coming soon. Showing mock output.",
    })
