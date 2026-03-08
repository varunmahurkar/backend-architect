"""
CSV Analyzer Tool — Parse, query, and summarize CSV/Excel files.
Uses pandas for data manipulation. Supports statistics, profiling, and natural language queries.
"""

import json
import logging
import io

import httpx
import pandas as pd
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _load_data(file_url: str) -> pd.DataFrame:
    """Download and load CSV/Excel file into a DataFrame."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(file_url)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    data = resp.content

    if file_url.endswith(".xlsx") or file_url.endswith(".xls") or "spreadsheet" in content_type:
        return pd.read_excel(io.BytesIO(data))
    else:
        # Try CSV
        try:
            return pd.read_csv(io.BytesIO(data))
        except Exception:
            # Try with different separators
            return pd.read_csv(io.BytesIO(data), sep=None, engine="python")


def _generate_summary(df: pd.DataFrame) -> dict:
    """Generate a summary of the DataFrame."""
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "sample_rows": json.loads(df.head(5).to_json(orient="records", default_handler=str)),
    }


def _generate_stats(df: pd.DataFrame) -> dict:
    """Generate statistics for numeric columns."""
    numeric_df = df.select_dtypes(include=["number"])
    if numeric_df.empty:
        return {"message": "No numeric columns found."}

    stats = {}
    for col in numeric_df.columns:
        col_data = numeric_df[col].dropna()
        if len(col_data) == 0:
            continue
        stats[col] = {
            "mean": round(float(col_data.mean()), 4),
            "median": round(float(col_data.median()), 4),
            "std": round(float(col_data.std()), 4),
            "min": float(col_data.min()),
            "max": float(col_data.max()),
            "count": int(col_data.count()),
            "unique": int(col_data.nunique()),
        }
    return stats


def _generate_profile(df: pd.DataFrame) -> dict:
    """Generate a data quality profile."""
    total_cells = df.shape[0] * df.shape[1]
    missing_cells = int(df.isnull().sum().sum())

    profile = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "completeness": round((1 - missing_cells / total_cells) * 100, 2) if total_cells > 0 else 100,
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": {},
    }

    for col in df.columns:
        col_info = {
            "dtype": str(df[col].dtype),
            "unique": int(df[col].nunique()),
            "missing": int(df[col].isnull().sum()),
            "missing_pct": round(df[col].isnull().mean() * 100, 2),
        }
        if df[col].dtype in ["object", "string"]:
            col_info["top_values"] = df[col].value_counts().head(5).to_dict()
            col_info["avg_length"] = round(df[col].dropna().astype(str).str.len().mean(), 1)
        profile["columns"][col] = col_info

    return profile


@nurav_tool(metadata=ToolMetadata(
    name="csv_analyzer",
    description="Parse, analyze, and summarize CSV/Excel files. Generates statistics, detects patterns, profiles data quality, and answers questions about tabular data.",
    niche="files",
    status=ToolStatus.ACTIVE,
    icon="table",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"file_url": "https://example.com/data.csv", "operations": "summary,stats"},
            output='{"summary": {"rows": 1000, "columns": 10}, "stats": {"revenue": {"mean": 5000, "median": 4500}}}',
            description="Analyze a CSV file with summary and statistics",
        ),
    ],
    input_schema={"file_url": "str", "operations": "str (comma-separated: summary,stats,profile)", "query": "str (optional)"},
    output_schema={"summary": "dict", "stats": "dict", "profile": "dict"},
    avg_response_ms=3000,
    success_rate=0.90,
))
@tool
async def csv_analyzer(file_url: str, operations: str = "summary,stats", query: str = "") -> str:
    """Analyze a CSV or Excel file. Provide a URL and choose operations: summary, stats, profile."""
    ops = [op.strip().lower() for op in operations.split(",")]

    try:
        df = await _load_data(file_url)
    except httpx.TimeoutException:
        return json.dumps({"error": "Timeout downloading file."})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP error {e.response.status_code} downloading file."})
    except Exception as e:
        return json.dumps({"error": f"Failed to load file: {str(e)}"})

    result = {}

    if "summary" in ops:
        result["summary"] = _generate_summary(df)

    if "stats" in ops:
        result["stats"] = _generate_stats(df)

    if "profile" in ops:
        result["profile"] = _generate_profile(df)

    if query:
        # Simple query: look for column matches
        query_lower = query.lower()
        matching_cols = [c for c in df.columns if query_lower in c.lower()]
        if matching_cols:
            col = matching_cols[0]
            if df[col].dtype in ["object", "string"]:
                result["query_result"] = {
                    "column": col,
                    "unique_values": int(df[col].nunique()),
                    "top_values": df[col].value_counts().head(10).to_dict(),
                }
            else:
                result["query_result"] = {
                    "column": col,
                    "stats": _generate_stats(df[[col]]),
                }
        else:
            result["query_result"] = {"message": f"No column matching '{query}' found. Columns: {list(df.columns)}"}

    return json.dumps(result, ensure_ascii=False, default=str)
