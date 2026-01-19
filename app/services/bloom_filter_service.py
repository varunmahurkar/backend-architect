"""
Bloom Filter service for fast username availability checking.
Uses multiple hash functions for low false positive rate.
"""
import hashlib
import math
import base64
import random
import string
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from app.config.settings import settings

try:
    from supabase import create_client
except ImportError:
    raise ImportError("Supabase not installed")


# Bloom filter configuration
BLOOM_FILTER_SIZE = 100000  # 100k bits (~12.5KB)
BLOOM_HASH_COUNT = 7  # Number of hash functions
FALSE_POSITIVE_RATE = 0.01  # 1% false positive rate


class BloomFilter:
    """In-memory Bloom filter for username checking."""

    def __init__(self, size: int = BLOOM_FILTER_SIZE, hash_count: int = BLOOM_HASH_COUNT):
        self.size = size
        self.hash_count = hash_count
        self.bit_array = bytearray(math.ceil(size / 8))
        self.item_count = 0
        self.last_updated = datetime.now(timezone.utc)

    def _get_hash_values(self, item: str) -> List[int]:
        """Generate multiple hash values for an item."""
        hashes = []
        item_bytes = item.lower().encode('utf-8')

        # Use different hash algorithms and seeds
        for i in range(self.hash_count):
            # Combine item with seed for different hash values
            seed = f"nurav_bloom_seed_{i}".encode('utf-8')
            combined = seed + item_bytes

            # Use SHA-256 and take different portions
            h = hashlib.sha256(combined).hexdigest()
            hash_val = int(h[i * 4:(i + 1) * 4], 16) % self.size
            hashes.append(hash_val)

        return hashes

    def _set_bit(self, index: int):
        """Set a bit in the array."""
        byte_index = index // 8
        bit_index = index % 8
        self.bit_array[byte_index] |= (1 << bit_index)

    def _get_bit(self, index: int) -> bool:
        """Get a bit from the array."""
        byte_index = index // 8
        bit_index = index % 8
        return bool(self.bit_array[byte_index] & (1 << bit_index))

    def add(self, item: str):
        """Add an item to the filter."""
        for hash_val in self._get_hash_values(item):
            self._set_bit(hash_val)
        self.item_count += 1
        self.last_updated = datetime.now(timezone.utc)

    def might_contain(self, item: str) -> bool:
        """
        Check if item might be in the filter.
        Returns True if possibly present (may be false positive).
        Returns False if definitely not present.
        """
        for hash_val in self._get_hash_values(item):
            if not self._get_bit(hash_val):
                return False
        return True

    def to_base64(self) -> str:
        """Export filter as base64 string."""
        return base64.b64encode(self.bit_array).decode('utf-8')

    @classmethod
    def from_base64(cls, data: str, size: int, hash_count: int) -> 'BloomFilter':
        """Create filter from base64 string."""
        bf = cls(size=size, hash_count=hash_count)
        bf.bit_array = bytearray(base64.b64decode(data))
        return bf

    def get_info(self) -> dict:
        """Get filter information."""
        return {
            "size": self.size,
            "hash_count": self.hash_count,
            "item_count": self.item_count,
            "fill_ratio": sum(bin(b).count('1') for b in self.bit_array) / self.size,
            "last_updated": self.last_updated.isoformat()
        }


# Global bloom filter instance
_username_bloom_filter: Optional[BloomFilter] = None
_last_refresh: Optional[datetime] = None
REFRESH_INTERVAL_SECONDS = 300  # Refresh every 5 minutes


def get_supabase_client():
    """Get Supabase client with anon key."""
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError("Supabase not configured")
    return create_client(settings.supabase_url, settings.supabase_key)


def get_supabase_admin_client():
    """
    Get Supabase client with service role key (for database operations).
    This bypasses Row Level Security (RLS).
    """
    if not settings.supabase_url:
        raise ValueError("Supabase URL not configured")

    # Prefer service role key for DB operations, fall back to anon key
    key = settings.supabase_service_role_key or settings.supabase_key
    if not key:
        raise ValueError("Supabase key not configured")

    return create_client(settings.supabase_url, key)


def _load_usernames_into_filter(bf: BloomFilter) -> int:
    """
    Load all usernames from database into bloom filter.
    Returns 0 if database is unavailable (filter will be empty but functional).
    """
    try:
        supabase = get_supabase_admin_client()
        # Fetch all usernames from auth_users_table
        result = supabase.table("auth_users_table").select("username").execute()

        count = 0
        for row in result.data:
            if row.get("username"):
                bf.add(row["username"].lower())
                count += 1

        return count
    except ValueError as e:
        # Supabase not configured - this is OK, filter will be empty
        print(f"Supabase not configured, using empty Bloom filter: {e}")
        return 0
    except Exception as e:
        # Database error - this is OK, filter will be empty
        print(f"Could not load usernames into Bloom filter: {e}")
        return 0


def get_username_bloom_filter(force_refresh: bool = False) -> BloomFilter:
    """
    Get or create the username bloom filter.
    Refreshes periodically to stay in sync with database.
    """
    global _username_bloom_filter, _last_refresh

    now = datetime.now(timezone.utc)

    # Check if we need to refresh
    needs_refresh = (
        _username_bloom_filter is None or
        force_refresh or
        _last_refresh is None or
        (now - _last_refresh).total_seconds() > REFRESH_INTERVAL_SECONDS
    )

    if needs_refresh:
        _username_bloom_filter = BloomFilter()
        count = _load_usernames_into_filter(_username_bloom_filter)
        _last_refresh = now
        print(f"Bloom filter refreshed with {count} usernames")

    return _username_bloom_filter


