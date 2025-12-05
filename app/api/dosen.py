from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date
from sqlalchemy import or_, func

from app.core.database import get_db
from app.api.auth import get_current_dosen, get_current_user
from app.models import Dosen, Mahasiswa, Dokumen, Catatan, Referensi, User
from app.schemas import (
    CatatanCreate, CatatanUpdate, CatatanResponse,
    DokumenResponse, DokumenDetailResponse,
    ReferensiValidationRequest, ReferensiResponse
)

router = APIRouter()


# ============= Public Dosen Endpoints =============
@router.get("/available-dosen")
async def get_available_dosen(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of available dosen for mahasiswa to choose from"""
    
    # Get all dosen with their current bimbingan count
    dosen_list = db.query(
        Dosen,
        func.count(Mahasiswa.id).label('jumlah_bimbingan')
    ).outerjoin(
        Mahasiswa, Mahasiswa.dosen_pembimbing_id == Dosen.id
    ).join(
        User, Dosen.user_id == User.id
    ).group_by(
        Dosen.id
    ).all()
    
    result = []
    for dosen, jumlah_bimbingan in dosen_list:
        result.append({
            "id": dosen.id,
            "nama": dosen.user.nama,
            "email": dosen.user.email,
            "nip": dosen.nip,
            "jabatan": dosen.jabatan,
            "bidang_keahlian": dosen.bidang_keahlian,
            "jumlah_bimbingan": jumlah_bimbingan
        })
    
    return result


# ============= Dashboard & Monitoring =============
@router.get("/dashboard/stats")
async def get_dosen_dashboard_stats(
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics for dosen"""
    
    # Hitung jumlah mahasiswa bimbingan
    total_mahasiswa = db.query(Mahasiswa).filter(
        Mahasiswa.dosen_pembimbing_id == current_dosen.id
    ).count()
    
    # Hitung total dokumen dari semua mahasiswa bimbingan
    total_dokumen = db.query(Dokumen).join(Mahasiswa).filter(
        Mahasiswa.dosen_pembimbing_id == current_dosen.id
    ).count()
    
    # Dokumen yang sudah dianalisis
    dokumen_completed = db.query(Dokumen).join(Mahasiswa).filter(
        Mahasiswa.dosen_pembimbing_id == current_dosen.id,
        Dokumen.status_analisis == 'completed'
    ).count()
    
    # Total catatan yang diberikan
    total_catatan = db.query(Catatan).filter(
        Catatan.dosen_id == current_dosen.id
    ).count()
    
    # Referensi yang perlu divalidasi
    referensi_pending = db.query(Referensi).join(Dokumen).join(Mahasiswa).filter(
        Mahasiswa.dosen_pembimbing_id == current_dosen.id,
        Referensi.status_validasi == 'pending'
    ).count()
    
    return {
        "total_mahasiswa": total_mahasiswa,
        "total_dokumen": total_dokumen,
        "dokumen_completed": dokumen_completed,
        "total_catatan": total_catatan,
        "referensi_pending": referensi_pending
    }


# ============= Mahasiswa Bimbingan =============
@router.get("/mahasiswa")
async def get_mahasiswa_bimbingan(
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Get list of mahasiswa under supervision"""
    
    mahasiswa_list = db.query(Mahasiswa).options(
        joinedload(Mahasiswa.user),
        joinedload(Mahasiswa.dokumen)
    ).filter(
        Mahasiswa.dosen_pembimbing_id == current_dosen.id
    ).all()
    
    result = []
    for mhs in mahasiswa_list:
        total_docs = len(mhs.dokumen)
        completed_docs = sum(1 for doc in mhs.dokumen if doc.status_analisis == 'completed')
        
        result.append({
            "id": mhs.id,
            "nim": mhs.nim,
            "nama": mhs.user.nama,
            "email": mhs.user.email,
            "program_studi": mhs.program_studi,
            "angkatan": mhs.angkatan,
            "total_dokumen": total_docs,
            "dokumen_completed": completed_docs
        })
    
    return result


@router.get("/mahasiswa/{mahasiswa_id}/dokumen", response_model=List[DokumenResponse])
async def get_mahasiswa_documents(
    mahasiswa_id: int,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Get all documents from a specific mahasiswa"""
    
    # Verify mahasiswa is under this dosen's supervision
    mahasiswa = db.query(Mahasiswa).filter(
        Mahasiswa.id == mahasiswa_id,
        Mahasiswa.dosen_pembimbing_id == current_dosen.id
    ).first()
    
    if not mahasiswa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mahasiswa not found or not under your supervision"
        )
    
    dokumen_list = db.query(Dokumen).options(
        joinedload(Dokumen.tags),
        joinedload(Dokumen.kata_kunci),
        joinedload(Dokumen.referensi)
    ).filter(
        Dokumen.mahasiswa_id == mahasiswa_id
    ).all()
    
    return dokumen_list


# ============= Dokumen Detail =============
@router.get("/dokumen/{dokumen_id}", response_model=DokumenDetailResponse)
async def get_dokumen_detail(
    dokumen_id: int,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Get document detail with catatan"""
    
    dokumen = db.query(Dokumen).options(
        joinedload(Dokumen.mahasiswa).joinedload(Mahasiswa.user),
        joinedload(Dokumen.tags),
        joinedload(Dokumen.kata_kunci),
        joinedload(Dokumen.referensi),
        joinedload(Dokumen.catatan)
    ).filter(Dokumen.id == dokumen_id).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Dokumen not found")
    
    # Verify dokumen belongs to mahasiswa under supervision
    if dokumen.mahasiswa.dosen_pembimbing_id != current_dosen.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This document is not under your supervision."
        )
    
    return dokumen


# ============= Catatan (Comments) =============
@router.post("/dokumen/{dokumen_id}/catatan", response_model=CatatanResponse, status_code=status.HTTP_201_CREATED)
async def add_catatan(
    dokumen_id: int,
    catatan_data: CatatanCreate,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Add comment/note to a document"""
    
    # Verify dokumen exists and is under supervision
    dokumen = db.query(Dokumen).join(Mahasiswa).filter(
        Dokumen.id == dokumen_id,
        Mahasiswa.dosen_pembimbing_id == current_dosen.id
    ).first()
    
    if not dokumen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dokumen not found or not under your supervision"
        )
    
    # Create catatan
    catatan = Catatan(
        dokumen_id=dokumen_id,
        dosen_id=current_dosen.id,
        isi_catatan=catatan_data.isi_catatan,
        halaman=catatan_data.halaman
    )
    
    db.add(catatan)
    db.commit()
    db.refresh(catatan)
    
    return catatan


@router.get("/dokumen/{dokumen_id}/catatan", response_model=List[CatatanResponse])
async def get_catatan_by_dokumen(
    dokumen_id: int,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Get all catatan for a document"""
    
    # Verify access
    dokumen = db.query(Dokumen).join(Mahasiswa).filter(
        Dokumen.id == dokumen_id,
        Mahasiswa.dosen_pembimbing_id == current_dosen.id
    ).first()
    
    if not dokumen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dokumen not found or not under your supervision"
        )
    
    catatan_list = db.query(Catatan).filter(
        Catatan.dokumen_id == dokumen_id
    ).order_by(Catatan.created_at.desc()).all()
    
    return catatan_list


@router.put("/catatan/{catatan_id}", response_model=CatatanResponse)
async def update_catatan(
    catatan_id: int,
    catatan_data: CatatanUpdate,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Update existing catatan"""
    
    catatan = db.query(Catatan).filter(
        Catatan.id == catatan_id,
        Catatan.dosen_id == current_dosen.id
    ).first()
    
    if not catatan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Catatan not found or you don't have permission to edit"
        )
    
    catatan.isi_catatan = catatan_data.isi_catatan
    if catatan_data.halaman is not None:
        catatan.halaman = catatan_data.halaman
    
    db.commit()
    db.refresh(catatan)
    
    return catatan


@router.delete("/catatan/{catatan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_catatan(
    catatan_id: int,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Delete catatan"""
    
    catatan = db.query(Catatan).filter(
        Catatan.id == catatan_id,
        Catatan.dosen_id == current_dosen.id
    ).first()
    
    if not catatan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Catatan not found or you don't have permission to delete"
        )
    
    db.delete(catatan)
    db.commit()
    
    return None


# ============= Validasi Referensi =============
@router.put("/referensi/{referensi_id}/validate", response_model=ReferensiResponse)
async def validate_referensi(
    referensi_id: int,
    validation_data: ReferensiValidationRequest,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Validate or reject a reference"""
    
    # Get referensi with dokumen and mahasiswa
    referensi = db.query(Referensi).join(Dokumen).join(Mahasiswa).filter(
        Referensi.id == referensi_id,
        Mahasiswa.dosen_pembimbing_id == current_dosen.id
    ).first()
    
    if not referensi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referensi not found or not under your supervision"
        )
    
    # Update validation status
    if validation_data.status_validasi not in ['validated', 'rejected']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be 'validated' or 'rejected'"
        )
        
    referensi.status_validasi = validation_data.status_validasi
    referensi.catatan_validasi = validation_data.catatan_validasi
    
    db.commit()
    db.refresh(referensi)
    
    return referensi


