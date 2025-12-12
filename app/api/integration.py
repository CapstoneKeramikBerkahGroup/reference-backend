from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.auth import get_current_user, get_current_mahasiswa
from app.services.zotero_service import zotero_service
from app.models import UserZotero, ExternalReference, Mahasiswa
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

# Schema untuk Request
class ZoteroConnectRequest(BaseModel):
    user_id_zotero: str
    api_key_zotero: str

# Schema untuk Response (Sederhana)
class ReferenceResponse(BaseModel):
    id: int
    title: str
    authors: str
    year: str
    source: str
    
    class Config:
        from_attributes = True

@router.post("/zotero/connect")
async def connect_zotero(
    payload: ZoteroConnectRequest,
    db: Session = Depends(get_db),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa)
):
    """Menyimpan API Key Zotero user ke database"""
    existing = db.query(UserZotero).filter(UserZotero.user_id == current_mahasiswa.user_id).first()
    
    if existing:
        existing.zotero_user_id = payload.user_id_zotero
        existing.api_key = payload.api_key_zotero
    else:
        new_conn = UserZotero(
            user_id=current_mahasiswa.user_id,
            zotero_user_id=payload.user_id_zotero,
            api_key=payload.api_key_zotero
        )
        db.add(new_conn)
    
    db.commit()
    return {"message": "Zotero connected successfully"}

@router.post("/zotero/sync")
async def sync_zotero(
    db: Session = Depends(get_db),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa)
):
    """Memicu proses sinkronisasi manual"""
    try:
        result = zotero_service.sync_library(current_mahasiswa.user_id, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/references", response_model=List[ReferenceResponse])
async def get_external_references(
    db: Session = Depends(get_db),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa)
):
    """Mengambil list referensi untuk ditampilkan di Draft TA"""
    refs = db.query(ExternalReference).filter(ExternalReference.user_id == current_mahasiswa.user_id).all()
    return refs

@router.post("/zotero/analyze/{ref_id}")
async def analyze_zotero_reference(
    ref_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa)
):
    """
    Mengubah item Zotero menjadi Dokumen lokal dan memulai analisis AI.
    """
    try:
        # 1. Download & Convert ke Dokumen
        result = zotero_service.process_zotero_document(ref_id, db, current_mahasiswa.user_id)
        doc_id = result['document_id']

        # 2. Trigger AI Processing (sama seperti saat upload manual)
        # Import fungsi background task dari nlp.py (hindari circular import dengan import di dalam fungsi atau pindahkan logic)
        from app.api.nlp import process_document_background
        background_tasks.add_task(process_document_background, doc_id, db)

        return {"message": "Processing started", "document_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/zotero/config")
async def get_zotero_config(
    db: Session = Depends(get_db),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa)
):
    """
    Get Zotero configuration for current user
    """
    config = db.query(UserZotero).filter(UserZotero.user_id == current_mahasiswa.user_id).first()
    
    if not config:
        return {"api_key": "", "user_id": ""}
    
    return {
        "api_key": config.api_key,
        "user_id": config.zotero_user_id
    }

@router.post("/zotero/config")
async def save_zotero_config(
    payload: ZoteroConnectRequest,
    db: Session = Depends(get_db),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa)
):
    """
    Save Zotero configuration (alias for /zotero/connect)
    """
    existing = db.query(UserZotero).filter(UserZotero.user_id == current_mahasiswa.user_id).first()
    
    if existing:
        existing.zotero_user_id = payload.user_id_zotero
        existing.api_key = payload.api_key_zotero
    else:
        new_conn = UserZotero(
            user_id=current_mahasiswa.user_id,
            zotero_user_id=payload.user_id_zotero,
            api_key=payload.api_key_zotero
        )
        db.add(new_conn)
    
    db.commit()
    return {"message": "Zotero configuration saved successfully"}

@router.post("/zotero/disconnect")
async def disconnect_zotero(
    db: Session = Depends(get_db),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa)
):
    """
    Disconnect Zotero account
    """
    config = db.query(UserZotero).filter(UserZotero.user_id == current_mahasiswa.user_id).first()
    
    if config:
        db.delete(config)
        db.commit()
    
    return {"message": "Zotero disconnected successfully"}