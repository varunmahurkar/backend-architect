"""
Embedding Model Providers
Centralized embedding model configuration for different use cases.
- Academic: text-embedding-3-large (3072 dims) for maximum quality
- General: text-embedding-3-small (1536 dims) for cost efficiency
"""

import logging
from typing import List, Optional
from functools import lru_cache
from app.config.settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_academic_embeddings():
    """
    Get high-quality embedding model for academic paper indexing.
    Uses text-embedding-3-large with 3072 dimensions.
    """
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(
        model="text-embedding-3-large",
        dimensions=3072,
        openai_api_key=settings.openai_api_key,
    )


@lru_cache(maxsize=4)
def get_general_embeddings():
    """
    Get cost-efficient embedding model for general use.
    Uses text-embedding-3-small with 1536 dimensions.
    Suitable for conversations, user docs, and general search.
    """
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        dimensions=1536,
        openai_api_key=settings.openai_api_key,
    )


async def embed_texts(texts: List[str], model: str = "general") -> List[List[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed
        model: "academic" for high-quality or "general" for cost-efficient

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    embeddings_model = get_academic_embeddings() if model == "academic" else get_general_embeddings()

    try:
        embeddings = await embeddings_model.aembed_documents(texts)
        return embeddings
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise


async def embed_query(query: str, model: str = "general") -> List[float]:
    """
    Generate embedding for a single query.

    Args:
        query: Query text to embed
        model: "academic" for high-quality or "general" for cost-efficient

    Returns:
        Embedding vector
    """
    embeddings_model = get_academic_embeddings() if model == "academic" else get_general_embeddings()

    try:
        embedding = await embeddings_model.aembed_query(query)
        return embedding
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        raise
