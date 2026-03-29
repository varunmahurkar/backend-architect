"""
Personalization Node — optional graph node for KG + memory context injection.
Runs only when state["use_personalization"] is True (user opt-in).
Calls knowledge_graph_query + memory_recall tools then stores context in state.
The synthesizer reads personalization_context and user_memory to personalise responses.
"""

import json
import logging
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)


async def personalization_node(state: AgentState) -> dict:
    """Fetch KG subgraph and user memory for the current query.

    Returns empty context if personalization is disabled or user has no history.
    Never raises — personalisation failures are non-fatal."""
    if not state.get("use_personalization"):
        return {"personalization_context": None, "user_memory": None}

    uid = state.get("user_id") or "default"
    query = state.get("query", "")

    personalization_context = None
    user_memory = None

    try:
        from app.tools.knowledge.knowledge_graph_query import knowledge_graph_query
        kg_raw = await knowledge_graph_query.ainvoke({
            "query": query,
            "user_id": uid,
            "max_nodes": 10,
            "depth": 2,
        })
        kg_data = json.loads(kg_raw)
        # Only include if graph is non-empty
        if kg_data.get("total_graph_nodes", 0) > 0:
            personalization_context = {
                "nodes": kg_data.get("nodes", []),
                "edges": kg_data.get("edges", []),
                "context_summary": kg_data.get("context", ""),
            }
        logger.debug(f"[personalization] KG: {kg_data.get('total_graph_nodes', 0)} nodes for uid={uid!r}")
    except Exception as exc:
        logger.debug(f"[personalization] KG query failed (non-fatal): {exc}")

    try:
        from app.tools.knowledge.memory_recall import memory_recall
        mem_raw = await memory_recall.ainvoke({
            "user_id": uid,
            "query": query,
            "memory_type": "all",
        })
        mem_data = json.loads(mem_raw)
        # Only include if there is actual history
        if mem_data.get("interaction_count", 0) > 0 or mem_data.get("recent_topics"):
            user_memory = {
                "preferences": mem_data.get("preferences", {}),
                "recent_topics": mem_data.get("recent_topics", [])[-10:],
                "relevant_topics": mem_data.get("relevant_topics", []),
                "interaction_count": mem_data.get("interaction_count", 0),
            }
        logger.debug(f"[personalization] Memory: {mem_data.get('interaction_count', 0)} interactions for uid={uid!r}")
    except Exception as exc:
        logger.debug(f"[personalization] Memory recall failed (non-fatal): {exc}")

    return {
        "personalization_context": personalization_context,
        "user_memory": user_memory,
        "current_phase": "personalized",
    }
