"""
Sentiment Analyzer Tool — LLM-based sentiment and emotion analysis.
Returns sentiment scores, per-sentence breakdown, and emotion detection.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="sentiment_analyzer",
    description="Analyze sentiment and emotional tone of text. Returns overall sentiment, per-sentence breakdown, and detected emotions (joy, anger, sadness, surprise, fear, disgust).",
    niche="analysis",
    status=ToolStatus.ACTIVE,
    icon="smile",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"text": "I love this product! It works amazingly well.", "granularity": "document"},
            output='{"overall": {"sentiment": "positive", "score": 0.95}, "emotions": {"joy": 0.9, "surprise": 0.3}}',
            description="Analyze sentiment of a review",
        ),
    ],
    input_schema={"text": "str", "granularity": "str ('document'|'sentence')", "include_emotions": "bool (default true)"},
    output_schema={"overall": "dict", "sentences": "array", "emotions": "dict"},
    avg_response_ms=2000,
    success_rate=0.95,
))
@tool
async def sentiment_analyzer(text: str, granularity: str = "document", include_emotions: bool = True) -> str:
    """Analyze text sentiment and emotional tone using AI."""
    if not text.strip():
        return json.dumps({"error": "No text provided."})

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        sentence_instruction = ""
        if granularity == "sentence":
            sentence_instruction = '"sentences": [{"text": "...", "sentiment": "positive/negative/neutral", "score": 0.0-1.0}],'

        emotion_instruction = ""
        if include_emotions:
            emotion_instruction = '"emotions": {"joy": 0.0-1.0, "anger": 0.0-1.0, "sadness": 0.0-1.0, "surprise": 0.0-1.0, "fear": 0.0-1.0, "disgust": 0.0-1.0, "trust": 0.0-1.0},'

        system = f"""Analyze the sentiment of the given text. Respond ONLY with valid JSON:
{{
  "overall": {{"sentiment": "positive" | "negative" | "neutral" | "mixed", "score": 0.0-1.0, "subjectivity": 0.0-1.0}},
  {sentence_instruction}
  {emotion_instruction}
  "tone": "descriptive word for the overall tone",
  "summary": "1-sentence description of the emotional content"
}}
Score: 0.0 = most negative, 0.5 = neutral, 1.0 = most positive.
Subjectivity: 0.0 = objective/factual, 1.0 = subjective/opinionated."""

        llm = get_llm(provider="google")
        response = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Analyze sentiment:\n\n{text[:5000]}"),
        ])

        result_text = response.content.strip()
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1])

        result = json.loads(result_text)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Sentiment analysis failed: {str(e)}"})
