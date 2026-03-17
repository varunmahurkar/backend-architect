"""
Unit Converter Tool — Convert between units of measurement.
Built-in conversion tables (no external deps). Currency via free API.
"""

import json
import logging

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

# Conversion factors to base units
CONVERSIONS = {
    "length": {
        "m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "yd": 0.9144,
        "ft": 0.3048, "in": 0.0254, "nm": 1852, "μm": 1e-6, "nm_nano": 1e-9,
    },
    "mass": {
        "kg": 1, "g": 0.001, "mg": 1e-6, "lb": 0.453592, "oz": 0.0283495,
        "ton": 1000, "st": 6.35029,
    },
    "volume": {
        "l": 1, "ml": 0.001, "gal": 3.78541, "qt": 0.946353, "pt": 0.473176,
        "cup": 0.236588, "fl_oz": 0.0295735, "tbsp": 0.0147868, "tsp": 0.00492892,
        "m3": 1000, "cm3": 0.001,
    },
    "speed": {
        "m/s": 1, "km/h": 0.277778, "mph": 0.44704, "knot": 0.514444, "ft/s": 0.3048,
    },
    "time": {
        "s": 1, "ms": 0.001, "min": 60, "h": 3600, "day": 86400, "week": 604800,
        "month": 2592000, "year": 31536000,
    },
    "data": {
        "b": 1, "kb": 1024, "mb": 1048576, "gb": 1073741824, "tb": 1099511627776,
        "bit": 0.125,
    },
    "area": {
        "m2": 1, "km2": 1e6, "cm2": 1e-4, "ft2": 0.092903, "acre": 4046.86,
        "hectare": 10000, "mi2": 2.59e6,
    },
    "energy": {
        "j": 1, "kj": 1000, "cal": 4.184, "kcal": 4184, "kwh": 3.6e6,
        "btu": 1055.06, "ev": 1.602e-19,
    },
}


def _convert_temperature(value: float, from_u: str, to_u: str) -> float:
    """Special handling for temperature conversions."""
    from_u, to_u = from_u.lower(), to_u.lower()
    # Normalize to Celsius first
    if from_u in ("c", "celsius"):
        c = value
    elif from_u in ("f", "fahrenheit"):
        c = (value - 32) * 5 / 9
    elif from_u in ("k", "kelvin"):
        c = value - 273.15
    else:
        raise ValueError(f"Unknown temperature unit: {from_u}")

    # Convert from Celsius to target
    if to_u in ("c", "celsius"):
        return c
    elif to_u in ("f", "fahrenheit"):
        return c * 9 / 5 + 32
    elif to_u in ("k", "kelvin"):
        return c + 273.15
    else:
        raise ValueError(f"Unknown temperature unit: {to_u}")


def _find_category(unit: str) -> tuple[str, str] | None:
    """Find which category a unit belongs to."""
    unit_lower = unit.lower()
    for cat, units in CONVERSIONS.items():
        if unit_lower in units:
            return cat, unit_lower
    return None


async def _convert_currency(value: float, from_c: str, to_c: str) -> dict:
    """Convert currency using free API."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"https://api.exchangerate-api.com/v4/latest/{from_c.upper()}")
        resp.raise_for_status()
        data = resp.json()
    rate = data["rates"].get(to_c.upper())
    if rate is None:
        raise ValueError(f"Unknown currency: {to_c}")
    return {"result": round(value * rate, 4), "rate": rate, "source": "exchangerate-api.com"}


@nurav_tool(metadata=ToolMetadata(
    name="unit_converter",
    description="Convert between units of measurement. Supports length, mass, temperature, time, volume, speed, data, energy, area, and currency.",
    niche="math",
    status=ToolStatus.ACTIVE,
    icon="ruler",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"value": "100", "from_unit": "celsius", "to_unit": "fahrenheit"},
            output='{"result": 212.0, "from": "celsius", "to": "fahrenheit", "formula": "°F = °C × 9/5 + 32"}',
            description="Convert Celsius to Fahrenheit",
        ),
        ToolExample(
            input={"value": "5.5", "from_unit": "km", "to_unit": "mi"},
            output='{"result": 3.4175, "from": "km", "to": "mi", "category": "length"}',
            description="Convert kilometers to miles",
        ),
    ],
    input_schema={"value": "str", "from_unit": "str", "to_unit": "str"},
    output_schema={"result": "float", "from": "str", "to": "str", "formula": "str", "category": "str"},
    avg_response_ms=200,
    success_rate=0.95,
))
@tool
async def unit_converter(value: str, from_unit: str, to_unit: str) -> str:
    """Convert between units of measurement."""
    try:
        val = float(value)
    except ValueError:
        return json.dumps({"error": f"Invalid numeric value: '{value}'"})

    from_lower = from_unit.lower().strip()
    to_lower = to_unit.lower().strip()

    # Temperature
    temp_units = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}
    if from_lower in temp_units and to_lower in temp_units:
        result = _convert_temperature(val, from_lower, to_lower)
        return json.dumps({"result": round(result, 6), "from": from_unit, "to": to_unit, "category": "temperature", "formula": "Temperature conversion"})

    # Currency (3-letter codes)
    if len(from_unit) == 3 and len(to_unit) == 3 and from_unit.isalpha() and to_unit.isalpha():
        from_cat = _find_category(from_lower)
        if from_cat is None:
            try:
                data = await _convert_currency(val, from_unit, to_unit)
                return json.dumps({"result": data["result"], "from": from_unit.upper(), "to": to_unit.upper(), "category": "currency", "rate": data["rate"]})
            except Exception as e:
                pass  # Fall through to regular conversion

    # Standard conversion
    from_cat = _find_category(from_lower)
    to_cat = _find_category(to_lower)

    if from_cat is None:
        return json.dumps({"error": f"Unknown unit: '{from_unit}'", "supported": list(CONVERSIONS.keys()) + ["temperature", "currency"]})
    if to_cat is None:
        return json.dumps({"error": f"Unknown unit: '{to_unit}'"})

    cat1, unit1 = from_cat
    cat2, unit2 = to_cat

    if cat1 != cat2:
        return json.dumps({"error": f"Cannot convert between {cat1} ({from_unit}) and {cat2} ({to_unit})"})

    base_value = val * CONVERSIONS[cat1][unit1]
    result = base_value / CONVERSIONS[cat1][unit2]

    return json.dumps({"result": round(result, 6), "from": from_unit, "to": to_unit, "category": cat1})
