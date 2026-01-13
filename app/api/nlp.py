from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
import logging
from pydantic import BaseModel

# Import Database & Models
from app.core.database import get_db
from app.models.models import Dokumen, IdeaHistory, KataKunci, Referensi, Mahasiswa, DokumenKata, User, ExternalReference
from app.api.auth import get_current_user
from app.api.auth import get_current_mahasiswa


# Import Schemas
from app.schemas import (
    KeywordExtractionRequest, KeywordExtractionResponse,
    SummarizationRequest, SummarizationResponse
)

# Import Servicen
from app.services.nlp_service import nlp_service
from app.services.custom_nlp import extract_references

router = APIRouter()
logger = logging.getLogger(__name__)


# ===== SCHEMAS TAMBAHAN =====
class OutlineRequest(BaseModel):
    title: str
    language: str = "id"
    outline_type: str = "thesis"  # "thesis" or "paper"
    dokumen_id: int = None  # Optional: for paper outline to use document content

class OutlineResponse(BaseModel):
    status: str
    data: dict

class GapMatrixRequest(BaseModel):
    doc_ids: List[int]
    language: str = "id"

class IdeaGenerationRequest(BaseModel):
    doc_ids: List[int]
    language: str = "id"
    
class SaveIdeaRequest(BaseModel):
    title: str
    content: Dict[str, Any]

# ===== BACKGROUND TASK =====
async def process_document_background(dokumen_id: int, db: Session, language: str = "id"):
    """
    Fungsi background untuk memproses dokumen dengan bahasa spesifik.
    """
    try:
        logger.info(f"🚀 Starting processing for document {dokumen_id} in {language}")
        doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
        if not doc:
            return

        doc.status_analisis = 'processing'
        db.commit()

        file_path = doc.file_path
        logger.info(f"📁 Attempting to extract text from: {file_path}")
        full_text = nlp_service.extract_text_from_file(file_path)
        
        if not full_text:
            logger.error(f"❌ No text extracted from {file_path}")
            raise Exception(f"Failed to extract text from file: {file_path}")

        # --- UPDATE DISINI: Gunakan parameter language ---
        logger.info(f"Generating smart summary ({language})...")
        summary = await nlp_service.generate_summary(full_text, lang=language)
        doc.ringkasan = summary

        logger.info("Extracting keywords...")
        keywords = await nlp_service.extract_keywords(full_text, num_keywords=10)
        
        # Bersihkan keyword lama & simpan baru (Logika sama seperti sebelumnya)
        db.query(DokumenKata).filter(DokumenKata.dokumen_id == dokumen_id).delete()
        for kw_text in keywords:
            keyword_obj = db.query(KataKunci).filter(KataKunci.kata == kw_text).first()
            if not keyword_obj:
                keyword_obj = KataKunci(kata=kw_text)
                db.add(keyword_obj)
                db.commit()
                db.refresh(keyword_obj)
            
            doc_kw = DokumenKata(dokumen_id=doc.id, kata_kunci_id=keyword_obj.id)
            db.add(doc_kw)

        # Extract References (Logika sama)
        db.query(Referensi).filter(Referensi.dokumen_id == dokumen_id).delete()
        references = extract_references(full_text)
        for ref in references:
            new_ref = Referensi(
                dokumen_id=doc.id,
                teks_referensi=ref.get('teks_referensi', ''),
                nomor=ref.get('nomor'),
                status_validasi='pending'
            )
            db.add(new_ref)

        doc.status_analisis = 'completed'
        db.commit()
        logger.info(f"✅ Document processing completed")

    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
        if doc:
            doc.status_analisis = 'failed'
            db.commit()


