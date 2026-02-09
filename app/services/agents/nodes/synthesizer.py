"""
Synthesizer Node
Generates the final response by combining search results, RAG context, and citations.
Produces a well-formatted, citation-rich answer using the LLM.
"""

import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
from app.services.agents.state import AgentState, SourceResult, CitationEntry
from app.services.llm_service import get_llm

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You are Nurav AI, an intelligent research assistant. Synthesize a comprehensive answer using the provided sources.

## CITATION RULES - MANDATORY
1. Add inline citations using this EXACT format: 【domain.com】 (use the special brackets 【 and 】)
2. Extract the domain from each source URL
3. Place citations IMMEDIATELY after any fact, claim, or information from a source
4. You can cite multiple sources: "This is true 【source1.com】【source2.com】"
5. ONLY cite when information comes from the provided sources
6. For academic papers, cite using 【arxiv.org】 format

## SOURCE TYPES
- Web sources: General web search results
- Academic sources: Research papers from arXiv (cite as 【arxiv.org】)
- Video sources: YouTube videos with transcripts (cite as 【youtube.com】)
- RAG context: Previously stored relevant information

## FORMATTING RULES
- Use **bold** for key terms and emphasis
- Use `code` for technical terms, commands, or code snippets
- Use ```language for code blocks
- Structure answers with ## headers for different sections
- Use bullet points (-) or numbered lists (1.) for lists
- Use > blockquotes when directly quoting sources
- Keep responses well-organized and easy to read

## IMPORTANT
- Use 【 and 】 brackets (special Unicode characters, NOT regular brackets [ ])
- Be comprehensive but concise
- Synthesize information from multiple source types when available
- If sources don't contain enough information, say so honestly
- Prioritize academic sources for factual claims when available"""


async def synthesize_response_node(state: AgentState) -> dict:
    """
    Synthesize final response from all gathered sources and RAG context.
    Builds citations list and generates a comprehensive response.
    """
    query = state.get("query", "")
    provider = state.get("provider", "google")
    chat_history = state.get("chat_history")
    custom_system = state.get("system_prompt")
    logger.info(f"Synthesizing response for: {query[:100]}")

    # Gather all source results
    web_results = state.get("web_results", [])
    academic_results = state.get("academic_results", [])
    youtube_results = state.get("youtube_results", [])
    rag_context = state.get("rag_context", [])

    # Build citations from all sources
    all_sources = web_results + academic_results + youtube_results
    citations: List[CitationEntry] = []
    for i, source in enumerate(all_sources, 1):
        domain = _extract_domain(source.get("url", ""))
        citations.append({
            "id": i,
            "url": source.get("url", ""),
            "root_url": f"https://{domain}",
            "title": source.get("title", ""),
            "snippet": source.get("snippet", "")[:200],
            "source_type": source.get("source_type", "web"),
            "favicon_url": "",
        })

    # Build context for LLM
    context_parts = []

    if web_results:
        context_parts.append("## Web Sources")
        for i, r in enumerate(web_results, 1):
            domain = _extract_domain(r.get("url", ""))
            context_parts.append(f"""Source [{i}] (Web):
- URL: {r.get("url", "")}
- Domain: {domain}
- Title: {r.get("title", "")}
- Content: {r.get("content", r.get("snippet", ""))[:1500]}
""")

    if academic_results:
        context_parts.append("## Academic Sources")
        for i, r in enumerate(academic_results, 1):
            idx = len(web_results) + i
            authors = ", ".join(r.get("authors", [])[:3])
            context_parts.append(f"""Source [{idx}] (Academic - arXiv):
- Title: {r.get("title", "")}
- Authors: {authors}
- Published: {r.get("published", "")}
- URL: {r.get("url", "")}
- Abstract: {r.get("content", "")[:2000]}
""")

    if youtube_results:
        context_parts.append("## Video Sources")
        for i, r in enumerate(youtube_results, 1):
            idx = len(web_results) + len(academic_results) + i
            context_parts.append(f"""Source [{idx}] (YouTube):
- Title: {r.get("title", "")}
- Channel: {", ".join(r.get("authors", []))}
- URL: {r.get("url", "")}
- Transcript excerpt: {r.get("content", "")[:2000]}
""")

    if rag_context:
        context_parts.append("## Previous Context (from your knowledge base)")
        for i, ctx in enumerate(rag_context, 1):
            context_parts.append(f"""Context [{i}]:
- Source: {ctx.get("source", "knowledge_base")}
- Content: {ctx.get("content", "")[:1000]}
""")

    context_text = "\n".join(context_parts)

    # Build system prompt
    system_prompt = SYNTHESIS_PROMPT
    if custom_system:
        system_prompt = f"{SYNTHESIS_PROMPT}\n\nAdditional instructions: {custom_system}"

    full_prompt = f"{system_prompt}\n\n--- SOURCES ---\n{context_text}\n--- END SOURCES ---"

    # Generate response
    try:
        llm = get_llm(provider, streaming=False)

        # Build message list
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        messages = [SystemMessage(content=full_prompt)]

        # Add chat history if available
        if chat_history:
            for msg in chat_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=query))

        response = await llm.ainvoke(messages)
        response_text = response.content if hasattr(response, "content") else str(response)

        logger.info(f"Synthesis complete: {len(response_text)} chars, {len(citations)} citations")

        return {
            "synthesized_response": response_text,
            "citations": citations,
            "current_phase": "synthesized",
        }

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        # Fallback: return a basic response with available info
        fallback = f"I encountered an error while generating a response: {str(e)}. "
        if citations:
            fallback += "However, I found some relevant sources you may want to check."
        return {
            "synthesized_response": fallback,
            "citations": citations,
            "current_phase": "synthesized",
            "errors": state.get("errors", []) + [f"Synthesis failed: {str(e)}"],
        }


def _extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain or url
    except Exception:
        return url
