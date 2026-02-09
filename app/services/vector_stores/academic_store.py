"""
Academic Vector Store (Pinecone)
Stores and retrieves academic paper embeddings for semantic search.
Uses text-embedding-3-large (3072 dims) for maximum retrieval quality.
"""

import logging
from typing import List, Dict, Optional
from app.services.vector_stores.base import VectorStoreBase, Document
from app.config.settings import settings

logger = logging.getLogger(__name__)


class AcademicVectorStore(VectorStoreBase):
    """Pinecone-backed vector store for academic papers."""

    def __init__(self):
        self._index = None

    def _get_index(self):
        """Lazy-initialize Pinecone index connection."""
        if self._index is None:
            from pinecone import Pinecone

            if not settings.pinecone_api_key:
                raise RuntimeError("PINECONE_API_KEY not configured")

            pc = Pinecone(api_key=settings.pinecone_api_key)
            self._index = pc.Index(settings.pinecone_academic_index)
            logger.info(f"Connected to Pinecone index: {settings.pinecone_academic_index}")

        return self._index

    async def upsert(self, documents: List[Document]) -> int:
        """
        Upsert academic paper documents into Pinecone.
        Generates embeddings if not already provided.
        """
        if not documents:
            return 0

        from app.services.vector_stores.embeddings import embed_texts

        index = self._get_index()

        # Generate embeddings for documents without them
        texts_to_embed = []
        embed_indices = []
        for i, doc in enumerate(documents):
            if doc.embedding is None:
                texts_to_embed.append(doc.content[:8000])  # Pinecone limit
                embed_indices.append(i)

        if texts_to_embed:
            embeddings = await embed_texts(texts_to_embed, model="academic")
            for idx, emb in zip(embed_indices, embeddings):
                documents[idx].embedding = emb

        # Batch upsert to Pinecone
        vectors = []
        for doc in documents:
            if doc.embedding:
                vectors.append({
                    "id": doc.id,
                    "values": doc.embedding,
                    "metadata": {
                        **doc.metadata,
                        "content": doc.content[:1000],  # Store truncated content in metadata
                    },
                })

        if vectors:
            # Upsert in batches of 100
            for i in range(0, len(vectors), 100):
                batch = vectors[i:i + 100]
                index.upsert(vectors=batch)

        logger.info(f"Upserted {len(vectors)} documents to Pinecone")
        return len(vectors)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter: Optional[Dict] = None,
    ) -> List[Document]:
        """
        Semantic search for academic papers.
        Returns papers ranked by cosine similarity.
        """
        from app.services.vector_stores.embeddings import embed_query

        index = self._get_index()
        query_embedding = await embed_query(query, model="academic")

        query_params = {
            "vector": query_embedding,
            "top_k": top_k,
            "include_metadata": True,
        }
        if filter:
            query_params["filter"] = filter

        results = index.query(**query_params)

        documents = []
        for match in results.get("matches", []):
            metadata = match.get("metadata", {})
            content = metadata.pop("content", "")
            documents.append(Document(
                id=match["id"],
                content=content,
                metadata=metadata,
                score=match.get("score"),
            ))

        logger.info(f"Academic search returned {len(documents)} results for: {query[:50]}")
        return documents

    async def delete(self, ids: List[str]) -> int:
        """Delete papers by ID from Pinecone."""
        if not ids:
            return 0
        index = self._get_index()
        index.delete(ids=ids)
        return len(ids)
