"""Knowledge Graph Ingest Tool — COMING SOON: Add to user's knowledge graph."""

import json
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample


@nurav_tool(metadata=ToolMetadata(
    name="knowledge_graph_ingest",
    description="Add documents, notes, or conversation context to the user's personal knowledge graph. Extracts entities and relationships automatically.",
    niche="knowledge",
    status=ToolStatus.COMING_SOON,
    icon="plus-circle",
    version="0.1.0",
    examples=[
        ToolExample(
            input={"content": "Machine learning is a subset of AI...", "user_id": "user123", "source_type": "note"},
            output='{"entities_added": 5, "relationships_added": 3, "nodes": [...]}',
            description="Ingest a note into knowledge graph",
        ),
    ],
    input_schema={"content": "str", "user_id": "str", "source_type": "str ('document'|'conversation'|'note')", "metadata": "dict (optional)"},
    output_schema={"entities_added": "int", "relationships_added": "int", "nodes": "array"},
    avg_response_ms=3000,
))
@tool
async def knowledge_graph_ingest(content: str, user_id: str = "", source_type: str = "note") -> str:
    """Ingest content into the knowledge graph. Coming soon."""
    return json.dumps({"status": "coming_soon", "message": "Knowledge graph ingestion is under development. Will use LLM-based entity extraction + NetworkX/Neo4j."})
