"""
LLM Service using LangChain with support for multiple providers.
Currently supports: Google Gemini, OpenAI, Anthropic
"""

from typing import Optional, AsyncGenerator, Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from app.config.settings import settings

# Provider type
LLMProvider = Literal["google", "openai", "anthropic"]


def get_llm(provider: Optional[LLMProvider] = None, streaming: bool = False, model_override: Optional[str] = None):
    """
    Get LLM instance based on provider.

    Args:
        provider: LLM provider (google, openai, anthropic). Defaults to settings default.
        streaming: Enable streaming responses.
        model_override: Override the default model for this provider (e.g. "gpt-4o-mini").

    Returns:
        LangChain LLM instance
    """
    provider = provider or settings.default_llm_provider

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not configured")

        return ChatGoogleGenerativeAI(
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

        return ChatOpenAI(
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

        return ChatAnthropic(
            model=model_override or settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.anthropic_temperature,
            max_tokens=settings.anthropic_max_tokens,
            streaming=streaming,
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")


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
