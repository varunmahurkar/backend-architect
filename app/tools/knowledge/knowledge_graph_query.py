"""
Knowledge Graph Query Tool — Query user's personal knowledge graph.
MVP: In-memory NetworkX graph. Finds entities, relationships, and connected concepts.
"""

import json
import logging
from typing import Any

import networkx as nx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

# In-memory knowledge graphs per user (MVP — will move to Neo4j/pgvector later)
_user_graphs: dict[str, nx.DiGraph] = {}


def _get_or_create_graph(user_id: str) -> nx.DiGraph:
    """Get or create a knowledge graph for a user."""
    if user_id not in _user_graphs:
        _user_graphs[user_id] = nx.DiGraph()
    return _user_graphs[user_id]


def _add_knowledge(graph: nx.DiGraph, entity: str, entity_type: str = "concept", properties: dict | None = None):
    """Add an entity node to the graph."""
    graph.add_node(entity, type=entity_type, **(properties or {}))


def _add_relationship(graph: nx.DiGraph, source: str, target: str, relation: str):
    """Add a relationship edge to the graph."""
    if not graph.has_node(source):
        graph.add_node(source, type="concept")
    if not graph.has_node(target):
        graph.add_node(target, type="concept")
    graph.add_edge(source, target, relation=relation)


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
    visited = set()

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

        # Get neighbors up to specified depth
        if depth > 0:
            try:
                neighbors = nx.single_source_shortest_path_length(graph, node, cutoff=depth)
                for neighbor, dist in neighbors.items():
                    if neighbor != node and neighbor not in visited and len(result_nodes) < max_nodes:
                        visited.add(neighbor)
                        ndata = graph.nodes[neighbor]
                        result_nodes.append({
                            "id": str(neighbor),
                            "label": str(neighbor),
                            "type": ndata.get("type", "concept"),
                            "properties": {k: v for k, v in ndata.items() if k != "type"},
                        })
            except nx.NetworkXError:
                pass

    # Collect edges between result nodes
    node_ids = {n["id"] for n in result_nodes}
    for u, v, data in graph.edges(data=True):
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
    version="1.0.0",
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
