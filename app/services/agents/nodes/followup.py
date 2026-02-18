"""
Follow-up Questions Generator
Generates 3 related follow-up questions after a response using gpt-4o-mini.
Fast and cheap (~100 tokens). 3s timeout, gracefully skips on failure.
"""

import logging
import json
import asyncio
from typing import List
from app.services.llm_service import get_llm
from app.config.settings import settings

logger = logging.getLogger(__name__)

FOLLOWUP_PROMPT = """Given this user query and the response summary, generate exactly 3 short follow-up questions the user might want to ask next. Return ONLY a JSON array of 3 strings, no other text.

User query: {query}

Response topics: {topics}

Return format: ["question 1?", "question 2?", "question 3?"]"""


async def generate_followup_questions(query: str, response_text: str) -> List[str]:
    """
    Generate 3 follow-up question suggestions.
    Uses gpt-4o-mini for speed and cost. 3s timeout, returns empty on failure.
    """
    try:
        # Extract first 500 chars as topic summary
        topics = response_text[:500] if response_text else query

        llm = get_llm(
            settings.classifier_provider,
            streaming=False,
            model_override=settings.classifier_model,
        )

        prompt = FOLLOWUP_PROMPT.format(query=query, topics=topics)
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=3.0)

        raw_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON array
        json_text = raw_text.strip()
        if json_text.startswith("```"):
            json_text = json_text.split("```")[1]
            if json_text.startswith("json"):
                json_text = json_text[4:]
        json_text = json_text.strip()

        questions = json.loads(json_text)

        if isinstance(questions, list) and len(questions) >= 3:
            return [str(q) for q in questions[:3]]

        logger.warning(f"Unexpected followup format: {questions}")
        return []

    except asyncio.TimeoutError:
        logger.warning("Follow-up generation timed out after 3s")
        return []
    except Exception as e:
        logger.warning(f"Follow-up generation failed: {e}")
        return []
