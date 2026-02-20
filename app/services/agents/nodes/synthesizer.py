"""
Synthesizer Node (Prepare Phase)
Builds the synthesis prompt, citations, and message list but does NOT call the LLM.
The actual LLM streaming happens in the endpoint after the graph completes,
enabling real token-by-token streaming to the client.
"""

import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
from app.services.agents.state import AgentState, SourceResult, CitationEntry

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


async def prepare_synthesis_node(state: AgentState) -> dict:
    """
    Prepare synthesis prompt and citations without calling the LLM.
    Stores system prompt and messages in state for the endpoint to stream.
    """
    query = state.get("query", "")
    chat_history = state.get("chat_history")
    custom_system = state.get("system_prompt")
    logger.info(f"Preparing synthesis for: {query[:100]}")

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

    full_system = f"{system_prompt}\n\n--- SOURCES ---\n{context_text}\n--- END SOURCES ---"

    # Build messages list for LLM (serializable dicts, not LangChain objects)
    messages = [{"role": "system", "content": full_system}]

    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": query})

    logger.info(f"Synthesis prepared: {len(citations)} citations, {len(messages)} messages")

    return {
        "citations": citations,
        "synthesis_system_prompt": full_system,
        "synthesis_messages": messages,
        "current_phase": "synthesized",
    }


def _extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain or url
    except Exception:
        return url
