"""
Agent Graph
LangGraph state machine that orchestrates the agentic workflow.
Routes queries through analysis -> search -> RAG -> synthesis pipeline.
"""

import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.services.agents.state import AgentState
from app.services.agents.nodes.analyzer import analyze_query_node
from app.services.agents.nodes.searcher import simple_search_node, research_search_node
from app.services.agents.nodes.retriever import rag_retrieval_node
from app.services.agents.nodes.synthesizer import synthesize_response_node

logger = logging.getLogger(__name__)


def route_by_complexity(state: AgentState) -> str:
    """
    Route to appropriate search strategy based on detected complexity.
    Simple queries get fast web search, research queries get parallel multi-source.
    """
    mode = state.get("mode", state.get("query_complexity", "simple"))
    logger.info(f"Routing query with mode: {mode}")

    if mode == "research" or mode == "deep":
        return "research_search"
    return "simple_search"


def create_agent_graph():
    """
    Create and compile the LangGraph agentic workflow.

    Graph structure:
        query_analyzer -> [simple_search | research_search] -> rag_retrieval -> synthesizer -> END

    Returns compiled graph with in-memory checkpointing.
    """
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node("query_analyzer", analyze_query_node)
    workflow.add_node("simple_search", simple_search_node)
    workflow.add_node("research_search", research_search_node)
    workflow.add_node("rag_retrieval", rag_retrieval_node)
    workflow.add_node("synthesizer", synthesize_response_node)

    # Set entry point
    workflow.set_entry_point("query_analyzer")

    # Conditional routing based on complexity
    workflow.add_conditional_edges(
        "query_analyzer",
        route_by_complexity,
        {
            "simple_search": "simple_search",
            "research_search": "research_search",
        },
    )

    # Both search paths lead to RAG retrieval, then synthesis
    workflow.add_edge("simple_search", "rag_retrieval")
    workflow.add_edge("research_search", "rag_retrieval")
    workflow.add_edge("rag_retrieval", "synthesizer")
    workflow.add_edge("synthesizer", END)

    # Compile with in-memory checkpointing for conversation persistence
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
