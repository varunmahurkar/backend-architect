"""
RAG Retrieval Node
Retrieves relevant context from vector stores based on query and user history.
Combines results from academic (Pinecone) and conversation (pgvector) stores.
"""

import logging
import asyncio
from typing import List, Dict
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)


async def rag_retrieval_node(state: AgentState) -> dict:
    """
    Retrieve relevant context from vector stores.
    Searches academic papers (Pinecone) and conversation history (pgvector).

    Currently gracefully skips if vector stores are not configured.
    This allows the system to work without vector DB setup in MVP.
    """
    query = state.get("query", "")
    user_id = state.get("user_id")
    logger.info(f"RAG retrieval for: {query[:100]}, user_id: {user_id}")

    rag_context: List[Dict] = []

    # Try academic vector store (Pinecone) with 5s timeout
    try:
        from app.services.vector_stores.academic_store import AcademicVectorStore
        academic_store = AcademicVectorStore()
        academic_docs = await asyncio.wait_for(academic_store.search(query=query, top_k=3), timeout=5.0)
        for doc in academic_docs:
            rag_context.append({
                "content": doc.content,
                "source": "academic_rag",
                "metadata": doc.metadata,
            })
        logger.info(f"Academic RAG returned {len(academic_docs)} results")
    except ImportError:
        logger.debug("Academic vector store not available (Pinecone not configured)")
    except asyncio.TimeoutError:
        logger.warning("Academic RAG timed out after 5s")
    except Exception as e:
        logger.warning(f"Academic RAG failed: {e}")

    # Try conversation vector store (pgvector) for personalized context with 5s timeout
    if user_id:
        try:
            from app.services.vector_stores.conversation_store import ConversationVectorStore
            conv_store = ConversationVectorStore()
            conv_docs = await asyncio.wait_for(
                conv_store.search(query=query, top_k=3, filter={"user_id": user_id}),
                timeout=5.0,
            )
            for doc in conv_docs:
                rag_context.append({
                    "content": doc.content,
                    "source": "conversation_rag",
                    "metadata": doc.metadata,
                })
            logger.info(f"Conversation RAG returned {len(conv_docs)} results")
        except ImportError:
            logger.debug("Conversation vector store not available (pgvector not configured)")
        except asyncio.TimeoutError:
            logger.warning("Conversation RAG timed out after 5s")
        except Exception as e:
            logger.warning(f"Conversation RAG failed: {e}")

    return {
        "rag_context": rag_context,
        "current_phase": "retrieved",
    }
