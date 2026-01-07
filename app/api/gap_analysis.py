from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.models import GapAnalysisHistory, Mahasiswa, User
from app.api.auth import get_current_user

router = APIRouter()

# --- Schemas ---
class GapSaveRequest(BaseModel):
    title: str
    result: Dict[str, Any]

class GapHistoryResponse(BaseModel):
    id: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Endpoints ---

@router.get("/list", response_model=List[GapHistoryResponse])
async def get_gap_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil list history analisis gap user ini"""
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(status_code=404, detail="Profil mahasiswa tidak ditemukan")

    history = db.query(GapAnalysisHistory).filter(
        GapAnalysisHistory.mahasiswa_id == mahasiswa.id
    ).order_by(GapAnalysisHistory.created_at.desc()).all()
    
    # Mapping manual agar aman (query_description -> title)
    return [{"id": h.id, "title": h.query_description, "created_at": h.created_at} for h in history]

@router.post("/save")
async def save_gap_analysis(
    req: GapSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(status_code=404, detail="Profil mahasiswa tidak ditemukan")

    new_entry = GapAnalysisHistory(
        mahasiswa_id=mahasiswa.id,
        query_description=req.title,
        result_json=req.result
    )
    db.add(new_entry)
    db.commit()
    return {"message": "Saved successfully"}

@router.get("/{history_id}")
async def get_gap_detail(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    history = db.query(GapAnalysisHistory).filter(GapAnalysisHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="History not found")
    return history.result_json