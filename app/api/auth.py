from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.config import settings
from app.models import User, Mahasiswa, Dosen
from app.schemas import (
    UserCreate, UserResponse, UserLogin,
    MahasiswaCreate, MahasiswaResponse,
    DosenCreate, DosenResponse,
    Token, TokenData,
    CaptchaResponse, LoginWithCaptcha,
    ForgotPasswordRequest, VerifyCodeRequest, ResetPasswordRequest,
    ProfileUpdateRequest, ChangePasswordRequest
)
from app.services.captcha_service import captcha_service
from app.services.redis_service import redis_service
from app.services.email_service import send_verification_email, send_password_changed_notification, generate_verification_code

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ============= Dependencies =============
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    # sub is string in JWT, convert back to int
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user


async def get_current_mahasiswa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Mahasiswa:
    """Get current mahasiswa (student authentication)"""
    if current_user.role != "mahasiswa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Mahasiswa role required."
        )
    
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(status_code=404, detail="Mahasiswa profile not found")
    
    return mahasiswa


async def get_current_dosen(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dosen:
    """Get current dosen (lecturer authentication)"""
    if current_user.role != "dosen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Dosen role required."
        )
    
    dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
    if not dosen:
        raise HTTPException(status_code=404, detail="Dosen profile not found")
    
    return dosen


