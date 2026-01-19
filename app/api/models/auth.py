from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SignUpRequest(BaseModel):
    """Request schema for user sign up with username."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password: 8+ chars, uppercase, lowercase, number, special char"
    )
    username: str = Field(
        ...,
        min_length=6,
        max_length=18,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_.\-]{5,17}$",
        description="Username: 6-18 chars, starts with letter, allows letters, numbers, _, -, ."
    )
    full_name: Optional[str] = Field(None, description="User's full name")


class SignInRequest(BaseModel):
    """Request schema for user sign in."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    username: Optional[str] = Field(None, description="Username")
    full_name: Optional[str] = Field(None, description="User's full name")
    created_at: Optional[datetime] = Field(None, description="Account creation timestamp")
    last_sign_in_at: Optional[datetime] = Field(None, description="Last sign in timestamp")


class AuthResponse(BaseModel):
    """Response schema for authentication endpoints."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    user: Optional[UserResponse] = Field(None, description="User data if successful")
    access_token: Optional[str] = Field(None, description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token for session management")


class ErrorResponse(BaseModel):
    """Response schema for error responses."""
    success: bool = False
    message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")


class PhoneSignUpRequest(BaseModel):
    """Request schema for phone sign up (OTP request)."""
    phone: str = Field(
        ...,
        pattern=r"^\+[1-9]\d{1,14}$",
        description="Phone number in E.164 format (e.g., +1234567890)"
    )


class PhoneVerifyRequest(BaseModel):
    """Request schema for verifying phone OTP."""
    phone: str = Field(
        ...,
        pattern=r"^\+[1-9]\d{1,14}$",
        description="Phone number in E.164 format"
    )
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code"
    )


class OTPResponse(BaseModel):
    """Response schema for OTP operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    message_id: Optional[str] = Field(None, description="Message ID from SMS provider")


class SubscriptionStatus(str, Enum):
    """User subscription status."""
    FREE = "free"
    HOORAY = "hooray"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class AuthUserRole(str, Enum):
    """User role in the system."""
    FREE = "free"
    PREMIUM = "premium"
    ADMIN = "admin"


class AccountStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    PENDING_VERIFICATION = "pending_verification"


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    email_marketing: bool = True
    email_updates: bool = True
    push_notifications: bool = True
    sms_notifications: bool = False


class UserProfile(BaseModel):
    """Complete user profile for auth_users_table."""
    idx: Optional[int] = Field(None, description="Auto-increment ID")
    user_uuid: str = Field(..., description="Supabase auth user UUID")
    shard_num: Optional[int] = Field(None, ge=1, le=26, description="Shard 1-26 based on first letter of username")
    username: Optional[str] = Field(None, min_length=6, max_length=18, pattern=r"^[a-zA-Z][a-zA-Z0-9_.\-]{5,17}$", description="Unique username")
    email: EmailStr = Field(..., description="User email")
    name: Optional[str] = Field(None, description="Display name")
    user_info: Optional[Dict[str, Any]] = Field(None, description="Additional user metadata")
    subscription_status: SubscriptionStatus = Field(default=SubscriptionStatus.FREE)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    profile_image_url: Optional[str] = None
    is_verified: bool = False
    payment_customer_id: Optional[str] = None
    auth_user_role: AuthUserRole = Field(default=AuthUserRole.FREE)
    # Additional recommended fields
    phone_number: Optional[str] = Field(None, pattern=r"^\+[1-9]\d{1,14}$")
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = None
    timezone: Optional[str] = Field(None, description="IANA timezone (e.g., America/New_York)")
    preferred_language: str = Field(default="en")
    notification_preferences: Optional[NotificationPreferences] = None
    two_factor_enabled: bool = False
    account_status: AccountStatus = Field(default=AccountStatus.ACTIVE)
    referral_code: Optional[str] = None
    referred_by: Optional[str] = Field(None, description="Referrer's user_uuid")


class SignUpRequestExtended(BaseModel):
    """Extended signup request with username."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$", description="Unique username")
    full_name: Optional[str] = Field(None, description="User's full name")


class UsernameCheckRequest(BaseModel):
    """Request to check username availability."""
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")


class UsernameCheckResponse(BaseModel):
    """Response for username availability check."""
    available: bool
    username: str
    suggestions: Optional[List[str]] = Field(None, description="Alternative username suggestions if taken")


class BloomFilterResponse(BaseModel):
    """Response containing Bloom filter data for usernames."""
    filter_data: str = Field(..., description="Base64 encoded Bloom filter bit array")
    hash_count: int = Field(..., description="Number of hash functions used")
    size: int = Field(..., description="Size of bit array")
    item_count: int = Field(..., description="Approximate number of items in filter")
    last_updated: datetime = Field(..., description="When filter was last updated")


class PasswordValidationRequest(BaseModel):
    """Request to validate password strength."""
    password: str = Field(..., min_length=1, description="Password to validate")


class PasswordValidationResponse(BaseModel):
    """Response for password validation."""
    valid: bool = Field(..., description="Whether password meets requirements")
    score: int = Field(..., ge=0, le=100, description="Password strength score 0-100")
    level: str = Field(..., description="Strength level: weak, fair, good, strong")
    issues: List[str] = Field(default=[], description="List of issues with password")
    feedback: List[str] = Field(default=[], description="Improvement suggestions")


class UsernameAvailabilityResponse(BaseModel):
    """Response for username availability check."""
    username: str = Field(..., description="Username that was checked")
    available: bool = Field(..., description="Whether username is available")
    message: str = Field(..., description="Status message")
    suggestions: Optional[List[str]] = Field(None, description="Alternative usernames if taken")


class RandomUsernameResponse(BaseModel):
    """Response for random username generation."""
    username: str = Field(..., description="Generated random username")
    suggestions: List[str] = Field(default=[], description="Additional suggestions")
