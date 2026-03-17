"""
Paraphraser Tool — Rewrite text in different tones, styles, or complexity levels.
LLM-powered with multiple variation support.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

TONE_INSTRUCTIONS = {
    "formal": "Rewrite in a formal, professional tone. Use sophisticated vocabulary, complete sentences, and avoid contractions.",
    "casual": "Rewrite in a friendly, conversational tone. Use simple words, contractions, and a relaxed style.",
    "academic": "Rewrite in an academic scholarly tone. Use precise terminology, passive voice where appropriate, and citation-ready phrasing.",
    "simple": "Rewrite in simple, easy-to-understand language. Use short sentences, common words, and avoid jargon.",
    "technical": "Rewrite with technical precision. Use domain-specific terminology and exact language.",
    "persuasive": "Rewrite with persuasive language. Use strong verbs, rhetorical devices, and compelling framing.",
    "creative": "Rewrite with creative flair. Use vivid language, metaphors, and engaging style.",
    "concise": "Rewrite as concisely as possible. Remove all redundancy while preserving core meaning.",
}


@nurav_tool(metadata=ToolMetadata(
    name="paraphraser",
    description="Rewrite text in different tones, styles, or complexity levels. Supports formal, casual, academic, simple, technical, persuasive, creative, and concise styles.",
    niche="language",
    status=ToolStatus.ACTIVE,
    icon="pen-line",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"text": "The experiment yielded statistically significant results.", "tone": "simple", "variations": 2},
            output='{"paraphrased": ["The experiment gave important results.", "The test worked really well."], "original_length": 55, "tone": "simple"}',
            description="Simplify academic text",
        ),
    ],
    input_schema={"text": "str", "tone": "str ('formal'|'casual'|'academic'|'simple'|'technical'|'persuasive'|'creative'|'concise')", "variations": "int (default 1, max 3)"},
    output_schema={"paraphrased": "array", "original_tone": "str", "target_tone": "str", "similarity_note": "str"},
    avg_response_ms=2500,
    success_rate=0.95,
))
@tool
async def paraphraser(text: str, tone: str = "casual", variations: int = 1) -> str:
    """Rewrite text in a different tone or style."""
    if not text.strip():
        return json.dumps({"error": "No text provided."})

    tone = tone.lower().strip()
    if tone not in TONE_INSTRUCTIONS:
        return json.dumps({
            "error": f"Unknown tone: '{tone}'",
            "supported_tones": list(TONE_INSTRUCTIONS.keys()),
        })

    variations = max(1, min(3, variations))

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        tone_guide = TONE_INSTRUCTIONS[tone]
        var_note = f"Provide exactly {variations} different variation(s)." if variations > 1 else "Provide 1 variation."

        system = f"""You are an expert writing assistant specializing in text paraphrasing.
{tone_guide}
{var_note}
Preserve the original meaning completely — only the style and tone should change.

Respond ONLY with valid JSON:
{{
  "paraphrased": ["variation 1", "variation 2"],
  "original_tone": "detected original tone (academic/formal/casual/etc)",
  "similarity_note": "brief note about how meaning was preserved"
}}"""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Paraphrase this text to {tone} tone:\n\n{text[:6000]}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        result = json.loads(result_text)
        return json.dumps({
            "paraphrased": result.get("paraphrased", [result_text]),
            "original_tone": result.get("original_tone", "unknown"),
            "target_tone": tone,
            "similarity_note": result.get("similarity_note", ""),
            "original_length": len(text),
            "variations": variations,
        })
    except json.JSONDecodeError:
        # LLM returned plain text — wrap it
        return json.dumps({
            "paraphrased": [resp.content.strip()],
            "original_tone": "unknown",
            "target_tone": tone,
            "original_length": len(text),
        })
    except Exception as e:
        return json.dumps({"error": f"Paraphrasing failed: {str(e)}"})
