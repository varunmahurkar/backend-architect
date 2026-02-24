"""
RAG Retrieval Tool — Wraps vector store retrieval logic
Retrieves relevant context from academic and conversation vector stores.
"""

import json
from typing import Optional
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="rag_retrieval",
    description="Retrieve relevant context from knowledge bases using vector similarity search. Searches academic papers and conversation history.",
    niche="knowledge",
    status=ToolStatus.ACTIVE,
    icon="database",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"query": "neural network optimization techniques"},
            output='[{"content": "...", "source": "academic_rag", "metadata": {...}}]',
            description="Retrieve context about neural network optimization",
        ),
    ],
    input_schema={"query": "str", "user_id": "str (optional)"},
    output_schema={"type": "array", "items": {"content": "str", "source": "str", "metadata": "dict"}},
    avg_response_ms=2000,
    success_rate=0.90,
))
@tool
async def rag_retrieval(query: str, user_id: str = "") -> str:
    """Retrieve relevant context from vector stores for a given query. Returns JSON array of context chunks."""
    from app.services.agents.nodes.retriever import rag_retrieval_node

    # Build a minimal state dict to pass to the node
    state = {"query": query, "user_id": user_id if user_id else None}
    result = await rag_retrieval_node(state)

    rag_context = result.get("rag_context", [])
    return json.dumps(rag_context, ensure_ascii=False, default=str)
