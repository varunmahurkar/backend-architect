"""Response Quality Validator — non-blocking relevance check; results are logged only, never surfaced to users."""

import logging
import json
import asyncio
from typing import Dict
from app.services.llm_service import get_llm
from app.config.settings import settings

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are a quality checker. Given a user query and an AI response, determine if the response adequately addresses the query.

Return ONLY valid JSON:
{{"relevant": true/false, "reason": "brief explanation"}}

User query: {query}

Response (first 500 chars): {response}"""


async def validate_response(query: str, response_text: str) -> Dict:
    """Check if a response addresses the query. Returns {relevant, reason}; defaults to relevant=True on error."""
    try:
        llm = get_llm(
            settings.classifier_provider,
            streaming=False,
            model_override=settings.classifier_model,
        )

        prompt = VALIDATION_PROMPT.format(
            query=query,
            response=response_text[:500],
        )

        result = await asyncio.wait_for(llm.ainvoke(prompt), timeout=3.0)
        raw_text = result.content if hasattr(result, "content") else str(result)

        json_text = raw_text.strip()
        if json_text.startswith("```"):
            json_text = json_text.split("```")[1]
            if json_text.startswith("json"):
                json_text = json_text[4:]
        json_text = json_text.strip()

        validation = json.loads(json_text)
        relevant = validation.get("relevant", True)
        reason = validation.get("reason", "")

        if not relevant:
            logger.warning(f"Response validation FAILED for query '{query[:50]}...': {reason}")
        else:
            logger.info(f"Response validation passed for query '{query[:50]}...'")

        return {"relevant": relevant, "reason": reason}

    except asyncio.TimeoutError:
        logger.warning("Response validation timed out after 3s")
        return {"relevant": True, "reason": "validation_timeout"}
    except Exception as e:
        logger.warning(f"Response validation error: {e}")
        return {"relevant": True, "reason": f"validation_error: {e}"}
