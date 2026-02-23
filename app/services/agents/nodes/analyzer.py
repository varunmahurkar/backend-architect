"""
Query Analyzer Node
Classifies query complexity, intent, and required sources.
Uses Gemini Flash for fast, cost-effective classification (< 500ms target).
"""

import logging
import json
import asyncio
from datetime import datetime
from app.services.agents.state import AgentState
from app.services.llm_service import get_llm
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Classification prompt for fast query analysis
CLASSIFIER_PROMPT = """You are a query classifier for a research assistant. Analyze the user query and return a JSON object.

Rules:
- "simple": Direct factual questions, definitions, quick lookups (< 5s answer)
- "research": Comparisons, multi-faceted topics, requires multiple sources (5-15s answer)
- "deep": Complex analysis, multi-step reasoning, comprehensive review (15-30s answer)

Sources to consider:
- "web": General web search (almost always needed)
- "arxiv": Academic/scientific papers (for research/technical queries)
- "youtube": Video explanations (for tutorials, how-to, visual topics)

Intent types:
- "factual": Simple fact lookup
- "definition": What is X?
- "comparison": Compare X vs Y
- "tutorial": How to do X
- "analysis": Deep analysis of topic
- "opinion": Subjective/discussion
- "current_events": Recent news/events

Return ONLY valid JSON, no other text:
{
  "complexity": "simple" | "research" | "deep",
  "intent": "<intent_type>",
  "domains": ["general", "cs", "medical", "physics", "math", "business", ...],
  "sources": ["web", "arxiv", "youtube"]
}

User query: """


async def analyze_query_node(state: AgentState) -> dict:
    """
    Analyze query to determine complexity, intent, and required sources.
    Uses Gemini Flash for speed and cost efficiency.

    Returns partial state update with classification results.
    """
    query = state.get("query", "")
    logger.info(f"Analyzing query: {query[:100]}...")

    try:
        # Use configured classifier model for fast, cost-effective classification (3s timeout)
        llm = get_llm(settings.classifier_provider, streaming=False, model_override=settings.classifier_model)

        response = await asyncio.wait_for(llm.ainvoke(CLASSIFIER_PROMPT + query), timeout=5.0)
        raw_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from response (handle markdown code blocks)
        json_text = raw_text.strip()
        if json_text.startswith("```"):
            json_text = json_text.split("```")[1]
            if json_text.startswith("json"):
                json_text = json_text[4:]
        json_text = json_text.strip()

        classification = json.loads(json_text)

        complexity = classification.get("complexity", "simple")
        intent = classification.get("intent", "factual")
        domains = classification.get("domains", ["general"])
        sources = classification.get("sources", ["web"])

        # Override mode if user explicitly set it
        mode = state.get("mode", complexity)

        logger.info(f"Classification: complexity={complexity}, intent={intent}, domains={domains}, sources={sources}")

        return {
            "query_complexity": complexity,
            "query_intent": intent,
            "query_domains": domains,
            "requires_sources": sources,
            "mode": mode if mode else complexity,
            "current_phase": "analyzed",
        }

    except asyncio.TimeoutError:
        logger.warning("Classifier LLM timed out after 5s. Falling back to heuristics.")
        return _heuristic_classification(query, state)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse classifier response: {e}. Falling back to heuristics.")
        return _heuristic_classification(query, state)
    except Exception as e:
        logger.error(f"Query analysis failed: {e}. Falling back to heuristics.")
        return _heuristic_classification(query, state)


def _heuristic_classification(query: str, state: AgentState) -> dict:
    """
    Fallback heuristic classifier when LLM classification fails.
    Uses keyword matching and query structure analysis.
    """
    query_lower = query.lower().strip()
    words = query_lower.split()
    word_count = len(words)

    # Complexity heuristics
    complexity = "simple"
    if word_count > 20 or any(kw in query_lower for kw in ["compare", "versus", "vs", "difference between", "pros and cons", "analyze", "explain in detail"]):
        complexity = "research"
    if any(kw in query_lower for kw in ["comprehensive", "in-depth", "literature review", "state of the art", "survey"]):
        complexity = "deep"

    # Intent heuristics
    intent = "factual"
    if query_lower.startswith(("what is", "what are", "define")):
        intent = "definition"
    elif any(kw in query_lower for kw in ["compare", "vs", "versus", "difference"]):
        intent = "comparison"
    elif query_lower.startswith(("how to", "how do", "tutorial", "guide")):
        intent = "tutorial"
    elif any(kw in query_lower for kw in ["analyze", "analysis", "evaluate", "assess"]):
        intent = "analysis"

    # Source heuristics
    sources = ["web"]
    academic_keywords = ["paper", "research", "study", "algorithm", "neural", "machine learning",
                         "deep learning", "transformer", "arxiv", "model", "architecture", "training"]
    if any(kw in query_lower for kw in academic_keywords):
        sources.append("arxiv")

    video_keywords = ["tutorial", "how to", "guide", "demo", "walkthrough", "explain"]
    if any(kw in query_lower for kw in video_keywords):
        sources.append("youtube")

    # Domain heuristics
    domains = ["general"]
    if any(kw in query_lower for kw in ["code", "programming", "python", "javascript", "api", "software", "algorithm"]):
        domains = ["cs"]
    elif any(kw in query_lower for kw in ["health", "medical", "disease", "treatment", "clinical", "patient"]):
        domains = ["medical"]
    elif any(kw in query_lower for kw in ["physics", "quantum", "relativity", "particle"]):
        domains = ["physics"]

    mode = state.get("mode", complexity)

    return {
        "query_complexity": complexity,
        "query_intent": intent,
        "query_domains": domains,
        "requires_sources": sources,
        "mode": mode if mode else complexity,
        "current_phase": "analyzed",
    }
