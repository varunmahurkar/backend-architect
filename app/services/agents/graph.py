"""
Agent Graph
LangGraph state machine that orchestrates the agentic workflow.
Pipeline: query_analyzer → [simple_search|research_search] → [rag_retrieval ∥ personalization] → prepare_synthesis → END
Personalization node runs in parallel with RAG when use_personalization=True.
"""

import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.services.agents.state import AgentState
from app.services.agents.nodes.analyzer import analyze_query_node
from app.services.agents.nodes.searcher import simple_search_node, research_search_node
from app.services.agents.nodes.retriever import rag_retrieval_node
from app.services.agents.nodes.synthesizer import prepare_synthesis_node
from app.services.agents.nodes.personalization import personalization_node

logger = logging.getLogger(__name__)


def route_by_complexity(state: AgentState) -> str:
    """Route to simple_search or research_search based on query complexity mode."""
    mode = state.get("mode", state.get("query_complexity", "simple"))
    logger.info(f"Routing query with mode: {mode}")

    if mode == "research" or mode == "deep":
        return "research_search"
    return "simple_search"


async def rag_and_personalization_node(state: AgentState) -> dict:
    """Run RAG retrieval and personalization in parallel using asyncio.gather.
    Merges both outputs so prepare_synthesis has full context."""
    import asyncio
    rag_task = asyncio.create_task(rag_retrieval_node(state))
    pers_task = asyncio.create_task(personalization_node(state))
    rag_result, pers_result = await asyncio.gather(rag_task, pers_task, return_exceptions=True)

    merged: dict = {}
    if isinstance(rag_result, dict):
        merged.update(rag_result)
    else:
        logger.warning(f"RAG node error (non-fatal): {rag_result}")

    if isinstance(pers_result, dict):
        merged.update(pers_result)
    else:
        logger.debug(f"Personalization node error (non-fatal): {pers_result}")

    return merged


def create_agent_graph():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("query_analyzer", analyze_query_node)
    workflow.add_node("simple_search", simple_search_node)
    workflow.add_node("research_search", research_search_node)
    workflow.add_node("rag_and_personalization", rag_and_personalization_node)
    workflow.add_node("prepare_synthesis", prepare_synthesis_node)

    workflow.set_entry_point("query_analyzer")

    workflow.add_conditional_edges(
        "query_analyzer",
        route_by_complexity,
        {
            "simple_search": "simple_search",
            "research_search": "research_search",
        },
    )

    workflow.add_edge("simple_search", "rag_and_personalization")
    workflow.add_edge("research_search", "rag_and_personalization")
    workflow.add_edge("rag_and_personalization", "prepare_synthesis")
    workflow.add_edge("prepare_synthesis", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# Singleton graph instance (reused across requests)
_agent_graph = None


def get_agent_graph():
    """Get or create the singleton agent graph instance."""
    global _agent_graph
    if _agent_graph is None:
        logger.info("Creating agent graph...")
        _agent_graph = create_agent_graph()
        logger.info("Agent graph created successfully")
    return _agent_graph
