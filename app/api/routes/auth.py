from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
from app.config.settings import settings
from app.api.models.auth import (
    SignUpRequest,
    SignInRequest,
    AuthResponse,
    ErrorResponse,
    UserResponse,
    PhoneSignUpRequest,
    PhoneVerifyRequest,
    OTPResponse,
    PasswordValidationRequest,
    PasswordValidationResponse,
    UsernameAvailabilityResponse,
    RandomUsernameResponse,
    BloomFilterResponse,
    UsernameCheckRequest
)
from app.api.dependencies.auth import get_current_user, TokenPayload
from app.services.user_service import (
    validate_username,
    check_username_exists,
    sync_user_signup,
    sync_user_signin,
    sync_user_signout,
    get_user_by_uuid
)
from app.services.password_service import (
    validate_password,
    calculate_password_strength
)
from app.services.bloom_filter_service import (
    check_username_availability_fast,
    check_username_availability_definitive,
    get_bloom_filter_data,
    generate_random_username,
    generate_username_suggestions,
    add_username_to_filter
)

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
    User sign up endpoint with password validation and secure hashing.

    Creates a new user account with email, password, and username.
    - Password: 8+ chars, uppercase, lowercase, number, special char
    - Username: 6-18 chars, starts with letter, allows letters, numbers, _, -, .

    Args:
        request: SignUpRequest containing email, password, username, and optional full_name

    Returns:
        AuthResponse with user data and tokens
    """
    try:
        # Validate password complexity
        pwd_valid, pwd_error, pwd_issues = validate_password(request.password)
        if not pwd_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=pwd_error
            )

        # Validate username format
        is_valid, error_msg = validate_username(request.username)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Check username availability using Bloom filter (probabilistic check)
        # This is a soft check - actual uniqueness is enforced by DB constraints
        try:
            available, msg = check_username_availability_definitive(request.username)
            if not available:
                suggestions = generate_username_suggestions(request.username, count=3)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Username already taken. Suggestions: {', '.join(suggestions)}"
                )
        except HTTPException:
            raise
        except Exception:
            pass  # If Bloom filter check fails, proceed - DB will enforce uniqueness

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

        # Sync to auth_users_table
        sync_error = None
        try:
            sync_user_signup(
                user_uuid=user.id,
                email=user.email,
                username=request.username,
                name=request.full_name
            )
            add_username_to_filter(request.username)
        except Exception as e:
            sync_error = str(e)

        user_response = UserResponse(
            id=user.id,
            email=user.email,
            username=request.username.lower(),
            full_name=request.full_name,
            created_at=user.created_at if hasattr(user, 'created_at') else None
        )

        message = "Account created successfully. Check your email for verification."
        if sync_error:
            message = f"Account created but profile sync failed: {sync_error}"

        return AuthResponse(
            success=True,
            message=message,
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

        # Sync signin to auth_users_table (update last_login_at)
        try:
            sync_user_signin(user.id)
        except Exception as e:
            print(f"Warning: Could not sync signin: {e}")

        # Get user profile for username
        profile = get_user_by_uuid(user.id)

        user_response = UserResponse(
            id=user.id,
            email=user.email,
            username=profile.get("username") if profile else None,
            full_name=profile.get("name") if profile else None,
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
async def signout(
    current_user: TokenPayload = Depends(get_current_user)
) -> dict:
    """
    User sign out endpoint.

    Signs out the current user and updates auth_users_table.

    Returns:
        Success message
    """
    try:
        sync_user_signout(current_user.sub)
    except Exception as e:
        print(f"Warning: Could not sync signout: {e}")

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
    Get current authenticated user information from auth_users_table.

    Requires valid JWT token in Authorization header.

    Returns:
        UserResponse with current user data
    """
    # Fetch user profile from auth_users_table
    profile = get_user_by_uuid(current_user.sub)

    if profile:
        return UserResponse(
            id=current_user.sub,
            email=profile.get("email", current_user.email or ""),
            username=profile.get("username"),
            full_name=profile.get("name"),
            created_at=profile.get("created_at"),
            last_sign_in_at=profile.get("last_login_at")
        )

    # Fallback to token payload data
    return UserResponse(
        id=current_user.sub,
        email=current_user.email or "",
        created_at=None,
        last_sign_in_at=None
    )


