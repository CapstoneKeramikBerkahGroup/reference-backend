from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging
from pydantic import BaseModel

# Import Database & Models
from app.core.database import get_db
# Pastikan model Referensi diimport dari app.models
from app.models import Dokumen, KataKunci, Referensi, Mahasiswa, DokumenKata 
from app.api.auth import get_current_user
from app.api.auth import get_current_mahasiswa
from app.services.custom_nlp import generate_thesis_outline


# Import Schemas
from app.schemas import (
    KeywordExtractionRequest, KeywordExtractionResponse,
    SummarizationRequest, SummarizationResponse
)

# Import Servicen
from app.services.nlp_service import nlp_service

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Background Task Function ---
async def process_document_background(dokumen_id: int, db: Session):
    """
    Fungsi background untuk memproses dokumen secara lengkap.
    """
    try:
        logger.info(f"🚀 Starting processing for document {dokumen_id}")
        doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
        if not doc:
            logger.error("Document not found")
            return

        # 1. Update status -> Processing
        doc.status_analisis = 'processing'
        db.commit()

        # 2. Extract Text
        # Menggunakan nama fungsi yang benar: extract_text_from_file
        file_path = doc.path_file
        full_text = nlp_service.extract_text_from_file(file_path)
        
        if not full_text:
            raise Exception("Failed to extract text from file")

        # 3. Generate Summary
        logger.info("Generating summary...")
        # generate_summary adalah async, jadi pakai await
        summary = await nlp_service.generate_summary(full_text)
        doc.ringkasan = summary

        # 4. Extract Keywords & Save
        logger.info("Extracting keywords...")
        # extract_keywords adalah async, pakai await
        keywords = await nlp_service.extract_keywords(full_text)
        
        # Bersihkan keyword lama
        db.query(DokumenKata).filter(DokumenKata.dokumen_id == dokumen_id).delete()
        
        for kw_text in keywords:
            # Cek/Buat Master Keyword
            keyword_obj = db.query(KataKunci).filter(KataKunci.kata == kw_text).first()
            if not keyword_obj:
                keyword_obj = KataKunci(kata=kw_text)
                db.add(keyword_obj)
                db.commit()
                db.refresh(keyword_obj)
            
            # Link Dokumen -> Keyword
            doc_kw = DokumenKata(dokumen_id=doc.id, kata_kunci_id=keyword_obj.id)
            db.add(doc_kw)

        # 5. Extract References & Save (FITUR BARU)
        logger.info("Extracting references...")
        # Bersihkan referensi lama
        db.query(Referensi).filter(Referensi.dokumen_id == dokumen_id).delete()
        
        # Fungsi ini synchronous di nlp_service, jadi TIDAK pakai await
        references = nlp_service.extract_references_from_text(full_text)
        
        for ref in references:
            new_ref = Referensi(
                dokumen_id=doc.id,
                teks_referensi=ref['teks_referensi'],
                nomor=ref.get('nomor') 
            )
            db.add(new_ref)

        # 6. Finish
        doc.status_analisis = 'completed'
        db.commit()
        logger.info(f"✅ Document {dokumen_id} processing completed successfully")

    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        # Re-query doc to ensure session is active
        doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
        if doc:
            doc.status_analisis = 'failed'
            db.commit()


# ============= NLP Endpoints =============

@router.post("/process/{dokumen_id}")
async def process_document_endpoint(
    dokumen_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Jalankan di background agar tidak blocking
    background_tasks.add_task(process_document_background, dokumen_id, db)
    
    return {"message": "Document processing started", "status": "processing"}


@router.get("/status/{dokumen_id}")
def get_status(dokumen_id: int, db: Session = Depends(get_db)):
    doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Hitung progress sederhana untuk UI
    progress = 0
    if doc.status_analisis == 'pending': progress = 0
    elif doc.status_analisis == 'processing': progress = 50
    elif doc.status_analisis == 'completed': progress = 100
    elif doc.status_analisis == 'failed': progress = 0

    return {
        "status": doc.status_analisis,
        "progress": progress,
        "current_step": "Processing..." if doc.status_analisis == 'processing' else "Idle"
    }


# --- Endpoint Manual (Opsional) ---

@router.post("/extract-keywords", response_model=KeywordExtractionResponse)
async def extract_keywords(
    request: KeywordExtractionRequest,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Extract keywords manually (Sync)"""
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == request.dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # FIX: Gunakan extract_text_from_file
        text = nlp_service.extract_text_from_file(dokumen.path_file)
        if not text: raise Exception("Empty text")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    keywords = await nlp_service.extract_keywords(text, num_keywords=request.top_k)
    
    # Logic penyimpanan keyword manual bisa ditaruh sini jika perlu
    # ... (kode simpan keyword sama seperti di background task) ...
    
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
    """Generate summary manually (Sync)"""
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == request.dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # FIX: Gunakan extract_text_from_file
        text = nlp_service.extract_text_from_file(dokumen.path_file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # FIX: Gunakan generate_summary
    summary = await nlp_service.generate_summary(
        text,
        max_length=request.max_length
    )
    
    dokumen.ringkasan = summary
    db.commit()
    
    return {
        "dokumen_id": dokumen.id,
        "summary": summary,
        "status": "completed"
<<<<<<< Updated upstream
    }
=======
    }
    
@router.post("/compare-gap")
async def compare_documents_gap(
    payload: dict, # Ekspektasi: {"doc_id_1": 1, "doc_id_2": 2}
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    doc1_id = payload.get("doc_id_1")
    doc2_id = payload.get("doc_id_2")
    
    # Ambil dokumen dari DB
    doc1 = db.query(Dokumen).filter(Dokumen.id == doc1_id).first()
    doc2 = db.query(Dokumen).filter(Dokumen.id == doc2_id).first()
    
    if not doc1 or not doc2:
        raise HTTPException(status_code=404, detail="One or both documents not found")

    # Ekstrak teks (Cache logic bisa ditambahkan di sini agar tidak baca PDF ulang)
    text1 = nlp_service.extract_text_from_file(doc1.path_file)
    text2 = nlp_service.extract_text_from_file(doc2.path_file)
    
    if not text1 or not text2:
         raise HTTPException(status_code=400, detail="Failed to extract text from documents")

    # Analisis Gap
    gap_analysis = await nlp_service.analyze_research_gap(text1, text2)
    
    # Analisis Keyword Overlap (Bonus)
    # Kita cari keyword unik di Doc 1 yang tidak ada di Doc 2, dan sebaliknya
    kw1 = await nlp_service.extract_keywords(text1)
    kw2 = await nlp_service.extract_keywords(text2)
    
    unique_to_doc1 = list(set(kw1) - set(kw2))
    unique_to_doc2 = list(set(kw2) - set(kw1))
    common_keywords = list(set(kw1) & set(kw2))

    return {
        "gap_analysis": gap_analysis,
        "keyword_comparison": {
            "unique_to_doc1": unique_to_doc1,
            "unique_to_doc2": unique_to_doc2,
            "common_topics": common_keywords
        }
    }
class OutlineRequest(BaseModel):
    title: str
@router.post("/generate-outline")
async def generate_outline_endpoint(request: OutlineRequest):
    """
    Generate Thesis Outline structure based on Title.
    """
    try:
        # Panggil logika dari custom_nlp.py
        outline = generate_thesis_outline(request.title)
        
        return {
            "status": "success", 
            "data": outline
        }
    except Exception as e:
        print(f"❌ Error generating outline: {str(e)}") # Cek log ini di terminal
        raise HTTPException(status_code=500, detail=str(e))
>>>>>>> Stashed changes
