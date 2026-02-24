"""
Query Analyzer Tool — Wraps analyzer.py query classification
Classifies query complexity, intent, domains, and required sources.
"""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="query_analyzer",
    description="Analyze a query to determine its complexity (simple/research/deep), intent, domains, and required sources. Uses LLM classification with heuristic fallbacks.",
    niche="analysis",
    status=ToolStatus.ACTIVE,
    icon="scan-search",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "compare transformer vs LSTM architectures"},
            output='{"complexity": "research", "intent": "comparison", "domains": ["cs"], "sources": ["web", "arxiv"]}',
            description="Analyze a comparison query",
        ),
    ],
    input_schema={"query": "str"},
    output_schema={"complexity": "str", "intent": "str", "domains": "array", "sources": "array"},
    avg_response_ms=500,
    success_rate=0.95,
))
@tool
async def query_analyzer(query: str) -> str:
    """Analyze a query to classify its complexity, intent, domains, and required sources."""
    from app.services.agents.nodes.analyzer import analyze_query_node

    # Build minimal state
    state = {"query": query, "mode": None}
    result = await analyze_query_node(state)

    return json.dumps({
        "complexity": result.get("query_complexity", "simple"),
        "intent": result.get("query_intent", "factual"),
        "domains": result.get("query_domains", ["general"]),
        "sources": result.get("requires_sources", ["web"]),
        "mode": result.get("mode", "simple"),
    }, ensure_ascii=False)
