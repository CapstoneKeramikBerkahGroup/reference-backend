from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import datetime
from uuid import uuid4
import base64

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
    
    # Return relative URL for frontend to construct proper request
    file_url = f"/{file_path}" 

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
            file_url=f"/{d.file_path}"
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
            file_url=f"/{d.file_path}"
        ))
    return results


# ENDPOINT BARU: Return PDF as base64 to completely bypass IDM
@router.get("/base64/{draft_id}")
def get_draft_pdf_base64(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return PDF as base64 encoded string to bypass IDM"""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Check file exists
    file_path = draft.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Read file and encode as base64
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    return JSONResponse(
        content={
            "data": pdf_base64,
            "filename": f"{draft.title}.pdf",
            "size": len(pdf_bytes)
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


# ENDPOINT: Download PDF directly
@router.get("/download/{draft_id}")
def download_draft_pdf(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download PDF file with proper headers"""
    from fastapi.responses import FileResponse
    
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Check file exists
    file_path = draft.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{draft.title}.pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{draft.title}.pdf"',
            "Access-Control-Allow-Origin": "*",
        }
    )


# ENDPOINT: Approve draft (Dosen Only) - Selesai Review / Layak
@router.patch("/{draft_id}/approve")
async def approve_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dosen menyetujui draft (status approved - layak tanpa revisi)"""
    if current_user.role != "dosen":
        raise HTTPException(status_code=403, detail="Hanya dosen yang bisa approve draft")
    
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft tidak ditemukan")
    
    # Validasi: Dosen harus pembimbing mahasiswa ini
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == draft.mahasiswa_id).first()
    dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
    
    if not mahasiswa or mahasiswa.dosen_pembimbing_id != dosen.id:
        raise HTTPException(status_code=403, detail="Anda bukan pembimbing mahasiswa ini")
    
    # Update status ke approved
    draft.status = 'approved'
    db.commit()
    
    return {
        "message": "Draft disetujui - Mahasiswa tidak perlu revisi lagi",
        "status": "approved"
    }


# ENDPOINT: Ubah status draft kembali ke reviewed (batalkan approval)
@router.patch("/{draft_id}/unapprove")
async def unapprove_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Batalkan approval draft (kembalikan ke status reviewed)"""
    if current_user.role != "dosen":
        raise HTTPException(status_code=403, detail="Hanya dosen yang bisa mengubah status")
    
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft tidak ditemukan")
    
    # Validasi: Dosen harus pembimbing mahasiswa ini
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == draft.mahasiswa_id).first()
    dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
    
    if not mahasiswa or mahasiswa.dosen_pembimbing_id != dosen.id:
        raise HTTPException(status_code=403, detail="Anda bukan pembimbing mahasiswa ini")
    
    # Update status ke reviewed
    draft.status = 'reviewed'
    db.commit()
    
    return {
        "message": "Status dikembalikan ke reviewed - Mahasiswa perlu revisi",
        "status": "reviewed"
    }
