"""Agent State Schema — TypedDict shared state read and written by all nodes in the agentic workflow."""

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
    """Shared state passed between all nodes in the agentic workflow."""

    query: str
    user_id: Optional[str]
    mode: Literal["simple", "research", "deep"]
    query_complexity: Literal["simple", "research", "deep"]
    query_intent: str
    query_domains: List[str]
    requires_sources: List[str]
    messages: Annotated[list, add_messages]  # add_messages reducer for proper accumulation
    web_results: List[SourceResult]
    academic_results: List[SourceResult]
    youtube_results: List[SourceResult]
    rag_context: List[Dict]
    citations: List[CitationEntry]
    synthesized_response: Optional[str]
    synthesis_system_prompt: Optional[str]  # prompt built in graph, LLM streaming in endpoint
    synthesis_messages: Optional[List[Dict]]
    current_phase: str
    provider: Optional[str]
    chat_history: Optional[List[Dict]]
    system_prompt: Optional[str]
    start_time: str
    errors: List[str]
