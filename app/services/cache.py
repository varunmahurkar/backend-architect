"""
Simple In-Memory Response Cache
Dict-based TTL cache for agentic query responses.
Key: sha256(normalized_query + mode), Value: {response, citations, timestamp}
Max 200 entries, 1hr TTL. No Redis needed for MVP.
"""

import hashlib
import time
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Cache configuration
MAX_ENTRIES = 200
TTL_SECONDS = 3600  # 1 hour


class ResponseCache:
    """Thread-safe in-memory cache for agentic responses."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _make_key(query: str, mode: str) -> str:
        """Create cache key from normalized query and mode."""
        normalized = query.strip().lower()
        raw = f"{normalized}:{mode}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, query: str, mode: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response if available and not expired.
        Returns dict with 'response' and 'citations' or None.
        """
        key = self._make_key(query, mode)
        entry = self._store.get(key)

        if entry is None:
            return None

        # Check TTL
        if time.monotonic() - entry["timestamp"] > TTL_SECONDS:
            del self._store[key]
            logger.debug(f"Cache expired for key {key[:12]}...")
            return None

        logger.info(f"Cache hit for query: {query[:50]}...")
        return {
            "response": entry["response"],
            "citations": entry["citations"],
        }

    def put(self, query: str, mode: str, response: str, citations: List[Dict]) -> None:
        """Store a response in cache. Evicts oldest entries if at capacity."""
        key = self._make_key(query, mode)

        # Evict oldest entries if at capacity
        if len(self._store) >= MAX_ENTRIES and key not in self._store:
            oldest_key = min(self._store, key=lambda k: self._store[k]["timestamp"])
            del self._store[oldest_key]
            logger.debug(f"Evicted oldest cache entry")

        self._store[key] = {
            "response": response,
            "citations": citations,
            "timestamp": time.monotonic(),
        }
        logger.info(f"Cached response for query: {query[:50]}... ({len(self._store)} entries)")

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()
        logger.info("Cache cleared")

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._store)


# Singleton cache instance
response_cache = ResponseCache()
