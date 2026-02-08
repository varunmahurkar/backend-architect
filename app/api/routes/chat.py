"""
Chat API routes for LLM interactions.
Supports multiple providers with streaming responses.
Includes agentic workflow endpoints for adaptive query processing.
"""

import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, AsyncGenerator, Dict
from app.api.dependencies.auth import get_current_user, get_optional_user, TokenPayload

logger = logging.getLogger(__name__)
from app.services.llm_service import (
    chat,
    chat_stream,
    get_available_providers,
    LLMProvider,
)
from app.api.models.crawler import (
    CrawlerType,
    Citation,
    CitationList,
    TriggerMode,
    StreamChunk,
)
from app.services.crawler_service import (
    crawl_urls,
    search_and_crawl,
    generate_citations,
    build_context_for_llm,
    agentic_search,
)

router = APIRouter(prefix="/chat", tags=["chat"])


# === Citation System Prompt ===

AGENTIC_SEARCH_PROMPT = """You are Nurav AI, an intelligent search assistant. You have access to web search results to answer user questions accurately.

## YOUR TASK
Analyze the search results provided and give a comprehensive, well-researched answer to the user's question.

## CITATION RULES - MANDATORY
1. Add inline citations using this EXACT format: 【domain.com】 (use the special brackets 【 and 】)
2. Extract the domain from each source URL (e.g., from "https://www.wikipedia.org/wiki/..." use 【wikipedia.org】)
3. Place citations IMMEDIATELY after any fact, claim, or information from a source
4. You can cite multiple sources for one fact: "This is true 【source1.com】【source2.com】"
5. ONLY cite when the information comes from the provided search results
6. Do NOT add citations for your own reasoning or general knowledge

## FORMATTING RULES
- Use **bold** for key terms and emphasis
- Use `code` for technical terms, commands, or code snippets
- Use ```language for code blocks
- Structure answers with ## headers for different sections
- Use bullet points (-) or numbered lists (1.) for lists
- Use > blockquotes when directly quoting sources
- Keep responses well-organized and easy to read

## EXAMPLE
Given a source with URL "https://docs.python.org/3/tutorial/..." and snippet about Python lists:

Your response: "Python lists are mutable sequences 【docs.python.org】. They can contain items of different types and support operations like append and extend 【docs.python.org】."

## IMPORTANT
- Use 【 and 】 brackets (special Unicode characters, NOT regular brackets [ ])
- Be comprehensive but concise
- Synthesize information from multiple sources when relevant
- If search results don't contain enough information, say so honestly"""


# Legacy prompt for RAG approach (kept for backwards compatibility)
CITATION_SYSTEM_PROMPT = """You are Nurav AI, a helpful assistant with access to web search results.

CRITICAL CITATION RULES - YOU MUST FOLLOW THESE:
1. Add inline citations using this EXACT format: 【domain.com】 (use the special brackets 【 and 】)
2. Use the "Domain for citation" value provided with each source (e.g., 【openai.com】, 【wikipedia.org】)
3. Place citations IMMEDIATELY after the sentence or fact you're citing
4. You can cite multiple sources: "This fact 【source1.com】【source2.com】"
5. ALWAYS cite when using information from the provided sources
6. Only omit citations for general knowledge not from sources

FORMATTING RULES - Use rich markdown formatting:
- Use **bold** for emphasis and *italic* for subtle emphasis
- Use `code` for inline code, commands, or technical terms
- Use ```language for code blocks with language specification (e.g., ```python, ```javascript)
- Structure long answers with ## headers for sections
- Use bullet points (-) or numbered lists (1.) for lists of items
- Use > for blockquotes when quoting from sources
- Use tables when comparing multiple items

Example with sources:
If sources include "Domain for citation: openai.com" and "Domain for citation: techcrunch.com"

Your response should be:
"GPT-4 was released by OpenAI in March 2023 【openai.com】. It showed major improvements in reasoning 【techcrunch.com】."

IMPORTANT: Use 【 and 】 brackets (NOT regular brackets). These are special Unicode characters.

The web sources are provided below. Use them to answer accurately with proper citations."""


