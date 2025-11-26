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
    
    class Config:
        from_attributes = True


# ============= Mahasiswa Schemas =============
class MahasiswaBase(BaseModel):
    nim: str
    program_studi: Optional[str] = None
    angkatan: Optional[int] = None


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
