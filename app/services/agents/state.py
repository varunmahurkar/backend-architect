"""
Agent State Schema
Defines the shared state for the LangGraph agentic workflow.
All nodes read from and write to this state during query processing.
"""

from typing import TypedDict, Annotated, List, Dict, Optional, Literal
from langgraph.graph import add_messages
from datetime import datetime


class SourceResult(TypedDict, total=False):
    """Unified result format from any source (web, arxiv, youtube, etc.)"""
    title: str
    url: str
    snippet: str
    content: str
    source_type: str  # "web", "arxiv", "youtube", "pubmed", "news"
    authors: List[str]
    published: str
    metadata: Dict


class CitationEntry(TypedDict, total=False):
    """Citation reference for the final response"""
    id: int
    url: str
    root_url: str
    title: str
    snippet: str
    source_type: str
    favicon_url: str


class AgentState(TypedDict, total=False):
    """
    Core state for the agentic workflow.

    Flow: query_analyzer -> route -> search nodes -> rag_retrieval -> synthesizer

    Fields:
        query: The original user query
        user_id: Authenticated user ID (for personalized RAG)
        mode: Confirmed complexity mode (simple/research/deep)
        query_complexity: AI-detected complexity level
        query_intent: Classified intent (factual, comparative, tutorial, etc.)
        query_domains: Detected domains (cs, medical, general, etc.)
        requires_sources: Sources needed for this query
        messages: LangGraph message history (with reducer)
        web_results: Search results from DuckDuckGo
        academic_results: Papers from arXiv/PubMed/Scholar
        youtube_results: Video results with transcripts
        rag_context: Retrieved context from vector stores
        citations: Formatted citation references for response
        synthesized_response: Final generated response text
        current_phase: Current processing phase for status updates
        provider: LLM provider to use for generation
        chat_history: Prior conversation context
        system_prompt: Custom system instructions
        start_time: Timestamp when processing began
        errors: Accumulated error messages
    """

    # Query analysis
    query: str
    user_id: Optional[str]
    mode: Literal["simple", "research", "deep"]
    query_complexity: Literal["simple", "research", "deep"]
    query_intent: str
    query_domains: List[str]
    requires_sources: List[str]

    # LangGraph messages (with add_messages reducer for proper accumulation)
    messages: Annotated[list, add_messages]

    # Source results
    web_results: List[SourceResult]
    academic_results: List[SourceResult]
    youtube_results: List[SourceResult]

    # RAG context
    rag_context: List[Dict]

    # Output
    citations: List[CitationEntry]
    synthesized_response: Optional[str]

    # Processing metadata
    current_phase: str
    provider: Optional[str]
    chat_history: Optional[List[Dict]]
    system_prompt: Optional[str]
    start_time: str
    errors: List[str]
