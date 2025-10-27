from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import datetime

from app.core.database import get_db
from app.core.config import settings
from app.models import Dokumen, Tag, Mahasiswa
from app.schemas import (
    DokumenResponse, DokumenDetailResponse,
    TagCreate, TagResponse,
    CatatanCreate, CatatanResponse
)
from app.api.auth import get_current_mahasiswa, get_current_dosen, get_current_user

router = APIRouter()


def save_upload_file(upload_file: UploadFile, mahasiswa_id: int) -> tuple:
    """Save uploaded file and return path and size"""
    
    # Validate file extension
    file_ext = upload_file.filename.split('.')[-1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Create mahasiswa directory
    mahasiswa_dir = os.path.join(settings.UPLOAD_DIR, f"mahasiswa_{mahasiswa_id}")
    os.makedirs(mahasiswa_dir, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{upload_file.filename}"
    file_path = os.path.join(mahasiswa_dir, filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    
    # Get file size in KB
    file_size_kb = os.path.getsize(file_path) // 1024
    
    # Check file size
    if file_size_kb > (settings.MAX_FILE_SIZE_MB * 1024):
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    return file_path, file_size_kb


# ============= Document Endpoints =============
@router.post("/upload", response_model=DokumenResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    judul: Optional[str] = Form(None),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Upload a new document (mahasiswa only)"""
    
    # Save file
    file_path, file_size_kb = save_upload_file(file, current_mahasiswa.id)
    
    # Get file format
    file_format = file.filename.split('.')[-1].lower()
    
    # Create document record
    dokumen = Dokumen(
        mahasiswa_id=current_mahasiswa.id,
        judul=judul or file.filename,
        nama_file=file.filename,
        path_file=file_path,
        format=file_format,
        ukuran_kb=file_size_kb,
        status_analisis="pending"
    )
    
    db.add(dokumen)
    db.commit()
    db.refresh(dokumen)
    
    return dokumen


@router.get("/", response_model=List[DokumenResponse])
async def get_all_documents(
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get all documents for current mahasiswa"""
    
    documents = db.query(Dokumen).filter(
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).offset(skip).limit(limit).all()
    
    return documents


@router.get("/{dokumen_id}", response_model=DokumenDetailResponse)
async def get_document_by_id(
    dokumen_id: int,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Get document details by ID"""
    
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return dokumen


@router.get("/{dokumen_id}/download")
async def download_document(
    dokumen_id: int,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Download document file"""
    
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not os.path.exists(dokumen.path_file):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    return FileResponse(
        path=dokumen.path_file,
        filename=dokumen.nama_file,
        media_type='application/octet-stream'
    )


@router.delete("/{dokumen_id}")
async def delete_document(
    dokumen_id: int,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Delete document"""
    
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete physical file
    if os.path.exists(dokumen.path_file):
        os.remove(dokumen.path_file)
    
    # Delete database record
    db.delete(dokumen)
    db.commit()
    
    return {"message": "Document deleted successfully"}


# ============= Tag Endpoints =============
@router.post("/{dokumen_id}/tags", response_model=DokumenResponse)
async def add_tag_to_document(
    dokumen_id: int,
    tag_data: TagCreate,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Add tag to document"""
    
    # Get document
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get or create tag
    tag = db.query(Tag).filter(Tag.nama == tag_data.nama.lower()).first()
    if not tag:
        tag = Tag(nama=tag_data.nama.lower())
        db.add(tag)
        db.commit()
        db.refresh(tag)
    
    # Add tag to document if not already added
    if tag not in dokumen.tags:
        dokumen.tags.append(tag)
        db.commit()
        db.refresh(dokumen)
    
    return dokumen


@router.delete("/{dokumen_id}/tags/{tag_id}")
async def remove_tag_from_document(
    dokumen_id: int,
    tag_id: int,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Remove tag from document"""
    
    # Get document
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get tag
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Remove tag from document
    if tag in dokumen.tags:
        dokumen.tags.remove(tag)
        db.commit()
    
    return {"message": "Tag removed successfully"}


@router.get("/tags/all", response_model=List[TagResponse])
async def get_all_tags(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get all available tags"""
    tags = db.query(Tag).offset(skip).limit(limit).all()
    return tags


# ============= Search Endpoint =============
@router.get("/search/", response_model=List[DokumenResponse])
async def search_documents(
    q: str,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Search documents by title or filename"""
    
    documents = db.query(Dokumen).filter(
        Dokumen.mahasiswa_id == current_mahasiswa.id,
        (Dokumen.judul.ilike(f"%{q}%")) | (Dokumen.nama_file.ilike(f"%{q}%"))
    ).all()
    
    return documents
