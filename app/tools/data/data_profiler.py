"""
Data Profiler Tool — Comprehensive dataset profiling.
Uses pandas for statistics, distributions, correlations, and data quality scoring.
"""

import json
import logging
import io

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _profile_dataframe(df, sample_size: int = 0) -> dict:
    """Generate a comprehensive profile of a pandas DataFrame."""
    import pandas as pd
    import numpy as np

    if sample_size > 0 and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)

    rows, cols = df.shape
    dtypes = {col: str(df[col].dtype) for col in df.columns}

    # Per-column stats
    column_stats = {}
    for col in df.columns:
        col_data = df[col]
        missing = int(col_data.isna().sum())
        unique = int(col_data.nunique())
        stats = {
            "dtype": str(col_data.dtype),
            "missing": missing,
            "missing_pct": round(missing / rows * 100, 2),
            "unique": unique,
            "unique_pct": round(unique / rows * 100, 2),
        }

        if pd.api.types.is_numeric_dtype(col_data):
            desc = col_data.describe()
            stats.update({
                "mean": round(float(desc.get("mean", 0)), 4),
                "std": round(float(desc.get("std", 0)), 4),
                "min": round(float(desc.get("min", 0)), 4),
                "25%": round(float(desc.get("25%", 0)), 4),
                "median": round(float(desc.get("50%", 0)), 4),
                "75%": round(float(desc.get("75%", 0)), 4),
                "max": round(float(desc.get("max", 0)), 4),
                "skewness": round(float(col_data.skew()), 4),
                "kurtosis": round(float(col_data.kurtosis()), 4),
            })
            # Outlier detection via IQR
            q1, q3 = col_data.quantile(0.25), col_data.quantile(0.75)
            iqr = q3 - q1
            outliers = int(((col_data < q1 - 1.5 * iqr) | (col_data > q3 + 1.5 * iqr)).sum())
            stats["outliers"] = outliers
        else:
            top_values = col_data.value_counts().head(5).to_dict()
            stats["top_values"] = {str(k): int(v) for k, v in top_values.items()}

        column_stats[col] = stats

    # Correlation matrix (numeric only)
    numeric_cols = df.select_dtypes(include=[float, int]).columns.tolist()
    correlations = {}
    if len(numeric_cols) >= 2:
        corr_matrix = df[numeric_cols].corr()
        # Only keep strong correlations (|r| > 0.5)
        strong = {}
        for i, c1 in enumerate(numeric_cols):
            for j, c2 in enumerate(numeric_cols):
                if i < j:
                    r = corr_matrix.loc[c1, c2]
                    if not pd.isna(r) and abs(r) > 0.5:
                        strong[f"{c1}↔{c2}"] = round(float(r), 3)
        correlations = strong

    # Data quality score
    total_cells = rows * cols
    missing_cells = sum(stats["missing"] for stats in column_stats.values())
    missing_pct = missing_cells / max(total_cells, 1)

    duplicate_rows = int(df.duplicated().sum())
    dup_pct = duplicate_rows / max(rows, 1)

    quality_score = round((1 - missing_pct * 0.5 - dup_pct * 0.3) * 100, 1)
    quality_score = max(0, min(100, quality_score))

    quality_issues = []
    if missing_pct > 0.1:
        quality_issues.append(f"High missing data: {round(missing_pct*100, 1)}% of cells")
    if dup_pct > 0.05:
        quality_issues.append(f"Duplicate rows: {duplicate_rows} ({round(dup_pct*100,1)}%)")
    for col, stats in column_stats.items():
        if stats["missing_pct"] > 30:
            quality_issues.append(f"Column '{col}' has {stats['missing_pct']}% missing values")

    return {
        "rows": rows,
        "columns": cols,
        "dtypes": dtypes,
        "column_stats": column_stats,
        "correlations": correlations,
        "duplicate_rows": duplicate_rows,
        "quality_score": quality_score,
        "quality_issues": quality_issues,
        "memory_usage_kb": round(df.memory_usage(deep=True).sum() / 1024, 2),
    }


@nurav_tool(metadata=ToolMetadata(
    name="data_profiler",
    description="Profile datasets comprehensively. Generates per-column statistics, distributions, outlier detection, correlation analysis, and a data quality score. Supports CSV, JSON, and Excel.",
    niche="data",
    status=ToolStatus.ACTIVE,
    icon="bar-chart-horizontal",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"file_url": "https://example.com/data.csv", "format": "csv"},
            output='{"rows": 1000, "columns": 10, "quality_score": 92.5, "correlations": {...}}',
            description="Profile a CSV dataset",
        ),
    ],
    input_schema={"file_url": "str (URL or inline CSV/JSON)", "format": "str ('csv'|'json'|'excel')", "sample_size": "int (0=all rows)"},
    output_schema={"rows": "int", "columns": "int", "dtypes": "dict", "column_stats": "dict", "correlations": "dict", "quality_score": "float"},
    avg_response_ms=5000,
    success_rate=0.92,
))
@tool
async def data_profiler(file_url: str, format: str = "csv", sample_size: int = 0) -> str:
    """Profile a dataset comprehensively."""
    if not file_url.strip():
        return json.dumps({"error": "No file URL or data provided."})

    try:
        import pandas as pd

        # Get data
        if file_url.startswith("http"):
            import httpx
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(file_url)
                resp.raise_for_status()
                data = resp.content
        else:
            data = file_url.encode("utf-8")

        fmt = format.lower().strip()
        if fmt == "csv":
            df = pd.read_csv(io.BytesIO(data))
        elif fmt == "json":
            df = pd.read_json(io.BytesIO(data))
        elif fmt in ("excel", "xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(data))
        else:
            # Try to auto-detect
            try:
                df = pd.read_csv(io.BytesIO(data))
            except Exception:
                df = pd.read_json(io.BytesIO(data))

        profile = _profile_dataframe(df, sample_size)
        profile["format"] = fmt
        profile["sampled"] = sample_size > 0 and len(df) > sample_size
        return json.dumps(profile, default=str)

    except Exception as e:
        return json.dumps({"error": f"Data profiling failed: {str(e)}"})
