"""
Knowledge Graph Ingest Tool — Extract entities & relationships from text and add to user's graph.
Uses LLM for NER + relation extraction. Persists to Supabase (kg_nodes/kg_edges) with in-memory fallback.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample, tool_error

logger = logging.getLogger(__name__)


async def _extract_entities_llm(content: str) -> dict:
    """Use LLM to extract entities and relationships from text."""
    from app.services.llm_service import invoke_with_failover
    from langchain_core.messages import HumanMessage

    system = """Extract entities and relationships from the text. Respond ONLY with valid JSON:
{
  "entities": [{"name": "entity name", "type": "person|concept|organization|technology|event|location|paper"}],
  "relationships": [{"source": "entity1", "target": "entity2", "relation": "is_a|part_of|related_to|created_by|used_in|authored|studies|published_in"}]
}
Extract the most important 10-20 entities and their relationships. Be specific with entity names."""

    response = await invoke_with_failover(
        [HumanMessage(content=f"Extract entities and relationships:\n\n{content[:5000]}")],
        system=system,
    )

    text = response.content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def _upsert_to_supabase(user_id: str, entities: list[dict], relationships: list[dict], source_type: str) -> bool:
    """Write nodes and edges to Supabase. Returns True on success."""
    try:
        from app.services.bloom_filter_service import get_supabase_admin_client
        supabase = get_supabase_admin_client()

        # Upsert nodes
        node_rows = [
            {
                "id": e["name"],
                "user_id": user_id,
                "label": e["name"],
                "type": e.get("type", "concept"),
                "properties": {"source": source_type},
            }
            for e in entities if e.get("name")
        ]
        if node_rows:
            supabase.table("kg_nodes").upsert(node_rows, on_conflict="id,user_id").execute()

        # Insert edges (duplicates OK — SERIAL id prevents unique conflicts)
        edge_rows = [
            {
                "user_id": user_id,
                "source": r["source"],
                "target": r["target"],
                "relation": r.get("relation", "related_to"),
                "weight": 1.0,
            }
            for r in relationships if r.get("source") and r.get("target")
        ]
        if edge_rows:
            supabase.table("kg_edges").insert(edge_rows).execute()

        return True
    except Exception as e:
        logger.warning(f"[knowledge_graph_ingest] Supabase write failed: {e}, falling back to in-memory")
        return False


@nurav_tool(metadata=ToolMetadata(
    name="knowledge_graph_ingest",
    description="Add documents, notes, or conversation context to the user's personal knowledge graph. Automatically extracts entities and relationships using AI.",
    niche="knowledge",
    status=ToolStatus.ACTIVE,
    icon="plus-circle",
    version="1.1.0",
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
        return tool_error("No content provided.", "INVALID_INPUT")

    uid = user_id or "default"

    try:
        extracted = await _extract_entities_llm(content)
    except Exception as e:
        return tool_error(f"Entity extraction failed: {str(e)}", "EXTERNAL_API", "Check your LLM provider configuration.")

    entities = extracted.get("entities", [])
    relationships = extracted.get("relationships", [])

    # Try to persist in Supabase first
    supabase_ok = _upsert_to_supabase(uid, entities, relationships, source_type)

    if not supabase_ok:
        # Fall back to in-memory graph
        from app.tools.knowledge.knowledge_graph_query import _get_or_create_graph
        graph = _get_or_create_graph(uid)

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
            "storage": "in_memory",
        }, ensure_ascii=False)

    # Supabase succeeded — count what was added
    nodes_added = [{"id": e["name"], "type": e.get("type", "concept")} for e in entities if e.get("name")]
    return json.dumps({
        "entities_added": len(nodes_added),
        "relationships_added": len([r for r in relationships if r.get("source") and r.get("target")]),
        "nodes": nodes_added,
        "storage": "supabase",
    }, ensure_ascii=False)
