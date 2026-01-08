from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.models import User, Mahasiswa, Dosen, PembimbingRequest
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# ===== Schemas =====
class PembimbingRequestCreate(BaseModel):
    dosen_id: int
    pesan_mahasiswa: str = ""

class PembimbingRequestUpdate(BaseModel):
    status: str  # accepted or rejected
    pesan_dosen: str = ""

class PembimbingRequestResponse(BaseModel):
    id: int
    mahasiswa_id: int
    dosen_id: int
    status: str
    pesan_mahasiswa: str | None
    pesan_dosen: str | None
    created_at: datetime
    updated_at: datetime | None
    
    # Additional info
    mahasiswa_nama: str | None = None
    mahasiswa_nim: str | None = None
    mahasiswa_bidang_keahlian: str | None = None
    dosen_nama: str | None = None
    dosen_nip: str | None = None

    class Config:
        from_attributes = True


# ===== Endpoints untuk Mahasiswa =====
@router.post("/request", response_model=PembimbingRequestResponse)
def create_pembimbing_request(
    request_data: PembimbingRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mahasiswa membuat request pembimbing ke dosen"""
    
    # Validasi role mahasiswa
    if current_user.role != "mahasiswa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya mahasiswa yang dapat membuat request pembimbing"
        )
    
    # Dapatkan profil mahasiswa
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil mahasiswa tidak ditemukan"
        )
    
    # Cek apakah mahasiswa sudah memiliki dosen pembimbing
    if mahasiswa.dosen_pembimbing_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anda sudah memiliki dosen pembimbing"
        )
    
    # Cek apakah sudah ada request pending ke dosen yang sama
    existing_request = db.query(PembimbingRequest).filter(
        and_(
            PembimbingRequest.mahasiswa_id == mahasiswa.id,
            PembimbingRequest.dosen_id == request_data.dosen_id,
            PembimbingRequest.status == 'pending'
        )
    ).first()
    
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anda sudah memiliki request pending ke dosen ini"
        )
    
    # Validasi dosen exists
    dosen = db.query(Dosen).filter(Dosen.id == request_data.dosen_id).first()
    if not dosen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dosen tidak ditemukan"
        )
    
    # Buat request baru
    new_request = PembimbingRequest(
        mahasiswa_id=mahasiswa.id,
        dosen_id=request_data.dosen_id,
        pesan_mahasiswa=request_data.pesan_mahasiswa,
        status='pending'
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    # Ambil info tambahan
    response = PembimbingRequestResponse.from_orm(new_request)
    response.mahasiswa_nama = current_user.nama
    response.mahasiswa_nim = mahasiswa.nim
    response.mahasiswa_bidang_keahlian = mahasiswa.bidang_keahlian
    response.dosen_nama = dosen.user.nama
    response.dosen_nip = dosen.nip
    
    return response


@router.get("/my-requests", response_model=List[PembimbingRequestResponse])
def get_my_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mahasiswa melihat semua request yang pernah dibuat"""
    
    if current_user.role != "mahasiswa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint ini hanya untuk mahasiswa"
        )
    
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil mahasiswa tidak ditemukan"
        )
    
    requests = db.query(PembimbingRequest).filter(
        PembimbingRequest.mahasiswa_id == mahasiswa.id
    ).order_by(PembimbingRequest.created_at.desc()).all()
    
    result = []
    for req in requests:
        response = PembimbingRequestResponse.from_orm(req)
        response.mahasiswa_nama = current_user.nama
        response.mahasiswa_nim = mahasiswa.nim
        response.mahasiswa_bidang_keahlian = mahasiswa.bidang_keahlian
        
        dosen = db.query(Dosen).filter(Dosen.id == req.dosen_id).first()
        if dosen:
            response.dosen_nama = dosen.user.nama
            response.dosen_nip = dosen.nip
        
        result.append(response)
    
    return result


