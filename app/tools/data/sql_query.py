"""
SQL Query Tool — Natural language to SQL on uploaded datasets.
Loads CSV/JSON into SQLite in-memory, generates SQL with LLM, executes it.
"""

import json
import logging
import io
import sqlite3

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _load_dataframe(file_url: str, format_hint: str = "csv"):
    """Load data from URL or inline content into a pandas DataFrame."""
    import pandas as pd

    if file_url.startswith("http"):
        import httpx
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(file_url)
            resp.raise_for_status()
            data = resp.content
    else:
        data = file_url.encode("utf-8")

    url_lower = file_url.lower()
    if url_lower.endswith(".json") or format_hint == "json":
        return pd.read_json(io.BytesIO(data))
    elif url_lower.endswith((".xlsx", ".xls")) or format_hint == "excel":
        return pd.read_excel(io.BytesIO(data))
    else:
        return pd.read_csv(io.BytesIO(data))


def _df_to_sqlite(df, table_name: str = "data") -> sqlite3.Connection:
    """Load a DataFrame into an in-memory SQLite database."""
    import pandas as pd

    conn = sqlite3.connect(":memory:")
    # Clean column names
    df.columns = [str(c).strip().replace(" ", "_").replace("-", "_").replace(".", "_").lower() for c in df.columns]
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    return conn


def _get_table_schema(conn: sqlite3.Connection, table_name: str) -> str:
    """Get table schema as a string for LLM context."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return ", ".join(f"{col[1]} {col[2]}" for col in columns)


@nurav_tool(metadata=ToolMetadata(
    name="sql_query",
    description="Query datasets using natural language or raw SQL. Loads CSV/JSON into SQLite in-memory, generates SQL with LLM, executes and returns results with the generated SQL for transparency.",
    niche="data",
    status=ToolStatus.ACTIVE,
    icon="database",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"question": "What is the average salary by department?", "file_url": "https://example.com/employees.csv"},
            output='{"sql": "SELECT department, AVG(salary) FROM data GROUP BY department", "result": [...], "columns": [...]}',
            description="Query CSV data with natural language",
        ),
    ],
    input_schema={"question": "str (natural language)", "file_url": "str (CSV/JSON URL or inline CSV)", "table_name": "str (default 'data')", "query": "str (optional raw SQL)"},
    output_schema={"sql": "str", "result": "array", "columns": "array", "rows": "int", "explanation": "str"},
    avg_response_ms=6000,
    success_rate=0.88,
))
@tool
async def sql_query(question: str, file_url: str = "", table_name: str = "data", query: str = "") -> str:
    """Query data with natural language or SQL."""
    if not question.strip() and not query.strip():
        return json.dumps({"error": "Provide either a question or a raw SQL query."})
    if not file_url.strip():
        return json.dumps({"error": "No file URL or data provided."})

    try:
        # Load data
        df = await _load_dataframe(file_url)
        conn = _df_to_sqlite(df, table_name)
        schema = _get_table_schema(conn, table_name)

        # Generate SQL from natural language if not provided
        sql = query.strip()
        if not sql and question.strip():
            try:
                from app.services.llm_service import get_llm
                from langchain_core.messages import HumanMessage, SystemMessage

                system = f"""You are an expert SQL query generator.
Table name: {table_name}
Schema: {schema}
SQLite dialect. Generate only the SQL SELECT query (no explanation, no markdown).
The query must be safe — only SELECT statements allowed."""

                llm = get_llm(provider="google")
                resp = await llm.ainvoke([
                    SystemMessage(content=system),
                    HumanMessage(content=f"Question: {question}"),
                ])
                sql = resp.content.strip()
                # Strip markdown if present
                if sql.startswith("```"):
                    lines = sql.split("\n")
                    sql = "\n".join(lines[1:-1])
                sql = sql.strip().rstrip(";")
            except Exception as e:
                return json.dumps({"error": f"SQL generation failed: {str(e)}", "schema": schema})

        # Safety check — only allow SELECT
        if not sql.strip().upper().startswith("SELECT"):
            return json.dumps({"error": "Only SELECT queries are allowed.", "generated_sql": sql})

        # Execute
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchmany(500)  # Limit results
        result = [dict(zip(columns, row)) for row in rows]

        # Generate explanation
        explanation = ""
        if question.strip():
            try:
                from app.services.llm_service import get_llm
                from langchain_core.messages import HumanMessage, SystemMessage
                llm = get_llm(provider="google")
                resp = await llm.ainvoke([
                    SystemMessage(content="Briefly explain in 1-2 sentences what this SQL query does and what the results mean."),
                    HumanMessage(content=f"Question: {question}\nSQL: {sql}\nResult preview: {str(result[:3])}"),
                ])
                explanation = resp.content.strip()
            except Exception:
                pass

        conn.close()
        return json.dumps({
            "sql": sql,
            "result": result,
            "columns": columns,
            "rows": len(result),
            "explanation": explanation,
            "schema": schema,
            "question": question,
        }, default=str)

    except sqlite3.Error as e:
        return json.dumps({"error": f"SQL execution failed: {str(e)}", "sql": sql if 'sql' in locals() else ""})
    except Exception as e:
        return json.dumps({"error": f"Query failed: {str(e)}"})
