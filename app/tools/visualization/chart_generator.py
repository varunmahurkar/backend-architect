"""
Chart Generator Tool — 3 rendering engines with auto-routing.
- Matplotlib PNG: research-grade, handles large datasets
- Plotly HTML: interactive hover/zoom for medium datasets
- Pure SVG: crisp, scalable, lightweight for small datasets
"""

import json
import logging
import base64
import io
from typing import Any

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

# Color palette for charts
COLORS = [
    "#4F46E5", "#7C3AED", "#EC4899", "#F59E0B", "#10B981",
    "#3B82F6", "#EF4444", "#8B5CF6", "#06B6D4", "#84CC16",
]


def _parse_data(data_str: str) -> dict[str, Any]:
    """Parse data JSON string into labels and datasets."""
    data = json.loads(data_str)
    labels = data.get("labels", [])

    if "values" in data:
        datasets = [{"name": "Data", "values": data["values"]}]
    elif "datasets" in data:
        datasets = data["datasets"]
    else:
        raise ValueError("Data must have 'values' or 'datasets' key")

    return {"labels": labels, "datasets": datasets}


def _auto_select_format(data: dict, chart_type: str) -> str:
    """Auto-select the best rendering format based on data and chart type."""
    total_points = sum(len(ds.get("values", [])) for ds in data["datasets"])
    num_labels = len(data["labels"])

    if total_points > 50 or chart_type in ("histogram", "heatmap"):
        return "png"
    elif num_labels <= 10 and len(data["datasets"]) == 1 and chart_type in ("bar", "pie"):
        return "svg"
    else:
        return "png"  # Plotly HTML is hard to display in playground; default to PNG