@router.get("/referensi/pending")
async def get_pending_referensi(
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Get all referensi that need validation"""
    
    referensi_list = db.query(Referensi).join(Dokumen).join(Mahasiswa).options(
        joinedload(Referensi.dokumen).joinedload(Dokumen.mahasiswa).joinedload(Mahasiswa.user)
    ).filter(
        Mahasiswa.dosen_pembimbing_id == current_dosen.id,
        Referensi.status_validasi == 'pending'
    ).all()
    
    result = []
    for ref in referensi_list:
        result.append({
            "id": ref.id,
            "dokumen_id": ref.dokumen_id,
            "dokumen_judul": ref.dokumen.judul,
            "mahasiswa_nama": ref.dokumen.mahasiswa.user.nama,
            "teks_referensi": ref.teks_referensi,
            "penulis": ref.penulis,
            "tahun": ref.tahun,
            "judul_publikasi": ref.judul_publikasi,
            "nomor": ref.nomor,
            "status_validasi": ref.status_validasi
        })
    
    return result


@router.get("/referensi/history")
async def get_referensi_history(
    status: Optional[str] = Query(None, enum=['validated', 'rejected']),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Get history of validated/rejected references"""
    
    query = db.query(Referensi).join(Dokumen).join(Mahasiswa).join(User).options(
        joinedload(Referensi.dokumen).joinedload(Dokumen.mahasiswa).joinedload(Mahasiswa.user)
    ).filter(
        Mahasiswa.dosen_pembimbing_id == current_dosen.id,
        Referensi.status_validasi.in_(['validated', 'rejected'])
    )
    
    if status:
        query = query.filter(Referensi.status_validasi == status)
    
    if start_date:
        query = query.filter(Referensi.updated_at >= start_date)
        
    if end_date:
        query = query.filter(Referensi.updated_at <= end_date)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.nama.ilike(search_term),
                Dokumen.judul.ilike(search_term)
            )
        )
        
    referensi_history = query.order_by(Referensi.updated_at.desc()).all()
    
    result = []
    for ref in referensi_history:
        result.append({
            "id": ref.id,
            "dokumen_id": ref.dokumen_id,
            "dokumen_judul": ref.dokumen.judul,
            "mahasiswa_nama": ref.dokumen.mahasiswa.user.nama,
            "teks_referensi": ref.teks_referensi,
            "status_validasi": ref.status_validasi,
            "catatan_validasi": ref.catatan_validasi,
            "validated_at": ref.updated_at
        })
        
    return result


