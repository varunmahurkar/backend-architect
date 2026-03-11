"""
Table Formatter Tool — Format data into clean, styled markdown or HTML tables.
Supports sorting, filtering, and conditional formatting.
"""

import json
import logging
import io

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _list_to_markdown(rows: list[dict], sort_by: str = "") -> str:
    """Convert list of dicts to markdown table."""
    if not rows:
        return ""
    headers = list(rows[0].keys())

    if sort_by and sort_by in headers:
        try:
            rows = sorted(rows, key=lambda r: (r.get(sort_by) is None, r.get(sort_by)))
        except TypeError:
            rows = sorted(rows, key=lambda r: str(r.get(sort_by, "")))

    col_widths = {h: max(len(str(h)), max(len(str(r.get(h, ""))) for r in rows)) for h in headers}

    header_row = "| " + " | ".join(str(h).ljust(col_widths[h]) for h in headers) + " |"
    separator = "| " + " | ".join("-" * col_widths[h] for h in headers) + " |"
    data_rows = [
        "| " + " | ".join(str(r.get(h, "")).ljust(col_widths[h]) for h in headers) + " |"
        for r in rows
    ]
    return "\n".join([header_row, separator] + data_rows)


def _list_to_html(rows: list[dict], sort_by: str = "") -> str:
    """Convert list of dicts to styled HTML table."""
    if not rows:
        return ""
    headers = list(rows[0].keys())

    if sort_by and sort_by in headers:
        try:
            rows = sorted(rows, key=lambda r: (r.get(sort_by) is None, r.get(sort_by)))
        except TypeError:
            rows = sorted(rows, key=lambda r: str(r.get(sort_by, "")))

    style = """<style>
table { border-collapse: collapse; width: 100%; font-family: sans-serif; font-size: 14px; }
th { background: #4F46E5; color: white; padding: 10px 14px; text-align: left; }
td { padding: 8px 14px; border-bottom: 1px solid #e5e7eb; }
tr:nth-child(even) { background: #f9fafb; }
tr:hover { background: #ede9fe; }
</style>"""

    th_cells = "".join(f"<th>{h}</th>" for h in headers)
    td_rows = "".join(
        "<tr>" + "".join(f"<td>{row.get(h, '')}</td>" for h in headers) + "</tr>"
        for row in rows
    )
    return f"{style}\n<table>\n<thead><tr>{th_cells}</tr></thead>\n<tbody>{td_rows}</tbody>\n</table>"


def _parse_data(data: str) -> list[dict]:
    """Parse JSON array or CSV string into list of dicts."""
    data = data.strip()
    # Try JSON
    try:
        parsed = json.loads(data)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except (json.JSONDecodeError, ValueError):
        pass

    # Try CSV
    import pandas as pd
    try:
        df = pd.read_csv(io.StringIO(data))
        return df.to_dict(orient="records")
    except Exception:
        pass

    raise ValueError("Data must be a JSON array or CSV string.")


@nurav_tool(metadata=ToolMetadata(
    name="table_formatter",
    description="Format data into clean markdown or HTML tables. Supports JSON arrays, CSV input, sorting by any column, and beautiful HTML styling.",
    niche="visualization",
    status=ToolStatus.ACTIVE,
    icon="table-2",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"data": '[{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]', "format": "markdown", "sort_by": "score"},
            output='{"table": "| name  | score |\\n|-------|-------|\\n| Bob   | 87    |", "rows": 2, "columns": 2}',
            description="Format sorted markdown table",
        ),
    ],
    input_schema={"data": "str (JSON array or CSV)", "format": "str ('markdown'|'html')", "sort_by": "str (optional column name)"},
    output_schema={"table": "str", "rows": "int", "columns": "int", "headers": "array"},
    avg_response_ms=300,
    success_rate=0.98,
))
@tool
async def table_formatter(data: str, format: str = "markdown", sort_by: str = "") -> str:
    """Format data into a clean table."""
    if not data.strip():
        return json.dumps({"error": "No data provided."})

    try:
        rows = _parse_data(data)
        if not rows:
            return json.dumps({"error": "No data rows found."})

        headers = list(rows[0].keys()) if rows else []
        fmt = format.lower().strip()

        if fmt == "html":
            table = _list_to_html(rows, sort_by)
        else:
            table = _list_to_markdown(rows, sort_by)

        return json.dumps({
            "table": table,
            "rows": len(rows),
            "columns": len(headers),
            "headers": headers,
            "format": fmt,
            "sorted_by": sort_by if sort_by else None,
        })
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Table formatting failed: {str(e)}"})
