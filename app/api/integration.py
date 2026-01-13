from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List, Any, Union
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.models import User, UserZotero, ExternalReference
from app.services.zotero_service import zotero_service
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# ===== Schemas =====
class ZoteroConfigCreate(BaseModel):
    user_id_zotero: Union[str, int]
    api_key_zotero: str
    library_type: str = "user"

    @field_validator('user_id_zotero', mode='before')
    @classmethod
    def transform_to_string(cls, v):
        return str(v)
    
class ZoteroConfigResponse(BaseModel):
    id: int = 0
    user_id: int = 0
    zotero_user_id: str = ""
    library_type: str = "user"
    last_sync: Optional[datetime] = None
    class Config:
        from_attributes = True


# ===== Endpoints =====
@router.post("/zotero/config")
async def set_zotero_config(
    config: ZoteroConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save Zotero configuration"""
    try:
        if current_user.role != "mahasiswa":
            raise HTTPException(status_code=403, detail="Only mahasiswa can connect Zotero")

        z_id = str(config.user_id_zotero).strip()
        api_key = config.api_key_zotero.strip()
        
        # Validate inputs
        if not z_id or not api_key:
            raise HTTPException(status_code=400, detail="User ID and API Key are required")
        
        existing = db.query(UserZotero).filter(UserZotero.user_id == current_user.id).first()

        if existing:
            existing.zotero_user_id = z_id
            existing.api_key = api_key
            existing.library_type = config.library_type
            logger.info(f"Updated Zotero config for user {current_user.id}")
        else:
            new_config = UserZotero(
                user_id=current_user.id,
                zotero_user_id=z_id,
                api_key=api_key,
                library_type=config.library_type
            )
            db.add(new_config)
            logger.info(f"Created new Zotero config for user {current_user.id}")
        
        db.commit()
        
        if existing:
            db.refresh(existing)
        
        return {"message": "Zotero connected successfully!", "status": "success"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving Zotero config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save configuration: {str(e)}"
        )

@router.get("/zotero/config", response_model=ZoteroConfigResponse)
async def get_zotero_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil konfigurasi Zotero. Jika belum ada, kembalikan default dummy."""
    config = db.query(UserZotero).filter(UserZotero.user_id == current_user.id).first()
    
    if not config:
        return ZoteroConfigResponse(
            id=0,
            user_id=current_user.id,
            zotero_user_id="",
            library_type="user",
            last_sync=None
        )
    
    return config


@router.post("/zotero/sync")
async def sync_zotero_library(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sync items dari Zotero library"""
    
    if current_user.role != "mahasiswa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya mahasiswa yang dapat sync Zotero"
        )
    
    try:
        result = zotero_service.sync_library(current_user.id, db)
        return result
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/references")
async def get_external_references(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    source: str | None = None
):
    """Get all external references (dari Zotero/Mendeley)"""
    
    query = db.query(ExternalReference).filter(
        ExternalReference.user_id == current_user.id
    )
    
    if source:
        query = query.filter(ExternalReference.source == source)
    
    references = query.order_by(ExternalReference.id.desc()).all()
    
    return {
        "total": len(references),
        "data": [
            {
                "id": ref.id,
                "source": ref.source,
                "title": ref.title,
                "authors": ref.authors,
                "year": ref.year,
                "url": ref.url,
                "has_pdf": ref.has_pdf,
                "is_analyzed": ref.is_analyzed,
                "local_document_id": ref.local_document_id
            }
            for ref in references
        ]
    }


@router.post("/zotero/analyze/{ext_ref_id}")
async def analyze_zotero_document(
    ext_ref_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download dan analisis document dari Zotero"""
    
    if current_user.role != "mahasiswa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya mahasiswa yang dapat analyze document"
        )
    
    try:
        result = zotero_service.process_zotero_document(ext_ref_id, db, current_user.id)
        return result
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )