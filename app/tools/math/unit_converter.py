"""Unit Converter Tool — COMING SOON: Convert between units."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="unit_converter",
    description="Convert between units of measurement. Supports length, mass, temperature, time, energy, data, currency, and more.",
    niche="math",
    status=ToolStatus.COMING_SOON,
    icon="ruler",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"value": "100", "from_unit": "celsius", "to_unit": "fahrenheit"},
            output='{"result": 212.0, "from": "celsius", "to": "fahrenheit", "formula": "°F = °C × 9/5 + 32"}',
            description="Convert Celsius to Fahrenheit",
        ),
    ],
    input_schema={"value": "str", "from_unit": "str", "to_unit": "str", "category": "str (optional)"},
    output_schema={"result": "float", "from": "str", "to": "str", "formula": "str"},
    avg_response_ms=100,
))
@tool
async def unit_converter(value: str, from_unit: str, to_unit: str, category: str = "") -> str:
    """Convert between units. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Unit converter is under development. Will use pint library + exchange rate API for currency."})
