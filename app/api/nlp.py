from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import asyncio

from app.core.database import get_db
from app.models import Dokumen, KataKunci, Referensi, Mahasiswa
from app.schemas import (
    KeywordExtractionRequest, KeywordExtractionResponse,
    SummarizationRequest, SummarizationResponse
)
from app.api.auth import get_current_mahasiswa
from app.services.nlp_service import nlp_service
from app.services.progress_tracker import (
    init_progress, update_progress, complete_progress, fail_progress, get_progress
)

router = APIRouter()


async def process_document_background(dokumen_id: int, db: Session):
    """Background task with progress tracking"""
    try:
        init_progress(dokumen_id)
        
        dokumen = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
        if not dokumen:
            fail_progress(dokumen_id, "Document not found")
            return
        
        # Step 1: Update status (10%)
        dokumen.status_analisis = "processing"
        db.commit()
        update_progress(dokumen_id, 10, "Starting processing...")
        await asyncio.sleep(0.5)  # Small delay to show progress
        
        # Step 2: Extract text (20%)
        update_progress(dokumen_id, 20, "Extracting text from document...")
        text = nlp_service.extract_text_from_file(dokumen.path_file)
        if not text:
            fail_progress(dokumen_id, "Failed to extract text")
            dokumen.status_analisis = "failed"
            db.commit()
            return
        await asyncio.sleep(0.5)  # Small delay to show progress
        
        # Step 3: Extract keywords (40%)
        update_progress(dokumen_id, 40, "Extracting keywords...")
        keywords = await nlp_service.extract_keywords(text, num_keywords=15)
        
        # Save keywords to database
        for keyword in keywords[:10]:  # Limit to 10 top keywords
            kata_kunci = db.query(KataKunci).filter(KataKunci.kata == keyword).first()
            if not kata_kunci:
                kata_kunci = KataKunci(kata=keyword, frekuensi=1)
                db.add(kata_kunci)
            else:
                kata_kunci.frekuensi += 1
            
            if kata_kunci not in dokumen.kata_kunci:
                dokumen.kata_kunci.append(kata_kunci)
        
        db.commit()
        await asyncio.sleep(0.5)  # Small delay to show progress
        
        # Step 4: Generate summary (60%)
        update_progress(dokumen_id, 60, "Generating summary...")
        summary = await nlp_service.generate_summary(text, max_length=200)
        dokumen.ringkasan = summary
        db.commit()
        await asyncio.sleep(0.5)  # Small delay to show progress
        
        # Step 5: Extract references (70%)
        update_progress(dokumen_id, 70, "Extracting references...")
        from app.services.custom_nlp import extract_references
        references = extract_references(text)
        
        # Delete existing references first to avoid duplicates
        db.query(Referensi).filter(Referensi.dokumen_id == dokumen.id).delete()
        
        # Save references to database
        for ref_data in references:
            referensi = Referensi(
                dokumen_id=dokumen.id,
                teks_referensi=ref_data["teks_referensi"]
            )
            db.add(referensi)
        
        db.commit()
        await asyncio.sleep(0.5)  # Small delay to show progress
        
        # Step 6: Generate embeddings (90%)
        update_progress(dokumen_id, 90, "Creating embeddings...")
        embedding = await nlp_service.generate_embedding(text)
        if embedding:
            # Store as JSON array in database
            import json
            dokumen.embeddings = json.dumps(embedding)
        
        db.commit()
        await asyncio.sleep(0.5)  # Small delay to show progress
        
        # Step 7: Complete (100%)
        dokumen.status_analisis = "completed"
        db.commit()
        complete_progress(dokumen_id, "Document processed successfully")
        
    except Exception as e:
        print(f"❌ Error processing document {dokumen_id}: {e}")
        fail_progress(dokumen_id, str(e))
        dokumen = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
        if dokumen:
            dokumen.status_analisis = "failed"
            db.commit()


# ============= NLP Endpoints =============
@router.post("/extract-keywords", response_model=KeywordExtractionResponse)
async def extract_keywords(
    request: KeywordExtractionRequest,
    background_tasks: BackgroundTasks,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Extract keywords from document"""
    
    # Get document
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == request.dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Extract text
    try:
        text = nlp_service.extract_text(dokumen.path_file, dokumen.format)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Extract keywords
    keywords = nlp_service.extract_keywords(text, top_k=request.top_k)
    
    # Save keywords to database
    for keyword in keywords:
        kata_kunci = db.query(KataKunci).filter(KataKunci.kata == keyword).first()
        if not kata_kunci:
            kata_kunci = KataKunci(kata=keyword, frekuensi=1)
            db.add(kata_kunci)
        else:
            kata_kunci.frekuensi += 1
        
        if kata_kunci not in dokumen.kata_kunci:
            dokumen.kata_kunci.append(kata_kunci)
    
    db.commit()
    
    return {
        "dokumen_id": dokumen.id,
        "keywords": keywords,
        "status": "completed"
    }


@router.post("/summarize", response_model=SummarizationResponse)
async def summarize_document(
    request: SummarizationRequest,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Generate summary for document"""
    
    # Get document
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == request.dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Extract text
    try:
        text = nlp_service.extract_text(dokumen.path_file, dokumen.format)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Generate summary
    summary = nlp_service.summarize_text(
        text,
        max_length=request.max_length,
        min_length=request.min_length
    )
    
    # Save summary
    dokumen.ringkasan = summary
    db.commit()
    
    return {
        "dokumen_id": dokumen.id,
        "summary": summary,
        "status": "completed"
    }


@router.post("/process/{dokumen_id}")
async def process_document(
    dokumen_id: int,
    background_tasks: BackgroundTasks,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Process document in background (extract keywords, summarize, extract references)"""
    
    # Get document
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Add background task
    background_tasks.add_task(process_document_background, dokumen_id, db)
    
    return {
        "message": "Document processing started",
        "dokumen_id": dokumen_id,
        "status": "processing"
    }


@router.get("/status/{dokumen_id}")
async def get_processing_status(
    dokumen_id: int,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Get document processing status"""
    
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get real-time progress if document is being processed
    progress_info = get_progress(dokumen_id)
    
    if progress_info and progress_info.get("status") == "processing":
        return {
            "dokumen_id": dokumen.id,
            "status": "processing",
            "progress": progress_info.get("progress", 0),
            "current_step": progress_info.get("current_step", ""),
            "started_at": progress_info.get("started_at"),
            "message": progress_info.get("message", "")
        }
    elif progress_info and progress_info.get("status") == "failed":
        return {
            "dokumen_id": dokumen.id,
            "status": "failed",
            "progress": 0,
            "error": progress_info.get("error", "Unknown error"),
            "message": progress_info.get("message", "")
        }
    
    # Document processing completed or not started
    return {
        "dokumen_id": dokumen.id,
        "status": dokumen.status_analisis or "pending",
        "progress": 100 if dokumen.status_analisis == "selesai" else 0,
        "has_summary": dokumen.ringkasan is not None,
        "keywords_count": len(dokumen.kata_kunci),
        "references_count": len(dokumen.referensi)
    }
