"""LLM service — multi-provider LangChain wrapper (Gemini, OpenAI, Anthropic).
Called by: chat.py (completions/stream), crawler.py (web chat), agents/graph.py (agentic nodes)."""

import asyncio
import logging
from typing import Optional, AsyncGenerator, Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Provider type
LLMProvider = Literal["google", "openai", "anthropic"]

# Module-level LLM instance cache keyed by "provider:streaming:model"
_llm_cache: dict[str, object] = {}

# Failover order for invoke_with_failover()
_FAILOVER_ORDER: list[LLMProvider] = ["google", "openai", "anthropic"]


def get_llm(provider: Optional[LLMProvider] = None, streaming: bool = False, model_override: Optional[str] = None):
    """Get LangChain LLM instance for the given provider."""
    provider = provider or settings.default_llm_provider

    cache_key = f"{provider}:{streaming}:{model_override or ''}"
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not configured")

        instance = ChatGoogleGenerativeAI(
            model=model_override or settings.google_model,
            google_api_key=settings.google_api_key,
            temperature=settings.google_temperature,
            max_output_tokens=settings.google_max_tokens,
            streaming=streaming,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        instance = ChatOpenAI(
            model=model_override or settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
            streaming=streaming,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        instance = ChatAnthropic(
            model=model_override or settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.anthropic_temperature,
            max_tokens=settings.anthropic_max_tokens,
            streaming=streaming,
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")

    # Don't cache streaming instances — they carry internal state
    if not streaming:
        _llm_cache[cache_key] = instance
    return instance


async def invoke_with_failover(messages: list, system: Optional[str] = None):
    """Invoke LLM with automatic provider failover (Google → OpenAI → Anthropic).

    Tries each configured provider with 2 retries (exponential backoff) before
    moving to the next. Raises RuntimeError if all providers fail.
    """
    import httpx

    if system:
        full_messages = [SystemMessage(content=system)] + list(messages)
    else:
        full_messages = list(messages)

    last_error: Exception = RuntimeError("No LLM providers configured")
    for provider in _FAILOVER_ORDER:
        try:
            llm = get_llm(provider=provider)
        except ValueError:
            # API key not configured for this provider — skip
            continue

        for attempt in range(2):
            try:
                return await llm.ainvoke(full_messages)
            except Exception as exc:
                last_error = exc
                exc_str = str(exc).lower()
                # Retryable: rate limits, timeouts, connection errors
                is_retryable = (
                    "429" in exc_str
                    or "rate" in exc_str
                    or "timeout" in exc_str
                    or "connect" in exc_str
                    or isinstance(exc, (httpx.TimeoutException, httpx.ConnectError))
                )
                if is_retryable and attempt == 0:
                    logger.warning(f"[llm_failover] {provider} attempt {attempt+1} failed ({exc}), retrying…")
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.warning(f"[llm_failover] {provider} failed: {exc}")
                    break  # Try next provider

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


def get_chat_chain(provider: Optional[LLMProvider] = None, system_prompt: Optional[str] = None):
    """
    Create a chat chain with optional system prompt.

    Args:
        provider: LLM provider
        system_prompt: Optional system prompt for the assistant

    Returns:
        LangChain runnable chain
    """
    llm = get_llm(provider)

    default_system = """You are Nurav AI, a helpful and intelligent assistant.
You provide clear, accurate, and well-formatted responses.
When providing code, use proper markdown code blocks with language specification.
Be concise but thorough in your explanations."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt or default_system),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
    ])

    chain = prompt | llm | StrOutputParser()
    return chain


async def chat(
    message: str,
    provider: Optional[LLMProvider] = None,
    chat_history: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Send a message to the LLM and get a response.

    Args:
        message: User message
        provider: LLM provider (google, openai, anthropic)
        chat_history: Optional list of previous messages
        system_prompt: Optional system prompt

    Returns:
        AI response as string
    """
    chain = get_chat_chain(provider, system_prompt)

    # Convert chat history to LangChain message format
    history = []
    if chat_history:
        for msg in chat_history:
            if msg.get("role") == "user":
                history.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                history.append(AIMessage(content=msg.get("content", "")))

    response = await chain.ainvoke({
        "input": message,
        "chat_history": history,
    })

    return response


async def chat_stream(
    message: str,
    provider: Optional[LLMProvider] = None,
    chat_history: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a response from the LLM.

    Args:
        message: User message
        provider: LLM provider
        chat_history: Optional list of previous messages
        system_prompt: Optional system prompt

    Yields:
        Response chunks as strings
    """
    llm = get_llm(provider, streaming=True)

    default_system = """You are Nurav AI, a helpful and intelligent assistant.
You provide clear, accurate, and well-formatted responses.
When providing code, use proper markdown code blocks with language specification.
Be concise but thorough in your explanations."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt or default_system),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
    ])

    chain = prompt | llm | StrOutputParser()

    # Convert chat history
    history = []
    if chat_history:
        for msg in chat_history:
            if msg.get("role") == "user":
                history.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                history.append(AIMessage(content=msg.get("content", "")))

    async for chunk in chain.astream({
        "input": message,
        "chat_history": history,
    }):
        yield chunk


def get_available_providers() -> list[dict]:
    """
    Get list of available (configured) LLM providers.

    Returns:
        List of provider info dicts
    """
    providers = []

    if settings.google_api_key:
        providers.append({
            "id": "google",
            "name": "Google Gemini",
            "model": settings.google_model,
            "available": True,
        })

    if settings.openai_api_key:
        providers.append({
            "id": "openai",
            "name": "OpenAI GPT",
            "model": settings.openai_model,
            "available": True,
        })

    if settings.anthropic_api_key:
        providers.append({
            "id": "anthropic",
            "name": "Anthropic Claude",
            "model": settings.anthropic_model,
            "available": True,
        })

    return providers
