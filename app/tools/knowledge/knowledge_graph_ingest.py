"""
Knowledge Graph Ingest Tool — Extract entities & relationships from text and add to user's graph.
Uses LLM for NER + relation extraction, stores in NetworkX (MVP).
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _extract_entities_llm(content: str) -> dict:
    """Use LLM to extract entities and relationships from text."""
    from app.services.llm_service import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    system = """Extract entities and relationships from the text. Respond ONLY with valid JSON:
{
  "entities": [{"name": "entity name", "type": "person|concept|organization|technology|event|location|paper"}],
  "relationships": [{"source": "entity1", "target": "entity2", "relation": "is_a|part_of|related_to|created_by|used_in|authored|studies|published_in"}]
}
Extract the most important 10-20 entities and their relationships. Be specific with entity names."""

    llm = get_llm(provider="google")
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Extract entities and relationships:\n\n{content[:5000]}"),
    ])

    text = response.content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


@nurav_tool(metadata=ToolMetadata(
    name="knowledge_graph_ingest",
    description="Add documents, notes, or conversation context to the user's personal knowledge graph. Automatically extracts entities and relationships using AI.",
    niche="knowledge",
    status=ToolStatus.ACTIVE,
    icon="plus-circle",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"content": "Transformers were introduced by Vaswani et al. in 2017. They use self-attention mechanisms.", "user_id": "user123"},
            output='{"entities_added": 3, "relationships_added": 2, "nodes": [{"id": "Transformers", "type": "technology"}]}',
            description="Ingest a note about Transformers",
        ),
    ],
    input_schema={"content": "str", "user_id": "str", "source_type": "str ('document'|'conversation'|'note')"},
    output_schema={"entities_added": "int", "relationships_added": "int", "nodes": "array"},
    avg_response_ms=3000,
    success_rate=0.90,
))
@tool
async def knowledge_graph_ingest(content: str, user_id: str = "", source_type: str = "note") -> str:
    """Ingest content into the user's knowledge graph by extracting entities and relationships."""
    if not content.strip():
        return json.dumps({"error": "No content provided."})

    uid = user_id or "default"

    try:
        extracted = await _extract_entities_llm(content)
    except Exception as e:
        return json.dumps({"error": f"Entity extraction failed: {str(e)}"})

    # Import and update the shared graph store
    from app.tools.knowledge.knowledge_graph_query import _get_or_create_graph

    graph = _get_or_create_graph(uid)
    entities = extracted.get("entities", [])
    relationships = extracted.get("relationships", [])

    nodes_added = []
    for entity in entities:
        name = entity.get("name", "")
        etype = entity.get("type", "concept")
        if name and not graph.has_node(name):
            graph.add_node(name, type=etype, source=source_type)
            nodes_added.append({"id": name, "type": etype})
        elif name:
            graph.nodes[name]["type"] = etype

    rels_added = 0
    for rel in relationships:
        src = rel.get("source", "")
        tgt = rel.get("target", "")
        relation = rel.get("relation", "related_to")
        if src and tgt:
            if not graph.has_node(src):
                graph.add_node(src, type="concept", source=source_type)
            if not graph.has_node(tgt):
                graph.add_node(tgt, type="concept", source=source_type)
            graph.add_edge(src, tgt, relation=relation)
            rels_added += 1

    return json.dumps({
        "entities_added": len(nodes_added),
        "relationships_added": rels_added,
        "nodes": nodes_added,
        "total_graph_nodes": graph.number_of_nodes(),
        "total_graph_edges": graph.number_of_edges(),
    }, ensure_ascii=False)
