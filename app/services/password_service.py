"""
Password service with complex hashing and validation.
Uses bcrypt + custom pepper + HMAC for extra security.
"""
import re
import hashlib
import hmac
import secrets
import base64
from typing import Tuple, Optional
from app.config.settings import settings

try:
    import bcrypt
except ImportError:
    raise ImportError("bcrypt not installed. Install with: pip install bcrypt")


# Custom pepper - stored in environment, adds extra layer beyond salt
PEPPER = (settings.jwt_secret or "nurav-default-pepper-change-me")[:32]

# Password requirements
MIN_LENGTH = 8
MAX_LENGTH = 128
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGIT = True
REQUIRE_SPECIAL = True
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;':\",./<>?"


def validate_password(password: str) -> Tuple[bool, str, list]:
    """
    Validate password complexity.
    Returns: (is_valid, error_message, list_of_issues)
    """
    issues = []

    if not password:
        return False, "Password is required", ["Password is required"]

    if len(password) < MIN_LENGTH:
        issues.append(f"At least {MIN_LENGTH} characters")

    if len(password) > MAX_LENGTH:
        issues.append(f"Maximum {MAX_LENGTH} characters")

    if REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        issues.append("One uppercase letter")

    if REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
        issues.append("One lowercase letter")

    if REQUIRE_DIGIT and not re.search(r'\d', password):
        issues.append("One number")

    if REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?]', password):
        issues.append("One special character (!@#$%^&*...)")

    # Check for common patterns
    common_patterns = [
        r'(.)\1{2,}',  # 3+ repeated characters
        r'(012|123|234|345|456|567|678|789|890)',  # Sequential numbers
        r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)',  # Sequential letters
    ]

    for pattern in common_patterns:
        if re.search(pattern, password.lower()):
            issues.append("No sequential or repeated patterns")
            break

    if issues:
        return False, f"Password must have: {', '.join(issues)}", issues

    return True, "Valid", []


def calculate_password_strength(password: str) -> dict:
    """
    Calculate password strength score (0-100).
    """
    score = 0
    feedback = []

    # Length score (up to 30 points)
    length = len(password)
    if length >= 8:
        score += 10
    if length >= 12:
        score += 10
    if length >= 16:
        score += 10

    # Character variety (up to 40 points)
    if re.search(r'[a-z]', password):
        score += 10
    if re.search(r'[A-Z]', password):
        score += 10
    if re.search(r'\d', password):
        score += 10
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?]', password):
        score += 10

    # Bonus for mixing (up to 20 points)
    char_types = sum([
        bool(re.search(r'[a-z]', password)),
        bool(re.search(r'[A-Z]', password)),
        bool(re.search(r'\d', password)),
        bool(re.search(r'[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?]', password)),
    ])
    if char_types >= 3:
        score += 10
    if char_types == 4:
        score += 10

    # Penalties
    if re.search(r'(.)\1{2,}', password):
        score -= 10
        feedback.append("Avoid repeated characters")

    if re.search(r'(012|123|234|345|456|567|678|789)', password):
        score -= 10
        feedback.append("Avoid sequential numbers")

    # Determine strength level
    if score >= 80:
        level = "strong"
    elif score >= 60:
        level = "good"
    elif score >= 40:
        level = "fair"
    else:
        level = "weak"

    return {
        "score": max(0, min(100, score)),
        "level": level,
        "feedback": feedback
    }


def _apply_pepper(password: str) -> bytes:
    """Apply HMAC with pepper to password."""
    return hmac.new(
        PEPPER.encode('utf-8'),
        password.encode('utf-8'),
        hashlib.sha256
    ).digest()


def _add_custom_twist(peppered: bytes, salt: bytes) -> bytes:
    """
    Custom twist: XOR peppered password with derived key from salt.
    This adds an extra layer that's unique to our implementation.
    """
    # Derive a key from salt using SHA-256
    derived = hashlib.sha256(salt + PEPPER.encode('utf-8')).digest()

    # XOR the peppered password with derived key
    twisted = bytes(a ^ b for a, b in zip(peppered, derived))

    return twisted


def hash_password(password: str) -> str:
    """
    Hash password with bcrypt + pepper + custom twist.

    Process:
    1. Apply HMAC with pepper
    2. Generate bcrypt salt
    3. Apply custom twist
    4. Hash with bcrypt
    5. Encode result with version prefix

    Returns: Encoded hash string
    """
    # Step 1: Apply pepper using HMAC
    peppered = _apply_pepper(password)

    # Step 2: Generate bcrypt salt (cost factor 12)
    salt = bcrypt.gensalt(rounds=12)

    # Step 3: Apply custom twist
    twisted = _add_custom_twist(peppered, salt)

    # Step 4: Base64 encode twisted for bcrypt compatibility
    twisted_b64 = base64.b64encode(twisted).decode('utf-8')

    # Step 5: Hash with bcrypt
    hashed = bcrypt.hashpw(twisted_b64.encode('utf-8'), salt)

    # Step 6: Return with version prefix for future upgrades
    return f"$nurav$v1${hashed.decode('utf-8')}"


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify password against stored hash.
    """
    try:
        # Check version prefix
        if not hashed.startswith("$nurav$v1$"):
            return False

        # Extract bcrypt hash
        bcrypt_hash = hashed[10:]  # Remove "$nurav$v1$"

        # Extract salt from bcrypt hash (first 29 chars)
        salt = bcrypt_hash[:29].encode('utf-8')

        # Recreate the twisted password
        peppered = _apply_pepper(password)
        twisted = _add_custom_twist(peppered, salt)
        twisted_b64 = base64.b64encode(twisted).decode('utf-8')

        # Verify with bcrypt
        return bcrypt.checkpw(twisted_b64.encode('utf-8'), bcrypt_hash.encode('utf-8'))

    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password."""
    # Ensure we have all required character types
    password = [
        secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
        secrets.choice('abcdefghijklmnopqrstuvwxyz'),
        secrets.choice('0123456789'),
        secrets.choice('!@#$%^&*()_+-='),
    ]

    # Fill remaining length with random chars
    all_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-='
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))

    # Shuffle
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)