# ============= Mahasiswa Bimbingan Management =============

@router.post("/assign-mahasiswa/{mahasiswa_id}")
async def assign_mahasiswa_to_dosen(
    mahasiswa_id: int,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Assign a mahasiswa to current dosen as pembimbing"""
    
    # Get mahasiswa
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == mahasiswa_id).first()
    if not mahasiswa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mahasiswa tidak ditemukan"
        )
    
    # Check if mahasiswa already has a pembimbing
    if mahasiswa.dosen_pembimbing_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mahasiswa sudah memiliki dosen pembimbing"
        )
    
    # Assign dosen to mahasiswa
    mahasiswa.dosen_pembimbing_id = current_dosen.id
    db.commit()
    
    return {
        "message": "Mahasiswa berhasil ditambahkan ke bimbingan",
        "mahasiswa_id": mahasiswa_id,
        "dosen_id": current_dosen.id
    }


@router.delete("/remove-mahasiswa/{mahasiswa_id}")
async def remove_mahasiswa_from_dosen(
    mahasiswa_id: int,
    current_dosen: Dosen = Depends(get_current_dosen),
    db: Session = Depends(get_db)
):
    """Remove a mahasiswa from current dosen's bimbingan"""
    
    # Get mahasiswa
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.id == mahasiswa_id).first()
    if not mahasiswa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mahasiswa tidak ditemukan"
        )
    
    # Check if mahasiswa is under current dosen
    if mahasiswa.dosen_pembimbing_id != current_dosen.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mahasiswa bukan di bawah bimbingan Anda"
        )
    
    # Remove dosen from mahasiswa
    mahasiswa.dosen_pembimbing_id = None
    
    # Also update or delete pembimbing_request if exists
    from app.models.models import PembimbingRequest
    pembimbing_request = db.query(PembimbingRequest).filter(
        PembimbingRequest.mahasiswa_id == mahasiswa_id,
        PembimbingRequest.dosen_id == current_dosen.id,
        PembimbingRequest.status == 'accepted'
    ).first()
    
    if pembimbing_request:
        # Change status to rejected or delete the record
        pembimbing_request.status = 'rejected'
        pembimbing_request.pesan_dosen = 'Dihapus dari bimbingan oleh dosen'
    
    db.commit()
    
    return {
        "message": "Mahasiswa berhasil dihapus dari bimbingan",
        "mahasiswa_id": mahasiswa_id
    }