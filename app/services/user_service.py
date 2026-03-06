"""User service — syncs Supabase Auth users to auth_users_table.
Called by: auth routes (signup/signin/signout lifecycle), chat routes (get user profile)."""
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from app.config.settings import settings

logger = logging.getLogger(__name__)

try:
    from supabase import create_client
except ImportError:
    raise ImportError("Supabase not installed")


# Username regex: starts with letter, 6-18 chars, only letters, numbers, _, -, .
USERNAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.\-]{5,17}$')


def get_supabase_client():
    """Get Supabase client with anon key (for auth operations)."""
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError("Supabase not configured")
    return create_client(settings.supabase_url, settings.supabase_key)


def get_supabase_admin_client():
    """Get Supabase client with service role key (bypasses RLS)."""
    if not settings.supabase_url:
        raise ValueError("SUPABASE_URL not configured")

    key = settings.supabase_service_role_key or settings.supabase_key
    if not key:
        raise ValueError("No Supabase key configured")

    return create_client(settings.supabase_url, key)


def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username format (6-18 chars, starts with letter, allows _ - .).
    Called by: auth.signup, auth.check_username."""
    if not username:
        return False, "Username is required"

    if len(username) < 6:
        return False, "Username must be at least 6 characters"

    if len(username) > 18:
        return False, "Username must be at most 18 characters"

    if not username[0].isalpha():
        return False, "Username must start with a letter"

    if not USERNAME_PATTERN.match(username):
        return False, "Username can only contain letters, numbers, underscore, dash, and dot"

    return True, "Valid"


def generate_shard_number(username: str) -> int:
    """Generate shard 1-26 based on first letter of username."""
    first_letter = username[0].lower()
    return ord(first_letter) - ord('a') + 1  # a=1, b=2, ..., z=26


def sync_user_signup(
    user_uuid: str,
    email: str,
    username: str,
    name: Optional[str] = None
) -> dict:
    """Insert new user row into auth_users_table with shard_num and default role.
    Called by: auth.signup after Supabase Auth account creation."""
    supabase = get_supabase_admin_client()

    # Build user data matching the actual table columns
    # ENUM values:
    #   subscription_status: 'hooray', 'pending', 'uhoh'
    #   auth_user_role (roles): 'free', 'subscriber', 'business'
    # Note: payment_customer_id uses user_uuid as placeholder (unique constraint requires non-null)
    user_data = {
        "user_uuid": user_uuid,
        "email": email,
        "username": username.lower() if username else "",
        "name": name,
        "shard_num": generate_shard_number(username),
        "subscription_status": "pending",
        "auth_user_role": "free",
        "is_verified": False,
        "payment_customer_id": f"pending_{user_uuid}",
    }

    # Remove None values (but keep empty strings and False)
    user_data = {k: v for k, v in user_data.items() if v is not None}

    result = supabase.table("auth_users_table").insert(user_data).execute()
    return result.data[0] if result.data else user_data


def sync_user_signin(user_uuid: str) -> dict:
    """Update last_login_at timestamp in auth_users_table. Called by: auth.signin."""
    supabase = get_supabase_admin_client()
    now = datetime.now(timezone.utc).isoformat()

    try:
        result = supabase.table("auth_users_table").update({
            "last_login_at": now,
            "updated_at": now,
        }).eq("user_uuid", user_uuid).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.warning(f"Signin sync error: {e}")
        return {}


def sync_user_signout(user_uuid: str) -> dict:
    """Update updated_at timestamp in auth_users_table. Called by: auth.signout."""
    supabase = get_supabase_admin_client()
    now = datetime.now(timezone.utc).isoformat()

    try:
        result = supabase.table("auth_users_table").update({
            "updated_at": now,
        }).eq("user_uuid", user_uuid).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.warning(f"Signout sync error: {e}")
        return {}


def check_username_exists(username: str) -> bool:
    """Direct DB check if username exists in auth_users_table. Called by: bloom_filter_service as fallback."""
    supabase = get_supabase_admin_client()
    try:
        result = supabase.table("auth_users_table").select("username").eq(
            "username", username.lower()
        ).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.warning(f"Username check error: {e}")
        return False


def get_user_by_uuid(user_uuid: str) -> Optional[dict]:
    """Fetch full user row from auth_users_table by UUID.
    Called by: auth.get_current_user_info, auth.signin, auth.get_user_profile."""
    supabase = get_supabase_admin_client()
    try:
        result = supabase.table("auth_users_table").select("*").eq(
            "user_uuid", user_uuid
        ).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"Get user error: {e}")
        return None
