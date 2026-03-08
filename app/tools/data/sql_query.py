"""SQL Query Tool — COMING SOON: Natural language to SQL on uploaded data."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="sql_query",
    description="Convert natural language questions to SQL queries and execute them against uploaded datasets loaded as SQLite tables.",
    niche="data",
    status=ToolStatus.COMING_SOON,
    icon="database",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"question": "What is the average salary by department?", "file_url": "https://example.com/employees.csv"},
            output='{"sql": "SELECT department, AVG(salary) FROM data GROUP BY department", "result": [...], "columns": [...]}',
            description="Query CSV data with natural language",
        ),
    ],
    input_schema={"question": "str", "file_url": "str", "table_name": "str (optional)", "query": "str (optional — raw SQL)"},
    output_schema={"sql": "str", "result": "array", "columns": "array", "rows": "int", "explanation": "str"},
    avg_response_ms=5000,
))
@tool
async def sql_query(question: str, file_url: str = "", table_name: str = "data", query: str = "") -> str:
    """Query data with natural language or SQL. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "SQL query tool is under development. Will use pandas + sqlite3 + LLM for NL-to-SQL."})
