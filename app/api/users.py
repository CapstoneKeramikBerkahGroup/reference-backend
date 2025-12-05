from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models import User, Mahasiswa, Dosen
from app.schemas import UserResponse, MahasiswaResponse, DosenResponse
from app.api.auth import get_current_user, get_current_dosen

router = APIRouter()


@router.get("/mahasiswa", response_model=List[MahasiswaResponse])
async def get_all_mahasiswa(
    current_user: User = Depends(get_current_dosen),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get all mahasiswa (dosen only)"""
    mahasiswa_list = db.query(Mahasiswa).offset(skip).limit(limit).all()
    return mahasiswa_list


@router.get("/mahasiswa/{mahasiswa_id}", response_model=MahasiswaResponse)
async def get_mahasiswa_by_id(
    mahasiswa_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get mahasiswa by ID"""
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == mahasiswa_id).first()
    if not mahasiswa:
        raise HTTPException(status_code=404, detail="Mahasiswa not found")
    return mahasiswa


@router.get("/dosen", response_model=List[DosenResponse])
async def get_all_dosen(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get all dosen"""
    dosen_list = db.query(Dosen).offset(skip).limit(limit).all()
    return dosen_list


@router.put("/mahasiswa/choose-dosen/{dosen_id}")
async def choose_dosen_pembimbing(
    dosen_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mahasiswa memilih dosen pembimbing"""
    # Pastikan user adalah mahasiswa
    if current_user.role != "mahasiswa":
        raise HTTPException(
            status_code=403,
            detail="Only mahasiswa can choose dosen pembimbing"
        )
    
    # Get mahasiswa profile
    mahasiswa = db.query(Mahasiswa).filter(
        Mahasiswa.user_id == current_user.id
    ).first()
    
    if not mahasiswa:
        raise HTTPException(status_code=404, detail="Mahasiswa profile not found")
    
    # Verify dosen exists
    dosen = db.query(Dosen).filter(Dosen.id == dosen_id).first()
    if not dosen:
        raise HTTPException(status_code=404, detail="Dosen not found")
    
    # Update dosen pembimbing
    mahasiswa.dosen_pembimbing_id = dosen_id
    db.commit()
    db.refresh(mahasiswa)
    
    return {
        "message": "Dosen pembimbing successfully selected",
        "dosen_id": dosen_id,
        "dosen_nama": dosen.user.nama
    }
