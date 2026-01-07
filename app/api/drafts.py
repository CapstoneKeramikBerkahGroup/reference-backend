from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import datetime
from uuid import uuid4

from app.core.database import get_db
from app.api.auth import get_current_user, get_current_dosen
from app.models.models import User, Mahasiswa, Draft, DraftComment, Dosen
from pydantic import BaseModel

router = APIRouter()

# --- Schemas ---
class DraftResponse(BaseModel):
    id: int
    title: str
    version: int
    status: str
    created_at: datetime
    file_url: str

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None      
    quoted_text: Optional[str] = None   
    page_number: Optional[int] = None

class CommentResponse(BaseModel):
    id: int
    user_name: str
    user_role: str
    content: str
    created_at: datetime
    parent_id: Optional[int] = None
    quoted_text: Optional[str] = None
    page_number: Optional[int] = None   
    
    class Config:
        from_attributes = True

# --- Endpoints ---

@router.post("/upload", response_model=DraftResponse)
async def upload_draft(
    title: str = Form(...),
    version: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload draft skripsi baru (PDF)"""
    if current_user.role != "mahasiswa":
        raise HTTPException(status_code=403, detail="Hanya mahasiswa bisa upload draft")

    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(status_code=404, detail="Profil mahasiswa tidak ditemukan")

    # 1. Validasi File
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Hanya file PDF yang diizinkan")

    # 2. Simpan File
    upload_dir = "uploads/drafts"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate nama file unik: NIM_Version_Random.pdf
    file_ext = os.path.splitext(file.filename)[1]
    unique_name = f"{mahasiswa.nim}_v{version}_{uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(upload_dir, unique_name)
    
    try:
        await file.seek(0)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan file: {str(e)}")

    # 3. Simpan ke Database
    new_draft = Draft(
        mahasiswa_id=mahasiswa.id,
        title=title,
        version=version,
        file_path=file_path, # Simpan relative path
        status='pending'
    )
    db.add(new_draft)
    db.commit()
    db.refresh(new_draft)
    
    # Construct URL untuk frontend (sesuaikan domain/port jika perlu)
    # Kita asumsikan folder 'uploads' di-mount di root static files
    file_url = f"http://localhost:8000/{file_path}" 

    return DraftResponse(
        id=new_draft.id,
        title=new_draft.title,
        version=new_draft.version,
        status=new_draft.status,
        created_at=new_draft.created_at,
        file_url=file_url
    )

@router.get("/my-drafts", response_model=List[DraftResponse])
async def get_my_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil list draft milik user login"""
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        return []

    drafts = db.query(Draft).filter(Draft.mahasiswa_id == mahasiswa.id).order_by(Draft.version.desc()).all()
    
    results = []
    for d in drafts:
        results.append(DraftResponse(
            id=d.id,
            title=d.title,
            version=d.version,
            status=d.status,
            created_at=d.created_at,
            file_url=f"http://localhost:8000/{d.file_path}"
        ))
    return results

@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Hapus komentar (hanya pemilik komentar)"""
    comment = db.query(DraftComment).filter(DraftComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Komentar tidak ditemukan")
    
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Tidak berhak menghapus komentar ini")
    
    db.delete(comment)
    db.commit()
    return {"message": "Komentar dihapus"}

@router.get("/{draft_id}/comments", response_model=List[CommentResponse])
async def get_draft_comments(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil komentar pada draft tertentu"""
    comments = db.query(DraftComment).filter(DraftComment.draft_id == draft_id).order_by(DraftComment.created_at.asc()).all()
    
    results = []
    for c in comments:
        # Ambil nama user yg komen
        user = db.query(User).filter(User.id == c.user_id).first()
        
        results.append(CommentResponse(
            id=c.id,
            user_name=user.nama if user else "Unknown",
            user_role=user.role if user else "unknown",
            content=c.content,
            created_at=c.created_at,
            # --- BAGIAN INI YANG HILANG SEBELUMNYA ---
            parent_id=c.parent_id,
            quoted_text=c.quoted_text,
            page_number=c.page_number
            # -----------------------------------------
        ))
    return results

@router.post("/{draft_id}/comments")
async def post_comment(
    draft_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kirim komentar baru atau balasan"""
    new_comment = DraftComment(
        draft_id=draft_id,
        user_id=current_user.id,
        content=comment.content,
        parent_id=comment.parent_id,       # Baru
        quoted_text=comment.quoted_text,   # Baru
        page_number=comment.page_number    # Baru
    )
    db.add(new_comment)
    db.commit()
    return {"message": "Komentar terkirim"}

@router.get("/student/{mahasiswa_id}", response_model=List[DraftResponse])
async def get_student_drafts(
    mahasiswa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Bisa dosen atau mhs
):
    """Ambil draft milik mahasiswa tertentu (untuk Dosen)"""
    # Validasi akses: Pastikan user adalah Dosen pembimbing dari mahasiswa ini
    if current_user.role == "dosen":
        dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
        mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == mahasiswa_id).first()
        
        if not mahasiswa or mahasiswa.dosen_pembimbing_id != dosen.id:
            raise HTTPException(status_code=403, detail="Anda bukan pembimbing mahasiswa ini")
            
    elif current_user.role == "mahasiswa":
        # Mahasiswa hanya boleh lihat punya sendiri (Self check)
        mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
        if not mahasiswa or mahasiswa.id != mahasiswa_id:
             raise HTTPException(status_code=403, detail="Akses ditolak")
    
    drafts = db.query(Draft).filter(Draft.mahasiswa_id == mahasiswa_id).order_by(Draft.version.desc()).all()
    
    results = []
    for d in drafts:
        results.append(DraftResponse(
            id=d.id,
            title=d.title,
            version=d.version,
            status=d.status,
            created_at=d.created_at,
            file_url=f"http://localhost:8000/{d.file_path}"
        ))
    return results