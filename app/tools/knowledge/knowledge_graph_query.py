"""
Knowledge Graph Query Tool — Query user's personal knowledge graph.
Backed by Supabase (kg_nodes + kg_edges tables) with in-memory NetworkX fallback.
"""

import json
import logging
from typing import Any

import networkx as nx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample, tool_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage backend — Supabase preferred, in-memory fallback
# ---------------------------------------------------------------------------

# In-memory fallback (used when Supabase is not configured)
_user_graphs: dict[str, nx.DiGraph] = {}


def _get_supabase():
    """Return a Supabase admin client or None if not configured."""
    try:
        from app.services.bloom_filter_service import get_supabase_admin_client
        return get_supabase_admin_client()
    except Exception:
        return None


def _get_or_create_graph(user_id: str) -> nx.DiGraph:
    """Get or create an in-memory knowledge graph for a user (fallback)."""
    if user_id not in _user_graphs:
        _user_graphs[user_id] = nx.DiGraph()
    return _user_graphs[user_id]


def _load_graph_from_supabase(user_id: str) -> nx.DiGraph | None:
    """Load a user's knowledge graph from Supabase into an nx.DiGraph.

    Returns None if Supabase is unavailable or tables don't exist yet.
    """
    supabase = _get_supabase()
    if not supabase:
        return None
    try:
        nodes_resp = supabase.table("kg_nodes").select("*").eq("user_id", user_id).execute()
        edges_resp = supabase.table("kg_edges").select("*").eq("user_id", user_id).execute()

        g = nx.DiGraph()
        for row in nodes_resp.data or []:
            props = row.get("properties") or {}
            g.add_node(row["id"], type=row.get("type", "concept"), label=row.get("label", row["id"]), **props)
        for row in edges_resp.data or []:
            g.add_edge(row["source"], row["target"], relation=row.get("relation", "related_to"), weight=row.get("weight", 1.0))
        return g
    except Exception as e:
        logger.warning(f"[knowledge_graph_query] Supabase load failed: {e}, using in-memory fallback")
        return None


def _query_graph(graph: nx.DiGraph, query: str, max_nodes: int, depth: int) -> dict[str, Any]:
    """Search the knowledge graph for relevant nodes and edges."""
    query_lower = query.lower()

    # Find matching nodes (substring match on node names)
    matching = []
    for node, data in graph.nodes(data=True):
        if query_lower in str(node).lower():
            matching.append((node, data))

    if not matching and graph.nodes:
        # If no direct match, return most connected nodes as context
        centrality = nx.degree_centrality(graph) if graph.nodes else {}
        top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
        matching = [(n, graph.nodes[n]) for n, _ in top_nodes]

    # Collect subgraph around matching nodes
    result_nodes = []
    result_edges = []
    visited: set = set()

    for node, data in matching[:max_nodes]:
        if node in visited:
            continue
        visited.add(node)
        result_nodes.append({
            "id": str(node),
            "label": str(node),
            "type": data.get("type", "concept"),
            "properties": {k: v for k, v in data.items() if k != "type"},
        })

        # Get neighbours up to specified depth
        if depth > 0:
            try:
                neighbours = nx.single_source_shortest_path_length(graph, node, cutoff=depth)
                for neighbour, _dist in neighbours.items():
                    if neighbour != node and neighbour not in visited and len(result_nodes) < max_nodes:
                        visited.add(neighbour)
                        ndata = graph.nodes[neighbour]
                        result_nodes.append({
                            "id": str(neighbour),
                            "label": str(neighbour),
                            "type": ndata.get("type", "concept"),
                            "properties": {k: v for k, v in ndata.items() if k != "type"},
                        })
            except nx.NetworkXError:
                pass

    # Collect edges between result nodes (capped at 200)
    node_ids = {n["id"] for n in result_nodes}
    for u, v, data in graph.edges(data=True):
        if len(result_edges) >= 200:
            break
        if str(u) in node_ids and str(v) in node_ids:
            result_edges.append({
                "source": str(u),
                "target": str(v),
                "relation": data.get("relation", "related_to"),
            })

    # Build context string
    context_parts = []
    for node in result_nodes[:10]:
        context_parts.append(f"{node['label']} ({node['type']})")
    for edge in result_edges[:10]:
        context_parts.append(f"{edge['source']} --[{edge['relation']}]--> {edge['target']}")
    context = "; ".join(context_parts) if context_parts else "No relevant knowledge found."

    return {
        "nodes": result_nodes,
        "edges": result_edges,
        "context": context,
        "total_graph_nodes": graph.number_of_nodes(),
        "total_graph_edges": graph.number_of_edges(),
    }


@nurav_tool(metadata=ToolMetadata(
    name="knowledge_graph_query",
    description="Query the user's personal knowledge graph. Finds entities, relationships, and connected concepts from past interactions and documents.",
    niche="knowledge",
    status=ToolStatus.ACTIVE,
    icon="share-2",
    version="1.1.0",
    examples=[
        ToolExample(
            input={"query": "machine learning", "user_id": "user123", "max_nodes": 10},
            output='{"nodes": [...], "edges": [...], "context": "machine learning (concept); ..."}',
            description="Query knowledge graph about machine learning",
        ),
    ],
    input_schema={"query": "str", "user_id": "str", "max_nodes": "int (default 20)", "depth": "int (default 2)"},
    output_schema={"nodes": "array", "edges": "array", "context": "str", "total_graph_nodes": "int", "total_graph_edges": "int"},
    avg_response_ms=500,
    success_rate=0.95,
))
@tool
async def knowledge_graph_query(query: str, user_id: str = "", max_nodes: int = 20, depth: int = 2) -> str:
    """Query the user's personal knowledge graph for entities and relationships."""
    uid = user_id or "default"

    # Try Supabase first, fall back to in-memory
    graph = _load_graph_from_supabase(uid)
    if graph is None:
        graph = _get_or_create_graph(uid)

    if graph.number_of_nodes() == 0:
        return json.dumps({
            "nodes": [],
            "edges": [],
            "context": "Knowledge graph is empty. Interact with the system or upload documents to build your knowledge graph.",
            "total_graph_nodes": 0,
            "total_graph_edges": 0,
            "message": "No knowledge stored yet. Your knowledge graph builds automatically as you interact with Nurav AI.",
        })

    result = _query_graph(graph, query, max_nodes, depth)
    return json.dumps(result, ensure_ascii=False, default=str)