# ============= Authentication Endpoints =============
@router.post("/register/mahasiswa", response_model=MahasiswaResponse, status_code=status.HTTP_201_CREATED)
async def register_mahasiswa(
    mahasiswa_data: MahasiswaCreate,
    db: Session = Depends(get_db)
):
    """Register new mahasiswa (student)"""
    
    # Check if email already exists
    if db.query(User).filter(User.email == mahasiswa_data.user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if NIM already exists
    if db.query(Mahasiswa).filter(Mahasiswa.nim == mahasiswa_data.nim).first():
        raise HTTPException(status_code=400, detail="NIM already registered")
    
    # Create user
    user = User(
        email=mahasiswa_data.user.email,
        nama=mahasiswa_data.user.nama,
        role="mahasiswa",
        hashed_password=get_password_hash(mahasiswa_data.user.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create mahasiswa profile
    mahasiswa = Mahasiswa(
        user_id=user.id,
        nim=mahasiswa_data.nim,
        program_studi=mahasiswa_data.program_studi,
        angkatan=mahasiswa_data.angkatan,
        bidang_keahlian=mahasiswa_data.bidang_keahlian
    )
    db.add(mahasiswa)
    db.commit()
    db.refresh(mahasiswa)
    
    return mahasiswa


@router.post("/register/dosen", response_model=DosenResponse, status_code=status.HTTP_201_CREATED)
async def register_dosen(
    dosen_data: DosenCreate,
    db: Session = Depends(get_db)
):
    """Register new dosen (lecturer)"""
    
    # Check if email already exists
    if db.query(User).filter(User.email == dosen_data.user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if NIP already exists
    if db.query(Dosen).filter(Dosen.nip == dosen_data.nip).first():
        raise HTTPException(status_code=400, detail="NIP already registered")
    
    # Create user
    user = User(
        email=dosen_data.user.email,
        nama=dosen_data.user.nama,
        role="dosen",
        hashed_password=get_password_hash(dosen_data.user.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create dosen profile
    dosen = Dosen(
        user_id=user.id,
        nip=dosen_data.nip,
        jabatan=dosen_data.jabatan,
        bidang_keahlian=dosen_data.bidang_keahlian
    )
    db.add(dosen)
    db.commit()
    db.refresh(dosen)
    
    return dosen


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login endpoint (OAuth2 compatible)"""
    
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Create access token (sub must be string per JWT spec)
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    response = UserResponse.from_orm(current_user)
    
    # Add bidang_keahlian from mahasiswa or dosen profile
    if current_user.role == "mahasiswa":
        mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
        if mahasiswa:
            response.bidang_keahlian = mahasiswa.bidang_keahlian
    elif current_user.role == "dosen":
        dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
        if dosen:
            response.bidang_keahlian = dosen.bidang_keahlian
    
    return response


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout endpoint (client should delete token)"""
    return {"message": "Successfully logged out"}


# ============= CAPTCHA Endpoints =============

@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha():
    """
    Generate new CAPTCHA
    Returns session_id and base64 captcha image
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Create CAPTCHA
    captcha_data = captcha_service.create_captcha()
    
    # Store CAPTCHA text in Redis (5 minutes expiration)
    redis_service.store_captcha(session_id, captcha_data["text"], expire_minutes=5)
    
    return {
        "session_id": session_id,
        "captcha_image": captcha_data["image"]
    }


@router.post("/login/captcha", response_model=Token)
async def login_with_captcha(
    login_data: LoginWithCaptcha,
    db: Session = Depends(get_db)
):
    """
    Login with CAPTCHA validation
    Validates CAPTCHA before checking credentials
    """
    # 1. Validate CAPTCHA first
    stored_captcha = redis_service.get_captcha(login_data.session_id)
    
    if not stored_captcha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA expired or invalid. Please refresh CAPTCHA."
        )
    
    if not captcha_service.validate_captcha(login_data.captcha_text, stored_captcha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CAPTCHA. Please try again."
        )
    
    # Delete used CAPTCHA
    redis_service.delete_captcha(login_data.session_id)
    
    # 2. Check rate limiting (only in production)
    if not settings.DEBUG:
        rate_limit_key = f"login_attempts:{login_data.email}"
        if not redis_service.check_rate_limit(rate_limit_key, max_attempts=5, window_minutes=15):
            ttl = redis_service.get_rate_limit_ttl(rate_limit_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts. Please try again in {ttl // 60} minutes."
            )
    else:
        print(f"🔓 DEBUG MODE: Rate limiting disabled for login")
    
    # 3. Validate user credentials
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # 4. Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# ============= Forgot Password Endpoints =============

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset
    Sends verification code to email if user exists
    """
    # Check if user exists
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        # Don't reveal if email exists (security best practice)
        return {
            "message": "If the email exists, a verification code has been sent.",
            "success": True
        }
    
    # Check rate limiting (only in production)
    if not settings.DEBUG:
        rate_limit_key = f"forgot_password:{request.email}"
        if not redis_service.check_rate_limit(rate_limit_key, max_attempts=3, window_minutes=60):
            ttl = redis_service.get_rate_limit_ttl(rate_limit_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many password reset requests. Please try again in {ttl // 60} minutes."
            )
    else:
        print(f"🔓 DEBUG MODE: Rate limiting disabled for forgot password")
    
    # Generate verification code
    code = generate_verification_code(length=6)
    
    # Store code in Redis
    redis_service.store_verification_code(
        request.email, 
        code, 
        expire_minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
    )
    
    # Send email
    try:
        await send_verification_email(request.email, code, user.nama)
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")
        print(f"🔑 DEVELOPMENT MODE - Verification Code for {request.email}: {code}")
        
        # In development, don't fail - just log the code
        if settings.DEBUG:
            print(f"✅ Code stored in Redis for testing: {code}")
            # Continue without throwing error in DEBUG mode
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email. Please try again later."
            )
    
    return {
        "message": "Verification code sent to your email.",
        "success": True,
        "expires_in_minutes": settings.VERIFICATION_CODE_EXPIRE_MINUTES
    }


@router.post("/verify-code")
async def verify_code(request: VerifyCodeRequest):
    """
    Verify the code sent to email
    Returns success if code is valid
    """
    # Get stored verification data
    verify_data = redis_service.get_verification_code(request.email)
    
    if not verify_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code expired or not found. Please request a new code."
        )
    
    # Check max attempts (5 attempts allowed)
    if verify_data["attempts"] >= 5:
        redis_service.delete_verification_code(request.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many failed attempts. Please request a new verification code."
        )
    
    # Validate code
    if verify_data["code"] != request.code:
        # Increment failed attempts
        attempts = redis_service.increment_verification_attempts(request.email)
        remaining = 5 - attempts
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempts remaining."
        )
    
    return {
        "message": "Verification code is valid.",
        "success": True
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using verification code
    Validates code and updates password
    """
    # Get stored verification data
    verify_data = redis_service.get_verification_code(request.email)
    
    if not verify_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code expired or not found. Please request a new code."
        )
    
    # Check max attempts
    if verify_data["attempts"] >= 5:
        redis_service.delete_verification_code(request.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many failed attempts. Please request a new verification code."
        )
    
    # Validate code
    if verify_data["code"] != request.code:
        attempts = redis_service.increment_verification_attempts(request.email)
        remaining = 5 - attempts
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempts remaining."
        )
    
    # Get user
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    # Update password
    user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    
    # Delete verification code
    redis_service.delete_verification_code(request.email)
    
    # Send confirmation email
    try:
        await send_password_changed_notification(request.email, user.nama)
    except Exception as e:
        print(f"Failed to send confirmation email: {e}")
        # Don't fail the request if email fails
    
    return {
        "message": "Password reset successfully. You can now login with your new password.",
        "success": True
    }


# ============= Profile Management Endpoints =============

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile (name, email, and bidang_keahlian for dosen)
    """
    # Check if email is already taken by another user
    if request.email != current_user.email:
        existing_user = db.query(User).filter(User.email == request.email, User.id != current_user.id).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Update user
    current_user.nama = request.nama
    current_user.email = request.email
    
    # Update bidang_keahlian for dosen or mahasiswa
    if request.bidang_keahlian:
        if current_user.role == "dosen":
            dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
            if dosen:
                dosen.bidang_keahlian = request.bidang_keahlian
        elif current_user.role == "mahasiswa":
            mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
            if mahasiswa:
                mahasiswa.bidang_keahlian = request.bidang_keahlian
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password (requires current password)
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    hashed_password = get_password_hash(request.new_password)
    
    # Update password
    current_user.hashed_password = hashed_password
    
    db.commit()
    
    return {
        "message": "Password changed successfully",
        "success": True
    }
