"""
Vector Store Base
Abstract base class defining the interface for all vector store implementations.
Ensures consistent API across Pinecone, pgvector, and Qdrant stores.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pydantic import BaseModel


class Document(BaseModel):
    """Document with content, metadata, and optional embedding vector."""
    id: str
    content: str
    metadata: Dict = {}
    embedding: Optional[List[float]] = None
    score: Optional[float] = None


class VectorStoreBase(ABC):
    """Abstract base for all vector store implementations."""

    @abstractmethod
    async def upsert(self, documents: List[Document]) -> int:
        """
        Insert or update documents in the vector store.

        Args:
            documents: List of Document objects to upsert

        Returns:
            Number of documents successfully upserted
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter: Optional[Dict] = None,
    ) -> List[Document]:
        """
        Semantic search for documents matching the query.

        Args:
            query: Search query text
            top_k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of matching Documents sorted by relevance
        """
        pass

    @abstractmethod
    async def delete(self, ids: List[str]) -> int:
        """
        Delete documents by their IDs.

        Args:
            ids: List of document IDs to delete

        Returns:
            Number of documents successfully deleted
        """
        pass
