"""
Crawler API routes for web crawling and citation-based chat.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, AsyncGenerator

from app.api.dependencies.auth import get_optional_user, TokenPayload
from app.api.models.crawler import (
    CrawlRequest,
    CrawlResponse,
    SearchAndCrawlRequest,
    WebChatRequest,
    WebChatResponse,
    CitationList,
    TriggerMode,
    StreamChunk,
)
from app.services.crawler_service import (
    crawl_urls,
    search_and_crawl,
    generate_citations,
    build_context_for_llm,
)
from app.services.llm_service import chat, chat_stream

router = APIRouter(prefix="/crawler", tags=["crawler"])


# === Citation System Prompt ===

CITATION_SYSTEM_PROMPT = """You are Nurav AI, a helpful assistant with access to web search results.

IMPORTANT CITATION RULES:
1. Use inline citations in the format [1], [2], etc. to reference sources
2. Place citations immediately after the relevant information
3. You can cite multiple sources for the same fact: [1][3]
4. Only cite sources that are actually relevant to your statement
5. If information is not from the provided sources, don't add a citation
6. Always base your response on the provided source content

Example response format:
"Python was created by Guido van Rossum [1] and first released in 1991 [2]. It emphasizes code readability [1][3]."

The web sources are provided below. Use them to answer the user's question accurately with proper citations."""


@router.post("/crawl", response_model=CrawlResponse)
async def crawl_endpoint(
    request: CrawlRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Crawl specific URLs.

    - **urls**: List of URLs to crawl (max 10)
    - **crawler_type**: auto, beautifulsoup, or playwright
    """
    try:
        result = await crawl_urls(
            urls=request.urls,
            crawler_type=request.crawler_type,
        )
        return CrawlResponse(success=True, result=result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crawl failed: {str(e)}",
        )


@router.post("/search-and-crawl", response_model=CrawlResponse)
async def search_and_crawl_endpoint(
    request: SearchAndCrawlRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Search web and crawl top results (Perplexity-style).

    - **query**: Search query
    - **max_results**: Number of results to crawl (1-10)
    - **search_engine**: duckduckgo (default)
    """
    try:
        result, urls = await search_and_crawl(
            query=request.query,
            max_results=request.max_results,
            crawler_type=request.crawler_type,
            search_engine=request.search_engine,
        )
        return CrawlResponse(success=True, result=result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search and crawl failed: {str(e)}",
        )


@router.post("/chat", response_model=WebChatResponse)
async def web_chat_endpoint(
    request: WebChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Chat with web crawling and citations.

    Two modes:
    1. **Explicit URLs**: Provide urls[] to crawl specific pages
    2. **Auto-search**: Set web_search_enabled=true for Perplexity-style search

    Response includes:
    - message: LLM response with [1], [2] citation markers
    - citations: Structured citation data for frontend rendering
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
            search_query = request.message  # Use message as search query
            crawl_result, _ = await search_and_crawl(
                query=request.message,
                max_results=5,
                crawler_type=request.crawler_type,
            )

        # Build context and citations if crawl was performed
        citations = CitationList()
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
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.chat_history
            ]

        # Call LLM
        response = await chat(
            message=request.message,
            provider=request.provider,
            chat_history=history,
            system_prompt=system_prompt,
        )

        return WebChatResponse(
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
            detail=f"Web chat failed: {str(e)}",
        )


@router.post("/chat/stream")
async def web_chat_stream_endpoint(
    request: WebChatRequest,
    current_user: Optional[TokenPayload] = Depends(get_optional_user),
):
    """
    Stream chat response with web crawling and citations.

    Returns Server-Sent Events (SSE) stream with:
    - type: "citation" - Citation data (sent first)
    - type: "content" - Response text chunks
    - type: "done" - Stream complete
    - type: "error" - Error occurred
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            trigger_mode = None
            crawl_result = None

            # Crawl phase
            if request.urls and len(request.urls) > 0:
                trigger_mode = TriggerMode.EXPLICIT_URLS
                crawl_result = await crawl_urls(request.urls, request.crawler_type)
            elif request.web_search_enabled:
                trigger_mode = TriggerMode.AUTO_SEARCH
                crawl_result, _ = await search_and_crawl(
                    query=request.message,
                    max_results=5,
                    crawler_type=request.crawler_type,
                )

            # Send citations first
            citations = []
            system_prompt = request.system_prompt

            if crawl_result and crawl_result.pages:
                citations = generate_citations(crawl_result.pages)

                # Send each citation as SSE event
                for citation in citations:
                    chunk = StreamChunk(type="citation", citation=citation)
                    yield f"data: {chunk.model_dump_json()}\n\n"

                # Build context for LLM
                context = build_context_for_llm(crawl_result.pages, citations)
                base_prompt = CITATION_SYSTEM_PROMPT
                if request.system_prompt:
                    base_prompt = f"{CITATION_SYSTEM_PROMPT}\n\nAdditional instructions: {request.system_prompt}"
                system_prompt = f"{base_prompt}\n\n--- WEB SOURCES ---\n{context}\n--- END SOURCES ---"

            # Convert chat history
            history = None
            if request.chat_history:
                history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.chat_history
                ]

            # Stream LLM response
            async for text_chunk in chat_stream(
                message=request.message,
                provider=request.provider,
                chat_history=history,
                system_prompt=system_prompt,
            ):
                chunk = StreamChunk(type="content", content=text_chunk)
                yield f"data: {chunk.model_dump_json()}\n\n"

            # Signal completion
            done_chunk = StreamChunk(type="done")
            yield f"data: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:
            error_chunk = StreamChunk(type="error", error=str(e))
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