@router.get("/profile")
async def get_user_profile(
    current_user: TokenPayload = Depends(get_current_user)
) -> dict:
    """
    Get full user profile from auth_users_table.

    Returns all profile fields including subscription status, verification status, etc.
    """
    profile = get_user_by_uuid(current_user.sub)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    return {
        "success": True,
        "profile": {
            "user_uuid": profile.get("user_uuid"),
            "username": profile.get("username"),
            "email": profile.get("email"),
            "name": profile.get("name"),
            "profile_image_url": profile.get("profile_image_url"),
            "subscription_status": profile.get("subscription_status"),
            "auth_user_role": profile.get("auth_user_role"),
            "is_verified": profile.get("is_verified"),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
            "last_login_at": profile.get("last_login_at"),
        }
    }


@router.put("/profile")
async def update_user_profile(
    current_user: TokenPayload = Depends(get_current_user),
    name: Optional[str] = None,
    profile_image_url: Optional[str] = None
) -> dict:
    """
    Update user profile in auth_users_table.

    Only allows updating name and profile_image_url.
    """
    from app.services.user_service import get_supabase_admin_client
    from datetime import datetime, timezone

    supabase = get_supabase_admin_client()

    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if name is not None:
        update_data["name"] = name
    if profile_image_url is not None:
        update_data["profile_image_url"] = profile_image_url

    try:
        result = supabase.table("auth_users_table").update(update_data).eq(
            "user_uuid", current_user.sub
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        return {
            "success": True,
            "message": "Profile updated",
            "profile": result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update profile: {str(e)}"
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


# =============================================================================
# Password Validation Endpoints
# =============================================================================

@router.post("/validate-password", response_model=PasswordValidationResponse)
async def validate_password_endpoint(request: PasswordValidationRequest) -> PasswordValidationResponse:
    """
    Validate password strength and complexity.

    Checks for:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    - No sequential or repeated patterns

    Args:
        request: PasswordValidationRequest with password to validate

    Returns:
        PasswordValidationResponse with validity, score, level, and issues
    """
    is_valid, error_msg, issues = validate_password(request.password)
    strength = calculate_password_strength(request.password)

    return PasswordValidationResponse(
        valid=is_valid,
        score=strength["score"],
        level=strength["level"],
        issues=issues,
        feedback=strength["feedback"]
    )


# =============================================================================
# Username Availability & Bloom Filter Endpoints
# =============================================================================

@router.post("/check-username", response_model=UsernameAvailabilityResponse)
async def check_username_endpoint(request: UsernameCheckRequest) -> UsernameAvailabilityResponse:
    """
    Check username availability using Bloom filter + database verification.

    Fast check using Bloom filter first, then confirms with database.
    Returns suggestions if username is taken.

    Args:
        request: UsernameCheckRequest with username to check

    Returns:
        UsernameAvailabilityResponse with availability status and suggestions
    """
    # Validate format first
    is_valid, error_msg = validate_username(request.username)
    if not is_valid:
        return UsernameAvailabilityResponse(
            username=request.username,
            available=False,
            message=error_msg,
            suggestions=None
        )

    # Check availability with Bloom filter + DB
    try:
        available, message = check_username_availability_definitive(request.username)
    except Exception as e:
        # If check fails, assume available (DB will enforce uniqueness on signup)
        print(f"Username check failed: {e}")
        available = True
        message = "Username appears available"

    suggestions = None
    if not available:
        try:
            suggestions = generate_username_suggestions(request.username, count=5)
        except Exception:
            suggestions = []

    return UsernameAvailabilityResponse(
        username=request.username,
        available=available,
        message=message,
        suggestions=suggestions
    )


@router.get("/check-username/{username}", response_model=UsernameAvailabilityResponse)
async def check_username_get(username: str) -> UsernameAvailabilityResponse:
    """
    Quick username availability check (GET endpoint for easier use).

    Uses Bloom filter for fast probabilistic check.

    Args:
        username: Username to check

    Returns:
        UsernameAvailabilityResponse with availability status
    """
    # Validate format first
    is_valid, error_msg = validate_username(username)
    if not is_valid:
        return UsernameAvailabilityResponse(
            username=username,
            available=False,
            message=error_msg,
            suggestions=None
        )

    # Check with Bloom filter + optional DB verification
    try:
        available, message = check_username_availability_definitive(username)
    except Exception as e:
        # If check fails, assume available (DB will enforce uniqueness on signup)
        print(f"Username check failed: {e}")
        available = True
        message = "Username appears available"

    suggestions = None
    if not available:
        try:
            suggestions = generate_username_suggestions(username, count=3)
        except Exception:
            suggestions = []

    return UsernameAvailabilityResponse(
        username=username,
        available=available,
        message=message,
        suggestions=suggestions
    )


@router.get("/generate-username", response_model=RandomUsernameResponse)
async def generate_username_endpoint() -> RandomUsernameResponse:
    """
    Generate a random available username.

    Creates a unique username using adjective_noun + number format.
    Verifies availability using Bloom filter.

    Returns:
        RandomUsernameResponse with generated username and additional suggestions
    """
    try:
        username = generate_random_username()

        # Ensure it's likely available using Bloom filter
        attempts = 0
        while attempts < 10:
            try:
                available, _ = check_username_availability_fast(username)
                if available:
                    break
            except Exception:
                # If check fails, just use the generated username
                break
            username = generate_random_username()
            attempts += 1

        # Generate additional suggestions
        suggestions = []
        for _ in range(4):
            try:
                suggestion = generate_random_username()
                available, _ = check_username_availability_fast(suggestion)
                if available and suggestion != username:
                    suggestions.append(suggestion)
            except Exception:
                # If check fails, still add the suggestion
                suggestion = generate_random_username()
                if suggestion != username:
                    suggestions.append(suggestion)

        return RandomUsernameResponse(
            username=username,
            suggestions=suggestions
        )
    except Exception as e:
        # Fallback: return a simple random username
        import random
        adjectives = ["swift", "bright", "cosmic", "cyber", "digital", "epic"]
        nouns = ["coder", "dragon", "eagle", "ninja", "phoenix", "wolf"]
        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        num = random.randint(10, 999)
        return RandomUsernameResponse(
            username=f"{adj}_{noun}{num}",
            suggestions=[]
        )


@router.get("/bloom-filter", response_model=BloomFilterResponse)
async def get_bloom_filter_endpoint() -> BloomFilterResponse:
    """
    Get Bloom filter data for client-side username checking.

    Client can use this to perform instant username availability checks
    without server round-trips. Note: Bloom filters have false positives,
    so final verification should still be done server-side.

    Returns:
        BloomFilterResponse with encoded filter data and metadata
    """
    from datetime import datetime, timezone

    try:
        data = get_bloom_filter_data()
        return BloomFilterResponse(
            filter_data=data["filter_data"],
            hash_count=data["hash_count"],
            size=data["size"],
            item_count=data["item_count"],
            last_updated=datetime.fromisoformat(data["last_updated"])
        )
    except Exception as e:
        # Return empty filter if initialization fails
        print(f"Bloom filter fetch failed: {e}")
        import base64
        import math
        empty_filter = base64.b64encode(bytearray(math.ceil(100000 / 8))).decode('utf-8')
        return BloomFilterResponse(
            filter_data=empty_filter,
            hash_count=7,
            size=100000,
            item_count=0,
            last_updated=datetime.now(timezone.utc)
        )
