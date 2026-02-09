"""
Conversation Vector Store (pgvector)
Stores and retrieves conversation embeddings for personalized RAG.
Uses text-embedding-3-small (1536 dims) for cost efficiency.
Leverages existing Supabase PostgreSQL with pgvector extension.
"""

import logging
from typing import List, Dict, Optional
from app.services.vector_stores.base import VectorStoreBase, Document
from app.config.settings import settings

logger = logging.getLogger(__name__)


class ConversationVectorStore(VectorStoreBase):
    """pgvector-backed vector store for conversation history."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-initialize Supabase client."""
        if self._client is None:
            from supabase import create_client
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise RuntimeError("Supabase not configured for vector store")
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
        return self._client

    async def upsert(self, documents: List[Document]) -> int:
        """
        Upsert conversation embeddings into pgvector.
        Generates embeddings if not already provided.
        """
        if not documents:
            return 0

        from app.services.vector_stores.embeddings import embed_texts

        # Generate embeddings for documents without them
        texts_to_embed = []
        embed_indices = []
        for i, doc in enumerate(documents):
            if doc.embedding is None:
                texts_to_embed.append(doc.content[:4000])
                embed_indices.append(i)

        if texts_to_embed:
            embeddings = await embed_texts(texts_to_embed, model="general")
            for idx, emb in zip(embed_indices, embeddings):
                documents[idx].embedding = emb

        client = self._get_client()
        count = 0

        for doc in documents:
            if doc.embedding:
                try:
                    data = {
                        "id": doc.id,
                        "user_id": doc.metadata.get("user_id"),
                        "conversation_id": doc.metadata.get("conversation_id"),
                        "message_id": doc.metadata.get("message_id", doc.id),
                        "role": doc.metadata.get("role", "user"),
                        "content": doc.content,
                        "embedding": doc.embedding,
                    }
                    client.table("conversation_embeddings").upsert(data).execute()
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to upsert conversation doc {doc.id}: {e}")

        logger.info(f"Upserted {count} conversation embeddings")
        return count

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter: Optional[Dict] = None,
    ) -> List[Document]:
        """
        Semantic search for relevant conversation history.
        Uses pgvector's cosine similarity for ranking.
        """
        from app.services.vector_stores.embeddings import embed_query

        query_embedding = await embed_query(query, model="general")
        client = self._get_client()

        try:
            # Use Supabase RPC for vector similarity search
            params = {
                "query_embedding": query_embedding,
                "match_threshold": 0.5,
                "match_count": top_k,
            }
            if filter and "user_id" in filter:
                params["filter_user_id"] = filter["user_id"]

            response = client.rpc("match_conversations", params).execute()

            documents = []
            for row in response.data or []:
                documents.append(Document(
                    id=row.get("id", ""),
                    content=row.get("content", ""),
                    metadata={
                        "user_id": row.get("user_id"),
                        "conversation_id": row.get("conversation_id"),
                        "role": row.get("role"),
                        "created_at": row.get("created_at"),
                    },
                    score=row.get("similarity"),
                ))

            logger.info(f"Conversation search returned {len(documents)} results")
            return documents

        except Exception as e:
            logger.warning(f"Conversation vector search failed: {e}")
            return []

    async def delete(self, ids: List[str]) -> int:
        """Delete conversation embeddings by ID."""
        if not ids:
            return 0
        client = self._get_client()
        try:
            client.table("conversation_embeddings").delete().in_("id", ids).execute()
            return len(ids)
        except Exception as e:
            logger.error(f"Failed to delete conversation embeddings: {e}")
            return 0
