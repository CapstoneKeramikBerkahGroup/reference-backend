from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ============= User Schemas =============
class UserBase(BaseModel):
    email: EmailStr
    nama: str
    role: str = Field(..., pattern="^(mahasiswa|dosen)$")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    bidang_keahlian: Optional[str] = None  # From mahasiswa or dosen profile
    
    class Config:
        from_attributes = True


# ============= Mahasiswa Schemas =============
class MahasiswaBase(BaseModel):
    nim: str
    program_studi: Optional[str] = None
    angkatan: Optional[int] = None
    bidang_keahlian: Optional[str] = None


class MahasiswaCreate(MahasiswaBase):
    user: UserCreate


class MahasiswaResponse(MahasiswaBase):
    id: int
    user_id: int
    user: UserResponse
    
    class Config:
        from_attributes = True


# ============= Dosen Schemas =============
class DosenBase(BaseModel):
    nip: str
    jabatan: Optional[str] = None
    bidang_keahlian: Optional[str] = None


class DosenCreate(DosenBase):
    user: UserCreate


class DosenResponse(DosenBase):
    id: int
    user_id: int
    user: UserResponse
    
    class Config:
        from_attributes = True


# ============= Auth Schemas =============
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None


# ============= CAPTCHA Schemas =============
class CaptchaResponse(BaseModel):
    session_id: str
    captcha_image: str  # base64 data URL


class LoginWithCaptcha(BaseModel):
    email: EmailStr
    password: str
    captcha_text: str
    session_id: str


# ============= Forgot Password Schemas =============
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6)


class ProfileUpdateRequest(BaseModel):
    nama: str = Field(..., min_length=1)
    email: EmailStr
    bidang_keahlian: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)
