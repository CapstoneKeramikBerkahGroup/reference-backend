from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import numpy as np

from app.core.database import get_db
from app.models import Dokumen, DocumentSimilarity, Mahasiswa
from app.schemas import VisualizationResponse, DocumentNode, DocumentEdge
from app.api.auth import get_current_mahasiswa
from app.services.nlp_service import nlp_service

router = APIRouter()


@router.get("/graph", response_model=VisualizationResponse)
@router.get("/similarity-graph", response_model=VisualizationResponse)  # Add alias for frontend
async def get_document_graph(
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db),
    min_similarity: float = 0.3
):
    """Get document relationship graph based on similarity"""
    
    # Get all documents for current mahasiswa
    documents = db.query(Dokumen).filter(
        Dokumen.mahasiswa_id == current_mahasiswa.id,
        Dokumen.status_analisis == "completed"
    ).all()
    
    if len(documents) < 2:
        return {
            "nodes": [
                {
                    "id": doc.id,
                    "label": doc.judul or doc.nama_file,
                    "tags": [tag.nama for tag in doc.tags],
                    "keywords": [kw.kata for kw in doc.kata_kunci[:5]]
                }
                for doc in documents
            ],
            "edges": []
        }
    
    # Create nodes
    nodes = []
    for doc in documents:
        nodes.append({
            "id": doc.id,
            "label": doc.judul or doc.nama_file,
            "tags": [tag.nama for tag in doc.tags],
            "keywords": [kw.kata for kw in doc.kata_kunci[:5]]
        })
    
    # Calculate similarities if not already calculated
    doc_ids = [doc.id for doc in documents]
    
    # Check if similarities already exist
    existing_similarities = db.query(DocumentSimilarity).filter(
        DocumentSimilarity.dokumen_1_id.in_(doc_ids),
        DocumentSimilarity.dokumen_2_id.in_(doc_ids)
    ).all()
    
    # Create similarity lookup
    similarity_lookup = {}
    for sim in existing_similarities:
        key = tuple(sorted([sim.dokumen_1_id, sim.dokumen_2_id]))
        similarity_lookup[key] = sim.similarity_score
    
    # Calculate missing similarities
    if len(similarity_lookup) < (len(documents) * (len(documents) - 1)) / 2:
        # Extract text from all documents or use embeddings if available
        texts = []
        for doc in documents:
            # Use summary if available, else extract from file
            if doc.ringkasan:
                texts.append(doc.ringkasan)
            else:
                try:
                    text = nlp_service.extract_text_from_file(doc.path_file)
                    texts.append(text[:1000] if text else doc.judul or doc.nama_file)
                except Exception as e:
                    print(f"Error extracting text from {doc.nama_file}: {e}")
                    texts.append(doc.judul or doc.nama_file)
        
        # Compute embeddings
        embeddings = nlp_service.compute_document_embeddings(texts)
        
        # Compute similarity matrix
        similarity_matrix = nlp_service.compute_similarity(embeddings)
        
        # Save similarities
        for i in range(len(documents)):
            for j in range(i + 1, len(documents)):
                doc_1_id = documents[i].id
                doc_2_id = documents[j].id
                similarity_score = float(similarity_matrix[i][j])
                
                # Check if already exists
                key = tuple(sorted([doc_1_id, doc_2_id]))
                if key not in similarity_lookup:
                    sim_record = DocumentSimilarity(
                        dokumen_1_id=doc_1_id,
                        dokumen_2_id=doc_2_id,
                        similarity_score=similarity_score
                    )
                    db.add(sim_record)
                    similarity_lookup[key] = similarity_score
        
        db.commit()
    
    # Create edges based on similarity threshold
    edges = []
    for (doc_1_id, doc_2_id), score in similarity_lookup.items():
        if score >= min_similarity:
            edges.append({
                "source": doc_1_id,
                "target": doc_2_id,
                "similarity": round(score, 3),  # Changed from 'weight' to 'similarity'
                "weight": round(score, 3)  # Keep weight for backwards compatibility
            })
    
    return {
        "nodes": nodes,
        "edges": edges
    }


@router.get("/similarity/{dokumen_id}")
async def get_similar_documents(
    dokumen_id: int,
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db),
    limit: int = 5
):
    """Get most similar documents to a specific document"""
    
    # Get document
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get similarities
    similarities = db.query(DocumentSimilarity).filter(
        (DocumentSimilarity.dokumen_1_id == dokumen_id) |
        (DocumentSimilarity.dokumen_2_id == dokumen_id)
    ).order_by(DocumentSimilarity.similarity_score.desc()).limit(limit).all()
    
    # Format results
    results = []
    for sim in similarities:
        other_doc_id = sim.dokumen_2_id if sim.dokumen_1_id == dokumen_id else sim.dokumen_1_id
        other_doc = db.query(Dokumen).filter(Dokumen.id == other_doc_id).first()
        
        if other_doc:
            results.append({
                "dokumen_id": other_doc.id,
                "judul": other_doc.judul,
                "nama_file": other_doc.nama_file,
                "similarity_score": round(sim.similarity_score, 3),
                "tags": [tag.nama for tag in other_doc.tags],
                "keywords": [kw.kata for kw in other_doc.kata_kunci[:3]]
            })
    
    return results


@router.delete("/similarity/cache")
async def clear_similarity_cache(
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """Clear similarity cache for current user's documents"""
    
    # Get all document IDs
    doc_ids = [doc.id for doc in db.query(Dokumen).filter(
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).all()]
    
    # Delete similarities
    db.query(DocumentSimilarity).filter(
        (DocumentSimilarity.dokumen_1_id.in_(doc_ids)) |
        (DocumentSimilarity.dokumen_2_id.in_(doc_ids))
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return {"message": "Similarity cache cleared"}
