"""
Grammar Checker Tool — Check grammar, spelling, style, and clarity using LLM.
Includes readability scoring and per-issue corrections with explanations.
"""

import json
import logging
import re

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _compute_readability(text: str) -> dict:
    """Compute readability metrics (Flesch-Kincaid approximation)."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = text.split()
    syllable_count = 0
    for word in words:
        word = word.lower().strip(".,!?;:'\"")
        vowels = "aeiou"
        count = 0
        prev_vowel = False
        for ch in word:
            is_vowel = ch in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith("e") and count > 1:
            count -= 1
        syllable_count += max(count, 1)

    num_sentences = max(len(sentences), 1)
    num_words = max(len(words), 1)

    # Flesch Reading Ease
    fre = 206.835 - 1.015 * (num_words / num_sentences) - 84.6 * (syllable_count / num_words)
    fre = max(0, min(100, round(fre, 1)))

    # Grade level
    grade = 0.39 * (num_words / num_sentences) + 11.8 * (syllable_count / num_words) - 15.59
    grade = max(0, round(grade, 1))

    if fre >= 80:
        level = "Easy"
    elif fre >= 60:
        level = "Standard"
    elif fre >= 40:
        level = "Difficult"
    else:
        level = "Very Difficult"

    return {
        "flesch_reading_ease": fre,
        "grade_level": grade,
        "level": level,
        "sentences": num_sentences,
        "words": num_words,
        "avg_words_per_sentence": round(num_words / num_sentences, 1),
    }


@nurav_tool(metadata=ToolMetadata(
    name="grammar_checker",
    description="Check grammar, spelling, style, and clarity. Returns corrections with explanations and a readability score.",
    niche="language",
    status=ToolStatus.ACTIVE,
    icon="spell-check",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"text": "Their going to the store tommorrow.", "language": "en"},
            output='{"corrected_text": "They\'re going to the store tomorrow.", "issues": [...], "readability": {"score": 85}}',
            description="Check grammar in a sentence",
        ),
    ],
    input_schema={"text": "str", "language": "str (default 'en')", "style": "str ('academic'|'business'|'casual'|'auto')"},
    output_schema={"corrected_text": "str", "issues": "array", "readability": "dict"},
    avg_response_ms=3000,
    success_rate=0.95,
))
@tool
async def grammar_checker(text: str, language: str = "en", style: str = "auto") -> str:
    """Check grammar, spelling, and style."""
    if not text.strip():
        return json.dumps({"error": "No text provided."})

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        style_guide = {
            "academic": "Use formal academic English. Flag colloquialisms, contractions, and informal language.",
            "business": "Use professional business English. Flag overly casual language and jargon.",
            "casual": "Allow informal language but fix grammar/spelling errors.",
            "auto": "Detect the appropriate style from context and check accordingly.",
        }

        system = f"""You are an expert proofreader and grammar checker for {language} text.
Style guidance: {style_guide.get(style, style_guide['auto'])}

Analyze the text for grammar, spelling, punctuation, style, and clarity issues.
Respond ONLY with valid JSON:
{{
  "corrected_text": "the fully corrected version of the text",
  "issues": [
    {{
      "type": "grammar|spelling|punctuation|style|clarity",
      "original": "the problematic text",
      "correction": "the corrected text",
      "explanation": "why this is an issue",
      "severity": "error|warning|suggestion",
      "position": "approximate location in text"
    }}
  ]
}}
If the text has no issues, return an empty issues array with the original text as corrected_text."""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Check this text:\n\n{text[:8000]}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        llm_result = json.loads(result_text)
        readability = _compute_readability(text)

        return json.dumps({
            "corrected_text": llm_result.get("corrected_text", text),
            "issues": llm_result.get("issues", []),
            "issue_count": len(llm_result.get("issues", [])),
            "readability": readability,
            "language": language,
            "style": style,
            "original_length": len(text),
        })
    except json.JSONDecodeError:
        readability = _compute_readability(text)
        return json.dumps({
            "corrected_text": text,
            "issues": [],
            "issue_count": 0,
            "readability": readability,
            "note": "LLM response could not be parsed. Readability metrics still available.",
        })
    except Exception as e:
        readability = _compute_readability(text)
        return json.dumps({
            "error": f"Grammar check failed: {str(e)}",
            "readability": readability,
        })
