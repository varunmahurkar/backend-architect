"""
Translator Tool — 2-tier fallback translation.
Tier 1: LLM (Gemini) — best quality, context-aware
Tier 2: MyMemory API — free, 5000 chars/day, no key needed
"""

import json
import logging

import httpx
from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _translate_llm(text: str, target_lang: str, source_lang: str) -> dict | None:
    """Tier 1: LLM translation via Gemini."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.config.settings import settings

        if not settings.google_api_key:
            return None

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.1,
            max_output_tokens=2000,
        )

        src_info = f" from {source_lang}" if source_lang != "auto" else ""
        system = f"You are a professional translator. Translate the following text{src_info} to {target_lang}. Only return the translated text, nothing else."

        response = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=text),
        ])

        translated = response.content.strip()
        if not translated:
            return None

        # Detect source language if auto
        detected_lang = source_lang
        if source_lang == "auto":
            detect_resp = await llm.ainvoke([
                SystemMessage(content="What language is this text written in? Reply with ONLY the ISO 639-1 two-letter language code (e.g., en, fr, es, de, zh, ja)."),
                HumanMessage(content=text),
            ])
            detected_lang = detect_resp.content.strip().lower()[:2]

        return {
            "translated_text": translated,
            "source_lang": detected_lang,
            "target_lang": target_lang,
            "method": "llm",
        }
    except Exception as e:
        logger.warning(f"LLM translation failed: {e}")
        return None


async def _translate_mymemory(text: str, target_lang: str, source_lang: str) -> dict | None:
    """Tier 2: MyMemory API (free, no key)."""
    try:
        src = source_lang if source_lang != "auto" else "en"
        langpair = f"{src}|{target_lang}"
        url = "https://api.mymemory.translated.net/get"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"q": text[:500], "langpair": langpair})
            resp.raise_for_status()
            data = resp.json()

        if data.get("responseStatus") == 200:
            translated = data["responseData"]["translatedText"]
            return {
                "translated_text": translated,
                "source_lang": src,
                "target_lang": target_lang,
                "method": "mymemory",
            }
        return None
    except Exception as e:
        logger.warning(f"MyMemory translation failed: {e}")
        return None


@nurav_tool(metadata=ToolMetadata(
    name="translator",
    description="Translate text between languages with automatic source language detection. Uses AI translation with fallbacks for reliability.",
    niche="language",
    status=ToolStatus.ACTIVE,
    icon="languages",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"text": "Hello world", "target_lang": "es"},
            output='{"translated_text": "Hola mundo", "source_lang": "en", "target_lang": "es", "method": "llm"}',
            description="Translate English to Spanish",
        ),
        ToolExample(
            input={"text": "Bonjour le monde", "target_lang": "en", "source_lang": "fr"},
            output='{"translated_text": "Hello world", "source_lang": "fr", "target_lang": "en", "method": "llm"}',
            description="Translate French to English",
        ),
    ],
    input_schema={"text": "str", "target_lang": "str (ISO code, e.g. es, fr, de)", "source_lang": "str (optional, default auto)"},
    output_schema={"translated_text": "str", "source_lang": "str", "target_lang": "str", "method": "str"},
    avg_response_ms=2000,
    success_rate=0.95,
))
@tool
async def translator(text: str, target_lang: str = "es", source_lang: str = "auto") -> str:
    """Translate text to a target language with automatic source language detection."""
    if not text.strip():
        return json.dumps({"error": "No text provided for translation."})

    # Tier 1: LLM
    result = await _translate_llm(text, target_lang, source_lang)
    if result:
        return json.dumps(result, ensure_ascii=False)

    # Tier 2: MyMemory API
    result = await _translate_mymemory(text, target_lang, source_lang)
    if result:
        return json.dumps(result, ensure_ascii=False)

    return json.dumps({"error": "All translation methods failed. Please try again later."})
