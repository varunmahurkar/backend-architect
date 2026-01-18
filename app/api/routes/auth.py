from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
from app.config.settings import settings
from app.api.models.auth import (
    SignUpRequest,
    SignInRequest,
    AuthResponse,
    ErrorResponse,
    UserResponse,
    PhoneSignUpRequest,
    PhoneVerifyRequest,
    OTPResponse
)
from app.api.dependencies.auth import get_current_user, TokenPayload

try:
    from supabase import create_client
except ImportError:
    raise ImportError("Supabase client is not installed. Install it with: pip install supabase")

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_supabase_client():
    """Initialize and return Supabase client."""
    if not settings.supabase_url or not settings.supabase_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase credentials not configured"
        )
    return create_client(settings.supabase_url, settings.supabase_key)


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignUpRequest) -> AuthResponse:
    """
    User sign up endpoint.
    
    Creates a new user account with email and password.
    
    Args:
        request: SignUpRequest containing email, password, and optional full_name
        
    Returns:
        AuthResponse with user data and tokens
    """
    try:
        supabase = get_supabase_client()
        
        # Sign up user with Supabase Auth
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
        })
        
        if response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user account"
            )
        
        user = response.user
        
        # Store additional user data in users table if full_name provided
        if request.full_name:
            try:
                supabase.table("users").insert({
                    "id": user.id,
                    "email": user.email,
                    "full_name": request.full_name
                }).execute()
            except Exception as e:
                print(f"Warning: Could not store full_name in users table: {e}")
        
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            full_name=request.full_name,
            created_at=user.created_at if hasattr(user, 'created_at') else None
        )
        
        return AuthResponse(
            success=True,
            message="User account created successfully. Check your email for verification.",
            user=user_response,
            access_token=response.session.access_token if response.session else None,
            refresh_token=response.session.refresh_token if response.session else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sign up failed: {str(e)}"
        )


@router.post("/signin", response_model=AuthResponse)
async def signin(request: SignInRequest) -> AuthResponse:
    """
    User sign in endpoint.
    
    Authenticates user with email and password, returns access token.
    
    Args:
        request: SignInRequest containing email and password
        
    Returns:
        AuthResponse with user data and tokens
    """
    try:
        supabase = get_supabase_client()
        
        # Sign in user with Supabase Auth
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if response.user is None or response.session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user = response.user
        session = response.session
        
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at if hasattr(user, 'created_at') else None,
            last_sign_in_at=user.last_sign_in_at if hasattr(user, 'last_sign_in_at') else None
        )
        
        return AuthResponse(
            success=True,
            message="Sign in successful",
            user=user_response,
            access_token=session.access_token,
            refresh_token=session.refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in failed"
        )


@router.post("/signout")
async def signout() -> dict:
    """
    User sign out endpoint.
    
    Signs out the current user. Client should discard tokens.
    
    Returns:
        Success message
    """
    return {
        "success": True,
        "message": "Sign out successful. Discard your tokens on the client."
    }


@router.post("/refresh-token")
async def refresh_token(refresh_token: str) -> AuthResponse:
    """
    Refresh access token endpoint.
    
    Gets a new access token using a refresh token.
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        AuthResponse with new access token
    """
    try:
        supabase = get_supabase_client()
        
        response = supabase.auth.refresh_session(refresh_token)
        
        if response.session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        session = response.session
        user = response.user
        
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at if hasattr(user, 'created_at') else None
        )
        
        return AuthResponse(
            success=True,
            message="Token refreshed successfully",
            user=user_response,
            access_token=session.access_token,
            refresh_token=session.refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: TokenPayload = Depends(get_current_user)
) -> UserResponse:
    """
    Get current authenticated user information.

    Requires valid JWT token in Authorization header.

    Returns:
        UserResponse with current user data
    """
    try:
        supabase = get_supabase_client()

        # Fetch user data from Supabase
        response = supabase.auth.get_user(
            supabase.auth._get_session().access_token if supabase.auth._get_session() else None
        )

        # If we can't get user from session, use the token payload
        return UserResponse(
            id=current_user.sub,
            email=current_user.email or "",
            created_at=None,  # Not available in token
            last_sign_in_at=None
        )

    except Exception as e:
        # Fallback to token payload data
        return UserResponse(
            id=current_user.sub,
            email=current_user.email or "",
            created_at=None,
            last_sign_in_at=None
        )


@router.post("/phone/send-otp", response_model=OTPResponse)
async def send_phone_otp(request: PhoneSignUpRequest) -> OTPResponse:
    """
    Send OTP to phone number for authentication.

    Args:
        request: PhoneSignUpRequest containing phone number in E.164 format

    Returns:
        OTPResponse with success status
    """
    try:
        supabase = get_supabase_client()

        # Send OTP via Supabase phone auth
        response = supabase.auth.sign_in_with_otp({
            "phone": request.phone
        })

        return OTPResponse(
            success=True,
            message="OTP sent successfully. Check your phone for the verification code.",
            message_id=getattr(response, 'message_id', None)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send OTP: {str(e)}"
        )


@router.post("/phone/verify-otp", response_model=AuthResponse)
async def verify_phone_otp(request: PhoneVerifyRequest) -> AuthResponse:
    """
    Verify phone OTP and authenticate user.

    Args:
        request: PhoneVerifyRequest containing phone and OTP

    Returns:
        AuthResponse with user data and tokens
    """
    try:
        supabase = get_supabase_client()

        # Verify OTP via Supabase
        response = supabase.auth.verify_otp({
            "phone": request.phone,
            "token": request.otp,
            "type": "sms"
        })

        if response.user is None or response.session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP"
            )

        user = response.user
        session = response.session

        user_response = UserResponse(
            id=user.id,
            email=user.email or "",
            created_at=user.created_at if hasattr(user, 'created_at') else None,
            last_sign_in_at=user.last_sign_in_at if hasattr(user, 'last_sign_in_at') else None
        )

        return AuthResponse(
            success=True,
            message="Phone verification successful",
            user=user_response,
            access_token=session.access_token,
            refresh_token=session.refresh_token
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OTP verification failed: {str(e)}"
        )