def add_username_to_filter(username: str):
    """Add a new username to the bloom filter."""
    bf = get_username_bloom_filter()
    bf.add(username.lower())


def check_username_availability_fast(username: str) -> Tuple[bool, str]:
    """
    Fast username availability check using Bloom filter.

    Returns:
        (possibly_available, message)
        - If False: Username might be taken (Bloom filter match)
        - If True: Username is likely available (not in Bloom filter)
    """
    try:
        bf = get_username_bloom_filter()

        if bf.might_contain(username.lower()):
            return False, "Username may be taken"
        else:
            return True, "Username appears available"
    except Exception as e:
        # If Bloom filter fails, assume available (DB will verify)
        print(f"Bloom filter fast check failed: {e}")
        return True, "Username appears available"


def check_username_availability_definitive(username: str) -> Tuple[bool, str]:
    """
    Username availability check using Bloom filter + optional DB verification.

    Strategy:
    1. Check Bloom filter first (fast, probabilistic)
    2. If Bloom filter says "not in set", username is definitely available
    3. If Bloom filter says "might be in set", try DB verification
    4. If DB verification fails, still allow (let actual insert handle uniqueness)

    Returns:
        (available, message)
    """
    username_lower = username.lower()

    # First, quick bloom filter check
    try:
        bf = get_username_bloom_filter()
        # Bloom filter: if not in filter, definitely available
        if not bf.might_contain(username_lower):
            return True, "Username is available"
    except Exception as e:
        # Bloom filter failed - skip to DB check or allow
        print(f"Bloom filter check failed: {e}")

    # Bloom filter says might exist (or failed) - try DB verification
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("auth_users_table").select("username").eq(
            "username", username_lower
        ).execute()

        if len(result.data) > 0:
            return False, "Username is taken"

        # DB says available (Bloom filter had false positive or failed)
        return True, "Username is available"

    except ValueError as e:
        # Supabase not configured - allow, actual signup will fail if there's an issue
        print(f"Supabase not configured (allowing): {e}")
        return True, "Username appears available"
    except Exception as e:
        # DB check failed - allow signup, let actual insert handle uniqueness
        # This is permissive: Bloom filter said "maybe", but we can't verify
        # Better to allow and let DB constraint catch duplicates
        print(f"DB username check failed (allowing): {e}")
        return True, "Username appears available"


def get_bloom_filter_data() -> dict:
    """
    Get bloom filter data for client-side checking.
    Client can use this to check usernames without server round-trips.
    """
    bf = get_username_bloom_filter()

    return {
        "filter_data": bf.to_base64(),
        "hash_count": bf.hash_count,
        "size": bf.size,
        "item_count": bf.item_count,
        "last_updated": bf.last_updated.isoformat()
    }


# Username generation
ADJECTIVES = [
    "swift", "bright", "cosmic", "cyber", "digital", "epic", "fast", "golden",
    "happy", "iron", "jade", "keen", "lucky", "magic", "noble", "prime",
    "quick", "rare", "silent", "tech", "ultra", "vivid", "wild", "zen"
]

NOUNS = [
    "arrow", "blade", "coder", "dragon", "eagle", "falcon", "ghost", "hawk",
    "iris", "joker", "knight", "lion", "matrix", "ninja", "oracle", "phoenix",
    "quest", "ranger", "shadow", "tiger", "unicorn", "viper", "wolf", "zero"
]


def generate_random_username() -> str:
    """Generate a random username."""
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    num = random.randint(10, 999)

    # Format: adjective_noun123 (6-18 chars)
    username = f"{adj}_{noun}{num}"

    # Ensure it starts with a letter and meets length requirements
    if len(username) < 6:
        username = username + str(random.randint(100, 999))
    elif len(username) > 18:
        username = username[:18]

    return username


def generate_username_suggestions(base_username: str, count: int = 5) -> List[str]:
    """
    Generate username suggestions based on a taken username.
    """
    suggestions = []
    base = base_username.lower()

    # Remove any numbers at the end
    base_clean = base.rstrip('0123456789')
    if len(base_clean) < 3:
        base_clean = base

    # Strategy 1: Add numbers
    for _ in range(2):
        num = random.randint(10, 999)
        suggestion = f"{base_clean}{num}"
        if 6 <= len(suggestion) <= 18 and suggestion[0].isalpha():
            suggestions.append(suggestion)

    # Strategy 2: Add underscore and numbers
    if len(base_clean) <= 14:
        num = random.randint(10, 99)
        suggestion = f"{base_clean}_{num}"
        if 6 <= len(suggestion) <= 18:
            suggestions.append(suggestion)

    # Strategy 3: Prepend adjective
    adj = random.choice(ADJECTIVES)
    suggestion = f"{adj}_{base_clean}"[:18]
    if 6 <= len(suggestion) <= 18 and suggestion[0].isalpha():
        suggestions.append(suggestion)

    # Strategy 4: Random variations
    while len(suggestions) < count:
        suggestions.append(generate_random_username())

    # Filter out duplicates and validate
    bf = get_username_bloom_filter()
    valid_suggestions = []

    for s in suggestions:
        s = s.lower()
        if (
            6 <= len(s) <= 18 and
            s[0].isalpha() and
            s not in valid_suggestions and
            not bf.might_contain(s)
        ):
            valid_suggestions.append(s)

        if len(valid_suggestions) >= count:
            break

    # If not enough, generate more random ones
    while len(valid_suggestions) < count:
        random_name = generate_random_username()
        if random_name not in valid_suggestions and not bf.might_contain(random_name):
            valid_suggestions.append(random_name)

    return valid_suggestions[:count]