@router.delete("/request/{request_id}")
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mahasiswa cancel request yang masih pending"""
    
    if current_user.role != "mahasiswa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya mahasiswa yang dapat cancel request"
        )
    
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil mahasiswa tidak ditemukan"
        )
    
    request = db.query(PembimbingRequest).filter(
        and_(
            PembimbingRequest.id == request_id,
            PembimbingRequest.mahasiswa_id == mahasiswa.id,
            PembimbingRequest.status == 'pending'
        )
    ).first()
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request tidak ditemukan atau sudah diproses"
        )
    
    db.delete(request)
    db.commit()
    
    return {"message": "Request berhasil dibatalkan"}


# ===== Endpoints untuk Dosen =====
@router.get("/incoming-requests", response_model=List[PembimbingRequestResponse])
def get_incoming_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dosen melihat semua request pembimbing yang masuk"""
    
    if current_user.role != "dosen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint ini hanya untuk dosen"
        )
    
    dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
    if not dosen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil dosen tidak ditemukan"
        )
    
    requests = db.query(PembimbingRequest).filter(
        PembimbingRequest.dosen_id == dosen.id
    ).order_by(
        PembimbingRequest.status.asc(),  # pending first
        PembimbingRequest.created_at.desc()
    ).all()
    
    result = []
    for req in requests:
        response = PembimbingRequestResponse.from_orm(req)
        
        mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == req.mahasiswa_id).first()
        if mahasiswa:
            response.mahasiswa_nama = mahasiswa.user.nama
            response.mahasiswa_nim = mahasiswa.nim
            response.mahasiswa_bidang_keahlian = mahasiswa.bidang_keahlian
        
        response.dosen_nama = current_user.nama
        response.dosen_nip = dosen.nip
        
        result.append(response)
    
    return result


@router.put("/request/{request_id}/respond", response_model=PembimbingRequestResponse)
def respond_to_request(
    request_id: int,
    response_data: PembimbingRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dosen accept atau reject request pembimbing"""
    
    if current_user.role != "dosen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya dosen yang dapat merespon request"
        )
    
    dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
    if not dosen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil dosen tidak ditemukan"
        )
    
    request = db.query(PembimbingRequest).filter(
        and_(
            PembimbingRequest.id == request_id,
            PembimbingRequest.dosen_id == dosen.id,
            PembimbingRequest.status == 'pending'
        )
    ).first()
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request tidak ditemukan atau sudah diproses"
        )
    
    # Validasi status
    if response_data.status not in ['accepted', 'rejected']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status harus 'accepted' atau 'rejected'"
        )
    
    # Update request
    request.status = response_data.status
    request.pesan_dosen = response_data.pesan_dosen
    
    # Jika accepted, set dosen sebagai pembimbing
    if response_data.status == 'accepted':
        mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == request.mahasiswa_id).first()
        if mahasiswa:
            # Cek apakah mahasiswa sudah punya pembimbing
            if mahasiswa.dosen_pembimbing_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mahasiswa sudah memiliki dosen pembimbing lain"
                )
            mahasiswa.dosen_pembimbing_id = dosen.id
            
            # Reject semua request pending lainnya dari mahasiswa ini
            other_requests = db.query(PembimbingRequest).filter(
                and_(
                    PembimbingRequest.mahasiswa_id == mahasiswa.id,
                    PembimbingRequest.id != request_id,
                    PembimbingRequest.status == 'pending'
                )
            ).all()
            
            for other_req in other_requests:
                other_req.status = 'rejected'
                other_req.pesan_dosen = "Mahasiswa sudah diterima oleh dosen lain"
    
    db.commit()
    db.refresh(request)
    
    # Ambil info tambahan
    response = PembimbingRequestResponse.from_orm(request)
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == request.mahasiswa_id).first()
    if mahasiswa:
        response.mahasiswa_nama = mahasiswa.user.nama
        response.mahasiswa_nim = mahasiswa.nim
    response.dosen_nama = current_user.nama
    response.dosen_nip = dosen.nip
    
    return response


@router.get("/my-bimbingan", response_model=List[dict])
def get_my_bimbingan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dosen melihat semua mahasiswa bimbingannya"""
    
    if current_user.role != "dosen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint ini hanya untuk dosen"
        )
    
    dosen = db.query(Dosen).filter(Dosen.user_id == current_user.id).first()
    if not dosen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil dosen tidak ditemukan"
        )
    
    mahasiswa_list = db.query(Mahasiswa).filter(
        Mahasiswa.dosen_pembimbing_id == dosen.id
    ).all()
    
    result = []
    for mhs in mahasiswa_list:
        result.append({
            "id": mhs.id,
            "nim": mhs.nim,
            "nama": mhs.user.nama,
            "email": mhs.user.email,
            "program_studi": mhs.program_studi,
            "angkatan": mhs.angkatan
        })
    
    return result
