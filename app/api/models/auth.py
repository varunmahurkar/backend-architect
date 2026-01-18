from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class SignUpRequest(BaseModel):
    """Request schema for user sign up."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (minimum 6 characters)")
    full_name: Optional[str] = Field(None, description="User's full name")


class SignInRequest(BaseModel):
    """Request schema for user sign in."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: Optional[str] = Field(None, description="User's full name")
    created_at: datetime = Field(..., description="Account creation timestamp")
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
