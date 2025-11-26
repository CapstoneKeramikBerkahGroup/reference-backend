from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
import shutil
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

from app.core.database import get_db
from app.core.config import settings
from app.models import Dokumen, Tag, Mahasiswa, KataKunci, Referensi, DocumentSimilarity
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


@router.get("/doc/{dokumen_id}", response_model=DokumenDetailResponse)
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


@router.get("/doc/{dokumen_id}/download")
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


@router.delete("/doc/{dokumen_id}")
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
@router.post("/doc/{dokumen_id}/tags", response_model=DokumenResponse)
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


@router.delete("/doc/{dokumen_id}/tags/{tag_id}")
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


# ============= Compilation Report Endpoint =============
@router.get("/compilation/download")
async def download_compilation_report(
    tag_filter: Optional[str] = Query(None, description="Filter by tag name"),
    keyword_filter: Optional[str] = Query(None, description="Filter by keyword"),
    status_filter: Optional[str] = Query(None, description="Filter by status (completed/processing/failed)"),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """
    Generate and download compilation report from all documents
    
    This endpoint creates a comprehensive PDF report that synthesizes:
    - Overview statistics of all documents
    - Top keywords across entire collection
    - Individual document summaries
    - Reference analysis
    - Document similarity network
    """
    
    try:
        # Query documents with filters
        query = db.query(Dokumen).filter(
            Dokumen.mahasiswa_id == current_mahasiswa.id
        )
        
        # Apply optional filters
        if tag_filter:
            query = query.join(Dokumen.tags).filter(Tag.nama == tag_filter.lower())
        
        if keyword_filter:
            query = query.join(Dokumen.kata_kunci).filter(
                KataKunci.kata.ilike(f"%{keyword_filter}%")
            )
        
        if status_filter:
            query = query.filter(Dokumen.status_analisis == status_filter)
        
        documents = query.order_by(Dokumen.tanggal_unggah.desc()).all()
        
        if not documents:
            raise HTTPException(
                status_code=404, 
                detail="No documents found. Please upload documents first."
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error querying documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query documents: {str(e)}"
        )
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    heading3_style = ParagraphStyle(
        'CustomHeading3',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8
    )
    
    # =================== TITLE PAGE ===================
    story.append(Spacer(1, 1*inch))
    story.append(Paragraph("📚 Literature Compilation Report", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Student info
    student_info_style = ParagraphStyle(
        'StudentInfo',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    story.append(Paragraph(f"<b>Student:</b> {current_mahasiswa.user.nama}", student_info_style))
    story.append(Paragraph(f"<b>NIM:</b> {current_mahasiswa.nim}", student_info_style))
    if current_mahasiswa.program_studi:
        story.append(Paragraph(f"<b>Program:</b> {current_mahasiswa.program_studi}", student_info_style))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%d %B %Y, %H:%M')}", student_info_style))
    
    story.append(Spacer(1, 0.5*inch))
    
    # Applied filters
    if tag_filter or keyword_filter or status_filter:
        filter_style = ParagraphStyle(
            'FilterInfo',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=4
        )
        story.append(Paragraph("<b>Applied Filters:</b>", filter_style))
        if tag_filter:
            story.append(Paragraph(f"Tag: {tag_filter}", filter_style))
        if keyword_filter:
            story.append(Paragraph(f"Keyword: {keyword_filter}", filter_style))
        if status_filter:
            story.append(Paragraph(f"Status: {status_filter}", filter_style))
    
    story.append(PageBreak())
    
    # =================== OVERVIEW STATISTICS ===================
    story.append(Paragraph("📊 Overview Statistics", heading2_style))
    story.append(Spacer(1, 0.1*inch))
    
    # Calculate statistics
    total_docs = len(documents)
    completed_docs = len([d for d in documents if d.status_analisis == 'completed'])
    total_size_kb = sum(d.ukuran_kb or 0 for d in documents)
    total_size_mb = total_size_kb / 1024
    
    # Count unique keywords
    all_keywords = set()
    for dokumen in documents:
        for kk in dokumen.kata_kunci:
            all_keywords.add(kk.kata)
    
    # Count total references
    total_refs = sum(len(dokumen.referensi) for dokumen in documents)
    
    # Date range
    if documents:
        oldest_date = min(d.tanggal_unggah for d in documents)
        newest_date = max(d.tanggal_unggah for d in documents)
        date_range = f"{oldest_date.strftime('%Y-%m-%d')} to {newest_date.strftime('%Y-%m-%d')}"
    else:
        date_range = "N/A"
    
    stats_data = [
        ["Total Documents:", str(total_docs)],
        ["Completed Analysis:", f"{completed_docs} / {total_docs} ({completed_docs*100//total_docs if total_docs > 0 else 0}%)"],
        ["Total Storage:", f"{total_size_mb:.2f} MB"],
        ["Unique Keywords:", str(len(all_keywords))],
        ["Total References:", str(total_refs)],
        ["Date Range:", date_range]
    ]
    
    stats_table = Table(stats_data, colWidths=[2.5*inch, 3.5*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 0.3*inch))
    
    # =================== TOP KEYWORDS ===================
    story.append(Paragraph("🔑 Top Keywords Across Collection", heading2_style))
    story.append(Spacer(1, 0.1*inch))
    
    # Aggregate keywords with frequency
    keyword_freq = {}
    try:
        for dokumen in documents:
            if hasattr(dokumen, 'kata_kunci') and dokumen.kata_kunci:
                for kk in dokumen.kata_kunci:
                    if kk.kata in keyword_freq:
                        keyword_freq[kk.kata] += (kk.frekuensi or 1)
                    else:
                        keyword_freq[kk.kata] = (kk.frekuensi or 1)
    except Exception as e:
        print(f"Warning: Error processing keywords: {e}")
    
    # Sort by frequency
    top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:20]
    
    if top_keywords:
        keywords_data = [["Rank", "Keyword", "Total Frequency"]]
        for idx, (keyword, freq) in enumerate(top_keywords, 1):
            keywords_data.append([str(idx), keyword, str(freq)])
        
        keywords_table = Table(keywords_data, colWidths=[0.7*inch, 3.8*inch, 1.5*inch])
        keywords_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
        ]))
        story.append(keywords_table)
    else:
        story.append(Paragraph("No keywords extracted yet.", body_style))
    
    story.append(PageBreak())
    
    # =================== DOCUMENT SUMMARIES ===================
    story.append(Paragraph("📄 Document Summaries", heading2_style))
    story.append(Spacer(1, 0.2*inch))
    
    for idx, dokumen in enumerate(documents, 1):
        try:
            # Document title
            doc_title = dokumen.judul if dokumen.judul else dokumen.nama_file
            # Escape special characters for PDF
            doc_title_safe = doc_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"{idx}. {doc_title_safe}", heading3_style))
            
            # Document metadata
            metadata = f"<b>File:</b> {dokumen.nama_file} | <b>Format:</b> {dokumen.format.upper() if dokumen.format else 'N/A'} | <b>Size:</b> {dokumen.ukuran_kb or 0} KB | <b>Uploaded:</b> {dokumen.tanggal_unggah.strftime('%Y-%m-%d') if dokumen.tanggal_unggah else 'N/A'}"
            story.append(Paragraph(metadata, ParagraphStyle('Metadata', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6b7280'))))
            story.append(Spacer(1, 0.05*inch))
            
            # Status badge
            status_color = {
                'completed': colors.HexColor('#10b981'),
                'processing': colors.HexColor('#f59e0b'),
                'failed': colors.HexColor('#ef4444')
            }.get(dokumen.status_analisis, colors.grey)
            
            status_text = dokumen.status_analisis.upper() if dokumen.status_analisis else 'UNKNOWN'
            status_para = Paragraph(
                f"<font color='{status_color.hexval()}'>● {status_text}</font>",
                ParagraphStyle('Status', parent=styles['Normal'], fontSize=9)
            )
            story.append(status_para)
            story.append(Spacer(1, 0.1*inch))
            
            # Summary
            if dokumen.ringkasan:
                story.append(Paragraph("<b>Summary:</b>", body_style))
                # Escape and truncate summary
                summary_safe = dokumen.ringkasan.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                summary_text = summary_safe[:500] + "..." if len(summary_safe) > 500 else summary_safe
                story.append(Paragraph(summary_text, body_style))
            else:
                story.append(Paragraph("<i>No summary available.</i>", body_style))
            
            story.append(Spacer(1, 0.1*inch))
            
            # Keywords for this document
            if hasattr(dokumen, 'kata_kunci') and dokumen.kata_kunci:
                keywords_list = ", ".join([f"<b>{kk.kata}</b>" for kk in dokumen.kata_kunci[:10]])
                story.append(Paragraph(f"<b>Keywords:</b> {keywords_list}", body_style))
                story.append(Spacer(1, 0.05*inch))
            
            # Reference count
            if hasattr(dokumen, 'referensi') and dokumen.referensi:
                story.append(Paragraph(f"<b>References:</b> {len(dokumen.referensi)} citations found", body_style))
            
            # Tags
            if hasattr(dokumen, 'tags') and dokumen.tags:
                tags_list = ", ".join([f"#{tag.nama}" for tag in dokumen.tags])
                story.append(Paragraph(f"<b>Tags:</b> {tags_list}", body_style))
            
            story.append(Spacer(1, 0.2*inch))
            
            # Page break every 3 documents to avoid crowding
            if idx % 3 == 0 and idx < len(documents):
                story.append(PageBreak())
        except Exception as e:
            print(f"Warning: Error processing document {idx}: {e}")
            # Continue with next document
            continue
    
    # =================== DOCUMENT RELATIONSHIPS ===================
    story.append(PageBreak())
    story.append(Paragraph("🔗 Document Similarity Network", heading2_style))
    story.append(Spacer(1, 0.1*inch))
    
    # Get all similarity relationships for these documents
    doc_ids = [d.id for d in documents]
    similarities = db.query(DocumentSimilarity).filter(
        DocumentSimilarity.dokumen_1_id.in_(doc_ids),
        DocumentSimilarity.dokumen_2_id.in_(doc_ids),
        DocumentSimilarity.similarity_score >= 0.5
    ).order_by(DocumentSimilarity.similarity_score.desc()).limit(50).all()
    
    if similarities:
        story.append(Paragraph(
            "The following documents show significant similarity (≥50%), suggesting related topics or overlapping content:",
            body_style
        ))
        story.append(Spacer(1, 0.1*inch))
        
        sim_data = [["Document 1", "Document 2", "Similarity"]]
        for sim in similarities[:20]:  # Top 20 similarities
            doc1 = next((d for d in documents if d.id == sim.dokumen_1_id), None)
            doc2 = next((d for d in documents if d.id == sim.dokumen_2_id), None)
            
            if doc1 and doc2:
                doc1_title = (doc1.judul or doc1.nama_file)[:30] + "..." if len(doc1.judul or doc1.nama_file) > 30 else (doc1.judul or doc1.nama_file)
                doc2_title = (doc2.judul or doc2.nama_file)[:30] + "..." if len(doc2.judul or doc2.nama_file) > 30 else (doc2.judul or doc2.nama_file)
                
                sim_data.append([
                    doc1_title,
                    doc2_title,
                    f"{sim.similarity_score:.1%}"
                ])
        
        if len(sim_data) > 1:
            sim_table = Table(sim_data, colWidths=[2.3*inch, 2.3*inch, 1.4*inch])
            sim_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
            ]))
            story.append(sim_table)
    else:
        story.append(Paragraph(
            "No significant similarity relationships found between documents. This may indicate diverse topics or insufficient analysis.",
            body_style
        ))
    
    # =================== FOOTER ===================
    story.append(PageBreak())
    story.append(Spacer(1, 2*inch))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER,
        spaceAfter=4
    )
    
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━━━━", footer_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "This report was automatically generated by the <b>AI Academic Reference Management System</b>",
        footer_style
    ))
    story.append(Paragraph(
        f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}",
        footer_style
    ))
    story.append(Paragraph(
        "Powered by Natural Language Processing and Machine Learning",
        footer_style
    ))
    
    # Build PDF
    try:
        doc.build(story)
        buffer.seek(0)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"PDF Generation Error: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )
    
    # Generate filename
    filter_suffix = ""
    if tag_filter:
        filter_suffix += f"_tag-{tag_filter}"
    if keyword_filter:
        filter_suffix += f"_keyword-{keyword_filter}"
    
    filename = f"compilation_report_{current_mahasiswa.nim}_{datetime.now().strftime('%Y%m%d_%H%M')}{filter_suffix}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
