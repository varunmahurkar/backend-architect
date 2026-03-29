"""Redis-backed distributed cache for agentic query responses.
Falls back to in-memory dict if REDIS_URL is not configured.
Same interface as app/services/cache.py (get/put) — drop-in replacement.
Called by: app/api/routes/chat.py (agentic-stream endpoint)."""

import hashlib
import json
import logging
import time
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

TTL_SECONDS = 3600  # 1 hour
MAX_FALLBACK_ENTRIES = 200


class RedisCache:
    """Async cache backed by Redis with transparent in-memory fallback.

    On startup, attempts to connect to Redis via REDIS_URL from settings.
    If Redis is unavailable or unconfigured, all operations use an in-memory
    dict with LRU eviction — zero config required for local development.
    """

    def __init__(self):
        self._client = None           # redis.asyncio.Redis instance (if connected)
        self._fallback: Dict[str, Dict[str, Any]] = {}  # in-memory LRU store
        self._connected = False

    async def connect(self) -> None:
        """Attempt Redis connection. Silently uses in-memory fallback on failure."""
        from app.config.settings import settings
        if not settings.redis_url:
            logger.info("REDIS_URL not set — using in-memory cache fallback")
            return

        try:
            import redis.asyncio as aioredis  # type: ignore[import]
            self._client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis cache connected: {settings.redis_url}")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}) — falling back to in-memory cache")
            self._client = None
            self._connected = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, query: str, mode: str) -> Optional[Dict[str, Any]]:
        """Return cached {response, citations} dict or None on miss/expiry."""
        key = self._make_key(query, mode)

        if self._connected and self._client:
            try:
                raw = await self._client.get(key)
                if raw:
                    logger.info(f"Redis cache HIT: {query[:50]!r}")
                    return json.loads(raw)
                return None
            except Exception as e:
                logger.warning(f"Redis GET failed ({e}), checking fallback")

        # In-memory fallback
        entry = self._fallback.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry["ts"] > TTL_SECONDS:
            del self._fallback[key]
            return None
        logger.info(f"Memory cache HIT: {query[:50]!r}")
        return {"response": entry["response"], "citations": entry["citations"]}

    async def put(
        self,
        query: str,
        mode: str,
        response: str,
        citations: List[Dict],
        ttl: int = TTL_SECONDS,
    ) -> None:
        """Store a response. TTL is applied both in Redis and the fallback store."""
        key = self._make_key(query, mode)
        payload = {"response": response, "citations": citations}

        if self._connected and self._client:
            try:
                await self._client.setex(key, ttl, json.dumps(payload))
                return
            except Exception as e:
                logger.warning(f"Redis SET failed ({e}), writing to fallback")

        # In-memory fallback with LRU eviction
        if len(self._fallback) >= MAX_FALLBACK_ENTRIES and key not in self._fallback:
            oldest = min(self._fallback, key=lambda k: self._fallback[k]["ts"])
            del self._fallback[oldest]

        self._fallback[key] = {"response": response, "citations": citations, "ts": time.monotonic()}
        logger.info(f"Memory cache SET: {query[:50]!r} ({len(self._fallback)} entries)")

    async def clear(self) -> None:
        """Flush all cached entries."""
        self._fallback.clear()
        if self._connected and self._client:
            try:
                await self._client.flushdb()
            except Exception as e:
                logger.warning(f"Redis FLUSHDB failed: {e}")

    @property
    def is_redis(self) -> bool:
        """True if backed by Redis, False if using in-memory fallback."""
        return self._connected

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(query: str, mode: str) -> str:
        raw = f"{query.strip().lower()}:{mode}"
        return f"nurav:{hashlib.sha256(raw.encode()).hexdigest()}"


# Singleton — initialised lazily in chat.py startup or first request
redis_cache = RedisCache()