# ===== ENDPOINTS =====
@router.post("/ideas/save")
async def save_generated_idea(
    req: SaveIdeaRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        raise HTTPException(status_code=404, detail="Mahasiswa not found")

    new_idea = IdeaHistory(
        mahasiswa_id=mahasiswa.id,
        title=req.title,
        content_json=req.content
    )
    db.add(new_idea)
    db.commit()
    return {"message": "Ide berhasil disimpan!"}

@router.get("/ideas/history")
async def get_idea_history(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == current_user.id).first()
    if not mahasiswa:
        return []
        
    history = db.query(IdeaHistory).filter(
        IdeaHistory.mahasiswa_id == mahasiswa.id
    ).order_by(IdeaHistory.created_at.desc()).all()
    
    return history


@router.post("/generate-ideas")
async def generate_ideas_endpoint(
    request: IdeaGenerationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Generate ide skripsi baru dari kombinasi paper yang dipilih.
    """
    logger.info(f"💡 Generating Ideas for docs: {request.doc_ids}")
    
    # 1. Ambil dokumen
    docs = db.query(Dokumen).filter(Dokumen.id.in_(request.doc_ids)).all()
    logger.info(f"📄 Found {len(docs)} documents in database")
    
    if len(docs) < 2:
        raise HTTPException(status_code=400, detail="Pilih minimal 2 dokumen untuk sintesis ide.")

    # 2. Extract Text
    docs_data = []
    for doc in docs:
        try:
            logger.info(f"📖 Extracting text from: {doc.file_path}")
            text = nlp_service.extract_text_from_file(doc.file_path)
            if text:
                docs_data.append({
                    "title": doc.judul,
                    "text": text[:4000] # Ambil agak banyak biar idenya kaya
                })
                logger.info(f"✅ Successfully extracted {len(text)} chars from {doc.judul}")
            else:
                logger.warning(f"⚠️ No text extracted from {doc.judul}")
        except Exception as e:
            logger.error(f"❌ Error extracting from {doc.judul}: {e}")
            continue
    
    logger.info(f"📊 Total documents with text: {len(docs_data)}")
    
    if not docs_data:
        raise HTTPException(status_code=400, detail="Gagal membaca teks dokumen. Pastikan dokumen adalah PDF yang valid.")

    # 3. Call Gemini
    try:
        result = await nlp_service.generate_research_ideas(docs_data, request.language)
        return result
    except Exception as e:
        logger.error(f"Generate Idea Error: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal menghasilkan ide: {str(e)}")

@router.post("/process/{dokumen_id}")
async def process_document_endpoint(
    dokumen_id: int, 
    background_tasks: BackgroundTasks,
    language: str = "id", # Tambahkan parameter ini
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Trigger background processing dengan opsi bahasa"""
    doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Kirim language ke background task
    background_tasks.add_task(process_document_background, dokumen_id, db, language)
    
    return {"message": f"Document processing started in {language}", "status": "processing"}


@router.get("/status/{dokumen_id}")
def get_status(dokumen_id: int, db: Session = Depends(get_db)):
    """Get processing status"""
    doc = db.query(Dokumen).filter(Dokumen.id == dokumen_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    progress = 0
    if doc.status_analisis == 'pending': 
        progress = 0
    elif doc.status_analisis == 'processing': 
        progress = 50
    elif doc.status_analisis == 'completed': 
        progress = 100
    elif doc.status_analisis == 'failed': 
        progress = 0

    return {
        "status": doc.status_analisis,
        "progress": progress,
        "current_step": "Processing..." if doc.status_analisis == 'processing' else "Idle"
    }


@router.post("/generate-outline", response_model=OutlineResponse)
async def generate_outline_endpoint(
    request: OutlineRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"📝 Generating {request.outline_type} outline: {request.title} ({request.language})")
        
        # Call appropriate function based on outline_type
        if request.outline_type == "paper":
            # Extract document content if dokumen_id provided
            doc_content = None
            if request.dokumen_id:
                doc = db.query(Dokumen).filter(Dokumen.id == request.dokumen_id).first()
                if doc and doc.file_path:
                    try:
                        doc_content = nlp_service.extract_text_from_file(doc.file_path)
                        logger.info(f"📄 Extracted {len(doc_content)} chars from document for context")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not extract document content: {e}")
            
            outline = await nlp_service.generate_paper_outline(
                request.title, 
                lang=request.language,
                doc_content=doc_content
            )
        else:  # default to thesis
            outline = await nlp_service.generate_thesis_outline(request.title, lang=request.language)
        
        return {
            "status": "success",
            "data": outline
        }
    except Exception as e:
        logger.error(f"❌ Error generating outline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-keywords", response_model=KeywordExtractionResponse)
async def extract_keywords(
    request: KeywordExtractionRequest,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Extract keywords manually"""
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == request.dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        text = nlp_service.extract_text_from_file(dokumen.file_path)
        if not text: 
            raise Exception("Empty text")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    keywords = await nlp_service.extract_keywords(text, num_keywords=request.top_k)
    
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
    """Generate summary manually"""
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == request.dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        text = nlp_service.extract_text_from_file(dokumen.file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    summary = await nlp_service.generate_summary(text, lang='id')
    
    dokumen.ringkasan = summary
    db.commit()
    
    return {
        "dokumen_id": dokumen.id,
        "summary": summary,
        "status": "completed"
    }

@router.post("/analyze-gap-matrix")
async def analyze_gap_matrix_endpoint(
    request: GapMatrixRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    logger.info(f"📊 Analyzing Gap Matrix for docs: {request.doc_ids}")
    
    docs = db.query(Dokumen).filter(Dokumen.id.in_(request.doc_ids)).all()
    
    if len(docs) < 2:
        raise HTTPException(status_code=400, detail="Pilih minimal 2 dokumen.")

    docs_data = []
    for doc in docs:
        try:
            # 1. Ambil Metadata (Author & Year) dari ExternalReference jika ada
            # Ini kuncinya agar kolom Penulis (Tahun) benar!
            ext_ref = db.query(ExternalReference).filter(
                ExternalReference.local_document_id == doc.id
            ).first()

            author_raw = ext_ref.authors if ext_ref else "Unknown Author"
            year_raw = ext_ref.year if ext_ref else "n.d."

            # 2. Ambil Teks
            text = nlp_service.extract_text_from_file(doc.file_path)
            if not text:
                logger.error(f"❌ TEKS KOSONG untuk file: {doc.nama_file}")
            else:
                logger.info(f"✅ Berhasil baca {doc.nama_file}: {len(text)} karakter")
            
            docs_data.append({
                "id": doc.id,
                "title": doc.judul,
                "author": author_raw, # Kirim ke service
                "year": year_raw,     # Kirim ke service
                "text": text[:5000]   # Limit karakter
            })
        except Exception as e:
            logger.warning(f"Skipping doc {doc.id}: {e}")
            continue

    if not docs_data:
        raise HTTPException(status_code=400, detail="Gagal mengekstrak teks.")

    try:
        # Panggil service
        result = await nlp_service.generate_gap_matrix(docs_data, request.language)
        return result
    except Exception as e:
        logger.error(f"Gap Analysis Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compare-gap")
async def compare_documents_gap(
    payload: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Compare research gap antara 2 dokumen"""
    doc1_id = payload.get("doc_id_1")
    doc2_id = payload.get("doc_id_2")
    
    doc1 = db.query(Dokumen).filter(Dokumen.id == doc1_id).first()
    doc2 = db.query(Dokumen).filter(Dokumen.id == doc2_id).first()
    
    if not doc1 or not doc2:
        raise HTTPException(status_code=404, detail="One or both documents not found")

    text1 = nlp_service.extract_text_from_file(doc1.file_path)
    text2 = nlp_service.extract_text_from_file(doc2.file_path)
    
    if not text1 or not text2:
        raise HTTPException(status_code=400, detail="Failed to extract text from documents")

    # Analisis Gap
    gap_analysis = await nlp_service.analyze_research_gap(text1, text2)
    
    # Keyword Overlap
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
        # Use nlp_service method
        outline = await nlp_service.generate_thesis_outline(request.title, lang=request.language)
        
        return {
            "status": "success", 
            "data": outline
        }
    except Exception as e:
        logger.error(f"❌ Error generating outline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