class ChatMessage(BaseModel):
    """Single chat message."""
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    """Chat request payload."""
    message: str = Field(..., min_length=1, max_length=10000)
    provider: Optional[LLMProvider] = "google"
    chat_history: Optional[list[ChatMessage]] = None
    system_prompt: Optional[str] = None
    stream: bool = False
    # Web search options
    web_search_enabled: bool = Field(default=False, description="Enable Perplexity-style search")
    urls: Optional[List[str]] = Field(None, max_length=10, description="Explicit URLs to crawl")
    crawler_type: CrawlerType = Field(default=CrawlerType.AUTO, description="auto, beautifulsoup, or playwright")
    # Agentic mode options
    mode: Optional[Literal["simple", "research", "deep"]] = Field(None, description="Confirmed query mode")


class ChatResponse(BaseModel):
    """Chat response payload."""
    success: bool
    message: str
    provider: str
    model: Optional[str] = None
    # Citation support
    citations: Optional[CitationList] = None
    trigger_mode: Optional[TriggerMode] = None
    search_query: Optional[str] = Field(None, description="Query used if auto-search was triggered")


class ProvidersResponse(BaseModel):
    """Available providers response."""
    providers: list[dict]


@router.post("/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Send a message to the LLM and get a response.

    - **message**: User message (required)
    - **provider**: LLM provider - google, openai, anthropic (default: google)
    - **chat_history**: Previous messages for context
    - **system_prompt**: Custom system prompt
    - **stream**: Enable streaming (use /chat/stream endpoint instead)
    - **web_search_enabled**: Enable Perplexity-style web search
    - **urls**: Explicit URLs to crawl for context
    - **crawler_type**: auto, beautifulsoup, or playwright
    """
    try:
        trigger_mode = None
        search_query = None
        crawl_result = None

        # Mode 1: Explicit URLs provided
        if request.urls and len(request.urls) > 0:
            trigger_mode = TriggerMode.EXPLICIT_URLS
            crawl_result = await crawl_urls(request.urls, request.crawler_type)

        # Mode 2: Auto-search enabled
        elif request.web_search_enabled:
            trigger_mode = TriggerMode.AUTO_SEARCH
            search_query = request.message
            crawl_result, _ = await search_and_crawl(
                query=request.message,
                max_results=5,
                crawler_type=request.crawler_type,
            )

        # Build context and citations if crawl was performed
        citations = None
        system_prompt = request.system_prompt

        if crawl_result and crawl_result.pages:
            citation_list = generate_citations(crawl_result.pages)
            citations = CitationList(
                citations=citation_list,
                total_count=len(citation_list),
            )

            # Build context with sources for LLM
            context = build_context_for_llm(crawl_result.pages, citation_list)

            # Combine citation prompt with user's system prompt
            base_prompt = CITATION_SYSTEM_PROMPT
            if request.system_prompt:
                base_prompt = f"{CITATION_SYSTEM_PROMPT}\n\nAdditional instructions: {request.system_prompt}"

            system_prompt = f"{base_prompt}\n\n--- WEB SOURCES ---\n{context}\n--- END SOURCES ---"

        # Convert chat history to dict format
        history = None
        if request.chat_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.chat_history]

        response = await chat(
            message=request.message,
            provider=request.provider,
            chat_history=history,
            system_prompt=system_prompt,
        )

        return ChatResponse(
            success=True,
            message=response,
            provider=request.provider or "google",
            citations=citations,
            trigger_mode=trigger_mode,
            search_query=search_query,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}",
        )


def _extract_domain(url: str) -> str:
    """Extract domain from URL for citations."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain
    except:
        return url


def _build_search_context(search_results: List[dict]) -> str:
    """Build context string from search results for LLM."""
    context_parts = []
    for i, result in enumerate(search_results, 1):
        domain = _extract_domain(result.get("url", ""))
        context_parts.append(f"""
Source [{i}]:
- URL: {result.get("url", "")}
- Domain for citation: {domain}
- Title: {result.get("title", "")}
- Content: {result.get("snippet", "")}
""")
    return "\n".join(context_parts)


@router.post("/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Stream a response from the LLM with agentic web search.

    Returns Server-Sent Events (SSE) stream.

    When web_search_enabled=true:
    - type: "status" - Progress phase (searching, generating)
    - type: "citation" - Citation data from search results
    - type: "content" - Response text chunks
    - type: "done" - Stream complete
    - type: "error" - Error occurred
    """
    async def generate() -> AsyncGenerator[str, None]:
        web_mode = request.web_search_enabled
        try:
            search_results = []
            citations = []
            system_prompt = request.system_prompt

            # Agentic search phase
            if request.web_search_enabled:
                # Send "searching" status
                status_chunk = StreamChunk(type="status", status="searching")
                yield f"data: {status_chunk.model_dump_json()}\n\n"

                logger.info(f"Agentic search for: {request.message}")
                search_results = await agentic_search(
                    query=request.message,
                    max_results=20,  # Get top 20 results
                )
                logger.info(f"Search returned {len(search_results)} results")

                # Generate citations from search results
                for i, result in enumerate(search_results, 1):
                    domain = _extract_domain(result.get("url", ""))
                    citation = Citation(
                        id=i,
                        url=result.get("url", ""),
                        root_url=f"https://{domain}",
                        title=result.get("title", ""),
                        snippet=result.get("snippet", ""),
                    )
                    citations.append(citation)

                    # Send citation event
                    chunk = StreamChunk(type="citation", citation=citation)
                    yield f"data: {chunk.model_dump_json()}\n\n"

                logger.info(f"Sent {len(citations)} citations")

                # Build context for LLM from search snippets
                context = _build_search_context(search_results)
                base_prompt = AGENTIC_SEARCH_PROMPT
                if request.system_prompt:
                    base_prompt = f"{AGENTIC_SEARCH_PROMPT}\n\nAdditional instructions: {request.system_prompt}"
                system_prompt = f"{base_prompt}\n\n--- SEARCH RESULTS ---\n{context}\n--- END SEARCH RESULTS ---"

            # Convert chat history
            history = None
            if request.chat_history:
                history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.chat_history
                ]

            # Send "generating" status before LLM streaming starts
            if web_mode:
                status_chunk = StreamChunk(type="status", status="generating")
                yield f"data: {status_chunk.model_dump_json()}\n\n"

            # Stream LLM response
            logger.info(f"Starting LLM stream with provider: {request.provider}")
            chunk_count = 0
            async for text_chunk in chat_stream(
                message=request.message,
                provider=request.provider,
                chat_history=history,
                system_prompt=system_prompt,
            ):
                chunk_count += 1
                if chunk_count <= 3:  # Log first few chunks for debugging
                    logger.info(f"LLM chunk {chunk_count}: {text_chunk[:100] if text_chunk else 'empty'}...")
                # Use StreamChunk format if web search was used, otherwise plain text
                if web_mode:
                    chunk = StreamChunk(type="content", content=text_chunk)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                else:
                    yield f"data: {text_chunk}\n\n"
            logger.info(f"LLM stream completed with {chunk_count} chunks")

            # Signal completion
            if web_mode:
                done_chunk = StreamChunk(type="done")
                yield f"data: {done_chunk.model_dump_json()}\n\n"
            else:
                yield "data: [DONE]\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Stream error: {e}")
            logger.error(traceback.format_exc())
            if web_mode:
                error_chunk = StreamChunk(type="error", error=str(e))
                yield f"data: {error_chunk.model_dump_json()}\n\n"
            else:
                yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers():
    """
    Get list of available LLM providers.

    Returns configured providers with their models.
    """
    providers = get_available_providers()

    if not providers:
        return ProvidersResponse(providers=[{
            "id": "google",
            "name": "Google Gemini",
            "model": "gemini-1.5-pro",
            "available": False,
            "message": "No API keys configured",
        }])

    return ProvidersResponse(providers=providers)


# =============================================================================
# Agentic Workflow Endpoints
# =============================================================================


class ModeSuggestionResponse(BaseModel):
    """Response for query mode suggestion."""
    suggested_mode: Literal["simple", "research", "deep"]
    reasoning: str
    estimated_time: str
    intent: str
    sources: List[str]


@router.post("/suggest-mode", response_model=ModeSuggestionResponse)
async def suggest_query_mode(
    request: ChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Analyze a query and suggest the optimal processing mode.
    Returns suggested complexity level, reasoning, and estimated time.
    Used for hybrid mode triggering (AI suggests, user confirms).
    """
    try:
        from app.services.agents.nodes.analyzer import analyze_query_node

        state = {
            "query": request.message,
            "messages": [],
        }
        analyzed = await analyze_query_node(state)

        complexity = analyzed.get("query_complexity", "simple")
        intent = analyzed.get("query_intent", "factual")
        sources = analyzed.get("requires_sources", ["web"])

        time_estimates = {
            "simple": "< 5 seconds",
            "research": "5-15 seconds",
            "deep": "15-30 seconds",
        }

        reasoning_parts = [f"Detected intent: {intent}"]
        if "arxiv" in sources:
            reasoning_parts.append("academic sources recommended")
        if "youtube" in sources:
            reasoning_parts.append("video content may help")
        if complexity == "research":
            reasoning_parts.append("multiple sources needed for comprehensive answer")
        elif complexity == "deep":
            reasoning_parts.append("complex topic requiring in-depth analysis")

        return ModeSuggestionResponse(
            suggested_mode=complexity,
            reasoning=". ".join(reasoning_parts),
            estimated_time=time_estimates.get(complexity, "< 5 seconds"),
            intent=intent,
            sources=sources,
        )

    except Exception as e:
        logger.error(f"Mode suggestion failed: {e}")
        return ModeSuggestionResponse(
            suggested_mode="simple",
            reasoning="Defaulting to simple mode",
            estimated_time="< 5 seconds",
            intent="factual",
            sources=["web"],
        )


@router.post("/agentic-stream")
async def agentic_chat_stream(
    request: ChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Stream a response using the agentic workflow.
    Processes the query through: analysis -> search -> RAG -> synthesis.

    SSE event types:
    - type: "status" - Processing phase update (analyzing, searching, retrieving, synthesizing)
    - type: "citation" - Citation data from search results
    - type: "content" - Response text chunk
    - type: "mode" - Detected/confirmed query mode
    - type: "done" - Stream complete
    - type: "error" - Error occurred
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            from app.services.agents.graph import get_agent_graph

            graph = get_agent_graph()

            # Build initial state
            initial_state = {
                "query": request.message,
                "user_id": current_user.sub if current_user else None,
                "mode": request.mode,  # None if not user-confirmed
                "messages": [],
                "web_results": [],
                "academic_results": [],
                "youtube_results": [],
                "rag_context": [],
                "citations": [],
                "synthesized_response": None,
                "current_phase": "analyzing",
                "provider": request.provider or "google",
                "chat_history": [
                    {"role": msg.role, "content": msg.content}
                    for msg in (request.chat_history or [])
                ],
                "system_prompt": request.system_prompt,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "errors": [],
            }

            # Send initial status
            yield _sse_event("status", {"status": "analyzing"})

            # Stream through the graph
            config = {"configurable": {"thread_id": f"agentic_{datetime.now(timezone.utc).timestamp()}"}}
            prev_phase = "analyzing"
            citations_sent = set()

            async for event in graph.astream(initial_state, config=config):
                # event is a dict of node outputs keyed by node name
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    # Send phase updates
                    phase = node_output.get("current_phase", "")
                    if phase and phase != prev_phase:
                        phase_labels = {
                            "analyzed": "searching",
                            "searched": "retrieving",
                            "retrieved": "synthesizing",
                            "synthesized": "generating",
                        }
                        display_phase = phase_labels.get(phase, phase)
                        yield _sse_event("status", {"status": display_phase})
                        prev_phase = phase

                    # Send mode detection result
                    if "query_complexity" in node_output:
                        yield _sse_event("mode", {
                            "mode": node_output.get("mode", node_output["query_complexity"]),
                            "intent": node_output.get("query_intent", ""),
                            "sources": node_output.get("requires_sources", []),
                        })

                    # Send citations as they're discovered
                    citations = node_output.get("citations", [])
                    for citation in citations:
                        cit_id = citation.get("id")
                        if cit_id and cit_id not in citations_sent:
                            citations_sent.add(cit_id)
                            yield _sse_event("citation", {"citation": citation})

                    # Stream synthesized response
                    response_text = node_output.get("synthesized_response")
                    if response_text:
                        # Stream in chunks for progressive rendering
                        chunk_size = 50
                        for i in range(0, len(response_text), chunk_size):
                            chunk = response_text[i:i + chunk_size]
                            yield _sse_event("content", {"content": chunk})

            # Signal completion
            yield _sse_event("done", {})

        except Exception as e:
            import traceback
            logger.error(f"Agentic stream error: {e}")
            logger.error(traceback.format_exc())
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event with type field."""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"
