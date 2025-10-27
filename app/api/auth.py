from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.models import User, Mahasiswa, Dosen
from app.schemas import (
    UserCreate, UserResponse, UserLogin,
    MahasiswaCreate, MahasiswaResponse,
    DosenCreate, DosenResponse,
    Token, TokenData
)

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
        angkatan=mahasiswa_data.angkatan
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
        departemen=dosen_data.departemen
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
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout endpoint (client should delete token)"""
    return {"message": "Successfully logged out"}