def _render_matplotlib(data: dict, chart_type: str, title: str) -> str:
    """Render chart using Matplotlib, return base64 PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    labels = data["labels"]
    datasets = data["datasets"]

    if chart_type == "bar":
        import numpy as np
        x = np.arange(len(labels))
        width = 0.8 / len(datasets)
        for i, ds in enumerate(datasets):
            offset = (i - len(datasets) / 2 + 0.5) * width
            ax.bar(x + offset, ds["values"], width, label=ds.get("name", f"Series {i+1}"), color=COLORS[i % len(COLORS)])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right")

    elif chart_type == "line":
        for i, ds in enumerate(datasets):
            ax.plot(labels, ds["values"], marker="o", label=ds.get("name", f"Series {i+1}"), color=COLORS[i % len(COLORS)])

    elif chart_type == "pie":
        values = datasets[0]["values"]
        ax.pie(values, labels=labels, autopct="%1.1f%%", colors=COLORS[:len(labels)])
        ax.axis("equal")

    elif chart_type == "scatter":
        for i, ds in enumerate(datasets):
            ax.scatter(range(len(ds["values"])), ds["values"], label=ds.get("name", f"Series {i+1}"), color=COLORS[i % len(COLORS)], s=60)

    elif chart_type == "histogram":
        for i, ds in enumerate(datasets):
            ax.hist(ds["values"], bins="auto", alpha=0.7, label=ds.get("name", f"Series {i+1}"), color=COLORS[i % len(COLORS)])

    else:
        # Default to bar
        for i, ds in enumerate(datasets):
            ax.bar(labels, ds["values"], label=ds.get("name", f"Series {i+1}"), color=COLORS[i % len(COLORS)])

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")
    if len(datasets) > 1:
        ax.legend()

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _render_svg(data: dict, chart_type: str, title: str) -> str:
    """Generate a pure SVG chart for small datasets."""
    labels = data["labels"]
    values = data["datasets"][0]["values"]
    n = len(labels)

    if chart_type == "pie":
        return _render_svg_pie(labels, values, title)

    # Bar chart SVG
    width = 500
    height = 320
    padding = 60
    chart_w = width - 2 * padding
    chart_h = height - 2 * padding
    max_val = max(values) if values else 1
    bar_w = chart_w / max(n, 1) * 0.7
    gap = chart_w / max(n, 1) * 0.3

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
    ]

    if title:
        svg_parts.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#1F2937">{title}</text>')

    # Bars
    for i, (label, val) in enumerate(zip(labels, values)):
        x = padding + i * (bar_w + gap) + gap / 2
        bar_h = (val / max_val) * chart_h if max_val > 0 else 0
        y = padding + chart_h - bar_h
        color = COLORS[i % len(COLORS)]

        svg_parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{color}" rx="3"/>')
        svg_parts.append(f'<text x="{x + bar_w/2}" y="{y - 5}" text-anchor="middle" font-size="11" fill="#374151">{val}</text>')
        svg_parts.append(f'<text x="{x + bar_w/2}" y="{height - 20}" text-anchor="middle" font-size="10" fill="#6B7280">{label}</text>')

    svg_parts.append("</svg>")
    svg_str = "\n".join(svg_parts)
    b64 = base64.b64encode(svg_str.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


def _render_svg_pie(labels: list, values: list, title: str) -> str:
    """Generate a pure SVG pie chart."""
    import math

    width, height = 400, 400
    cx, cy, r = 200, 210, 140
    total = sum(values) if values else 1

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
    ]

    if title:
        svg_parts.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#1F2937">{title}</text>')

    start_angle = -math.pi / 2
    for i, (label, val) in enumerate(zip(labels, values)):
        angle = (val / total) * 2 * math.pi
        end_angle = start_angle + angle
        large_arc = 1 if angle > math.pi else 0

        x1 = cx + r * math.cos(start_angle)
        y1 = cy + r * math.sin(start_angle)
        x2 = cx + r * math.cos(end_angle)
        y2 = cy + r * math.sin(end_angle)

        color = COLORS[i % len(COLORS)]
        path = f"M {cx},{cy} L {x1},{y1} A {r},{r} 0 {large_arc},1 {x2},{y2} Z"
        svg_parts.append(f'<path d="{path}" fill="{color}"/>')

        # Label
        mid = start_angle + angle / 2
        lx = cx + (r * 0.65) * math.cos(mid)
        ly = cy + (r * 0.65) * math.sin(mid)
        pct = f"{val/total*100:.0f}%"
        svg_parts.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="11" fill="white" font-weight="bold">{pct}</text>')

        start_angle = end_angle

    svg_parts.append("</svg>")
    svg_str = "\n".join(svg_parts)
    b64 = base64.b64encode(svg_str.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


@nurav_tool(metadata=ToolMetadata(
    name="chart_generator",
    description="Generate charts from structured data. Supports bar, line, pie, scatter, and histogram. Auto-selects the best rendering engine (Matplotlib/SVG) based on data size.",
    niche="visualization",
    status=ToolStatus.ACTIVE,
    icon="bar-chart-3",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"data": '{"labels": ["Q1", "Q2", "Q3", "Q4"], "values": [100, 250, 180, 320]}', "chart_type": "bar", "title": "Revenue by Quarter"},
            output='{"chart_url": "data:image/png;base64,...", "chart_type": "bar", "data_points": 4, "format_used": "svg", "render_engine": "svg"}',
            description="Generate a bar chart of quarterly revenue",
        ),
        ToolExample(
            input={"data": '{"labels": ["Python", "JS", "Rust", "Go"], "values": [40, 30, 15, 15]}', "chart_type": "pie", "title": "Language Usage"},
            output='{"chart_url": "data:image/svg+xml;base64,...", "chart_type": "pie", "data_points": 4, "format_used": "svg", "render_engine": "svg"}',
            description="Generate a pie chart of language usage",
        ),
    ],
    input_schema={"data": "str (JSON with labels+values)", "chart_type": "str (bar,line,pie,scatter,histogram)", "title": "str", "format": "str (auto,png,svg)"},
    output_schema={"chart_url": "str (data URI)", "chart_type": "str", "data_points": "int", "format_used": "str", "render_engine": "str"},
    avg_response_ms=2000,
    success_rate=0.95,
))
@tool
async def chart_generator(data: str = '{"labels": ["A", "B", "C"], "values": [10, 20, 30]}', chart_type: str = "bar", title: str = "", format: str = "auto") -> str:
    """Generate a chart from JSON data. Provide data as JSON string with labels and values."""
    try:
        parsed = _parse_data(data)
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": f"Invalid data format: {str(e)}. Expected JSON with 'labels' and 'values' keys."})

    total_points = sum(len(ds.get("values", [])) for ds in parsed["datasets"])

    # Determine format
    if format == "auto":
        fmt = _auto_select_format(parsed, chart_type)
    elif format in ("png", "svg", "html"):
        fmt = format
    else:
        fmt = "png"

    try:
        if fmt == "svg":
            chart_url = _render_svg(parsed, chart_type, title)
            engine = "svg"
        else:  # png (or html fallback to png)
            chart_url = _render_matplotlib(parsed, chart_type, title)
            engine = "matplotlib"
            fmt = "png"

        return json.dumps({
            "chart_url": chart_url,
            "chart_type": chart_type,
            "data_points": total_points,
            "format_used": fmt,
            "render_engine": engine,
        })

    except Exception as e:
        logger.error(f"Chart rendering failed: {e}")
        return json.dumps({"error": f"Failed to render chart: {str(e)}"})
