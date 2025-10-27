"""
Custom NLP Service - Converted from Jupyter Notebook
Provides keyword extraction, summarization, and document similarity analysis
"""

import pdfplumber
import docx
import os
import numpy as np
from keybert import KeyBERT
from transformers import pipeline
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# --- Global Settings & Configuration ---
MAX_CHARS_FOR_MODEL = 3000  # Prevent GPU/memory errors
SIMILARITY_THRESHOLD = 0.50  # Threshold for visualization

# Check GPU availability
DEVICE = 0 if torch.cuda.is_available() else -1  # 0 for first GPU, -1 for CPU
DEVICE_NAME = torch.cuda.get_device_name(0) if DEVICE == 0 else "CPU"
logger.info(f"💡 Using Device: {DEVICE_NAME}")


# --- Text Extraction Functions ---
def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """Extract raw text from PDF file with basic cleaning."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=1, y_tolerance=3)
                if page_text:
                    text += page_text + "\n"
        
        # Cleaning: remove excess newlines & trim lines
        cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(cleaned_lines)
    except Exception as e:
        logger.error(f"⚠️ Failed to process PDF {os.path.basename(file_path)}: {e}")
        return None


def extract_text_from_docx(file_path: str) -> Optional[str]:
    """Extract raw text from DOCX file with basic cleaning."""
    try:
        doc = docx.Document(file_path)
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error(f"⚠️ Failed to process DOCX {os.path.basename(file_path)}: {e}")
        return None


# --- NLP Model Functions ---
def extract_keywords_bert(
    text: str, 
    kw_model_instance: KeyBERT, 
    top_n: int = 10, 
    ngram_range: Tuple[int, int] = (1, 3)
) -> List[str]:
    """
    Extract keywords using KeyBERT with text truncation and error handling.
    
    Args:
        text: Input text to extract keywords from
        kw_model_instance: Initialized KeyBERT model
        top_n: Number of top keywords to return
        ngram_range: N-gram range for keyphrase extraction
        
    Returns:
        List of extracted keywords
    """
    if not text or not isinstance(text, str) or len(text.strip()) < 50:
        return []
    
    try:
        truncated_text = text[:MAX_CHARS_FOR_MODEL]
        keywords = kw_model_instance.extract_keywords(
            truncated_text,
            keyphrase_ngram_range=ngram_range,
            stop_words='english',
            use_maxsum=True,
            nr_candidates=20,
            top_n=top_n
        )
        
        # Filter out short keywords and digits
        filtered_keywords = [
            (kw, score) for kw, score in keywords 
            if len(kw) > 2 and not kw.isdigit()
        ]
        return [kw for kw, score in filtered_keywords]
    
    except RuntimeError as e:
        if "CUDA" in str(e):
            logger.error("❌ CUDA Runtime Error during KeyBERT extraction")
        else:
            logger.error(f"❌ Runtime Error during KeyBERT extraction: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Error during KeyBERT extraction: {e}")
        return []


def generate_summary_bart(text: str, summarizer_instance) -> str:
    """
    Generate summary using BART model with text truncation and error handling.
    
    Args:
        text: Input text to summarize
        summarizer_instance: Initialized BART summarization pipeline
        
    Returns:
        Summary text or error message
    """
    if not text or not isinstance(text, str) or len(text.strip()) < 100:
        return "Text too short to summarize."
    
    try:
        truncated_text = text[:MAX_CHARS_FOR_MODEL]
        summary = summarizer_instance(
            truncated_text, 
            max_length=150, 
            min_length=30, 
            do_sample=False
        )
        return summary[0]['summary_text']
    
    except RuntimeError as e:
        if "CUDA" in str(e):
            logger.error("❌ CUDA Runtime Error during BART summarization")
        else:
            logger.error(f"❌ Runtime Error during BART summarization: {e}")
        return "Failed to generate summary (Runtime Error)."
    except Exception as e:
        logger.error(f"❌ Error during BART summarization: {e}")
        return "Failed to generate summary."


def extract_references(text: str) -> List[Dict[str, str]]:
    """
    Extract references/citations from academic paper text.
    Supports multiple citation formats with improved filtering.
    
    Args:
        text: Full text of the document
        
    Returns:
        List of dictionaries with reference number and text
    """
    import re
    
    if not text or len(text.strip()) < 100:
        return []
    
    references = []
    
    # Strategy 1: Find "References" or "Bibliography" section
    ref_section_patterns = [
        r'\n\s*REFERENCES\s*\n(.*?)(?:\n\s*APPENDIX|\n\s*ACKNOWLEDGMENT|$)',
        r'\n\s*References\s*\n(.*?)(?:\n\s*Appendix|\n\s*Acknowledgment|$)',
        r'\n\s*BIBLIOGRAPHY\s*\n(.*?)(?:\n\s*APPENDIX|\n\s*ACKNOWLEDGMENT|$)',
        r'\n\s*Bibliography\s*\n(.*?)(?:\n\s*Appendix|\n\s*Acknowledgment|$)',
    ]
    
    ref_section = None
    for pattern in ref_section_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            ref_section = match.group(1)
            logger.info(f"📖 Found reference section ({len(ref_section)} chars)")
            break
    
    # If no reference section found, try last 30% of document
    if not ref_section:
        logger.warning("⚠️ No reference section header found, searching last 30% of document")
        # Take last 30% of document where references typically are
        start_pos = int(len(text) * 0.7)
        ref_section = text[start_pos:]
    
    if len(ref_section.strip()) < 100:
        logger.warning("⚠️ Reference section too short, no valid references found")
        return []
    
    # Helper function to validate reference text
    def is_valid_reference(text: str) -> bool:
        """Check if text looks like a valid academic reference"""
        if len(text) < 20:  # Lowered from 30 to be more flexible
            return False
        
        # Exclude obvious false positives first
        false_positives = [
            r'^SELF EVALUATION',
            r'^ACKNOWLEDGMENT',
            r'^APPENDIX',
            r'^CHAPTER \d+',
            r'^SECTION \d+',
            r'^TABLE OF CONTENTS',
            r'^LIST OF',
            r'^FIGURE \d+',
            r'^TABLE \d+',
        ]
        
        if any(re.match(pattern, text, re.IGNORECASE) for pattern in false_positives):
            return False
        
        # More relaxed: accept if has year OR author-like pattern OR URL
        indicators = [
            r'\b(19|20)\d{2}\b',  # Year (1900-2099)
            r'et\s+al\.',  # et al.
            r'\b(vol|volume|pp?|page|doi|isbn)\b',  # Academic indicators
            r'http[s]?://',  # URL
            r'[A-Z][a-z]+,\s+[A-Z]\.?',  # Author format: Smith, J.
            r'[A-Z][a-z]+\s+and\s+[A-Z][a-z]+',  # Authors: Smith and Jones
            r'Journal|Conference|Proceedings|IEEE|ACM',  # Publication venues
        ]
        
        has_indicator = any(re.search(pattern, text, re.IGNORECASE) for pattern in indicators)
        
        # Also accept if it has typical reference structure (author, title, year)
        has_structure = bool(re.search(r'[A-Z][a-z]+.*\d{4}', text))
        
        return has_indicator or has_structure
    
    # Strategy 2: Extract numbered references with brackets [1], [2]
    pattern_bracket = r'\[(\d+)\]\s*([^\[]+?)(?=\[\d+\]|\n\n|$)'
    matches_bracket = re.findall(pattern_bracket, ref_section, re.DOTALL)
    
    if matches_bracket:
        for num, ref_text in matches_bracket:
            cleaned_text = ' '.join(ref_text.strip().split())
            if is_valid_reference(cleaned_text):
                references.append({
                    "nomor": num,
                    "teks_referensi": cleaned_text[:1000]  # Increased from 500 to 1000
                })
    
    # Strategy 3: Extract numbered references with dots (1., 2.)
    if not references:
        # Pattern to match references like: 1. Author, A. (Year). Title...
        # Look ahead to next number or end of section
        pattern_numbered = r'(\d+)\.\s+([A-Z][^\n]+?)(?=\n\d+\.\s+[A-Z]|\n\s*$|$)'
        matches_numbered = re.findall(pattern_numbered, ref_section, re.DOTALL)
        
        for num, ref_text in matches_numbered:
            cleaned_text = ' '.join(ref_text.strip().split())
            if is_valid_reference(cleaned_text):
                references.append({
                    "nomor": num,
                    "teks_referensi": cleaned_text[:1000]  # Increased from 500 to 1000
                })
    
    # Strategy 4: Author-Year format (Harvard style)
    if not references:
        # Pattern: Author, A. (YYYY). Title. Journal/Publisher...
        pattern_harvard = r'([A-Z][a-z]+(?:,\s+[A-Z]\.)+)\s+\((\d{4})\)\.\s+([^.]+\.(?:[^.]+\.)?)'
        matches_harvard = re.findall(pattern_harvard, ref_section)
        
        for idx, (author, year, title_pub) in enumerate(matches_harvard, 1):
            ref_text = f"{author} ({year}). {title_pub}"
            cleaned_text = ' '.join(ref_text.strip().split())
            if is_valid_reference(cleaned_text):
                references.append({
                    "nomor": str(idx),
                    "teks_referensi": cleaned_text[:1000]  # Increased from 500 to 1000
                })
    
    # Remove duplicates (same text with different numbers)
    seen_texts = set()
    unique_references = []
    for ref in references:
        # Normalize for comparison (first 100 chars, lowercase)
        normalized = ref["teks_referensi"][:100].lower()
        if normalized not in seen_texts:
            seen_texts.add(normalized)
            unique_references.append(ref)
    
    logger.info(f"📚 Extracted {len(unique_references)} valid references from document")
    return unique_references[:50]  # Limit to 50 references max


def generate_embeddings(text: str, embedding_model_instance: SentenceTransformer) -> Optional[np.ndarray]:
    """
    Generate embeddings using SentenceTransformer with text truncation and error handling.
    
    Args:
        text: Input text to generate embeddings for
        embedding_model_instance: Initialized SentenceTransformer model
        
    Returns:
        Embedding vector as numpy array or None if failed
    """
    if not text or not isinstance(text, str) or len(text.strip()) < 50:
        return None
    
    try:
        # Longer truncation for embeddings (6000 chars)
        truncated_text = text[:MAX_CHARS_FOR_MODEL * 2]
        embedding = embedding_model_instance.encode(truncated_text, convert_to_numpy=True)
        return embedding
    
    except RuntimeError as e:
        if "CUDA" in str(e):
            logger.error("❌ CUDA Runtime Error during embedding generation")
        else:
            logger.error(f"❌ Runtime Error during embedding generation: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error during embedding generation: {e}")
        return None


def calculate_similarity_matrix(embeddings: List[np.ndarray]) -> np.ndarray:
    """
    Calculate cosine similarity matrix from embeddings.
    
    Args:
        embeddings: List of embedding vectors
        
    Returns:
        Similarity matrix as numpy array
    """
    if len(embeddings) < 2:
        raise ValueError("Need at least 2 embeddings to calculate similarity")
    
    embedding_matrix = np.array(embeddings)
    similarity_matrix = cosine_similarity(embedding_matrix)
    return similarity_matrix


def build_graph_data(
    filenames: List[str], 
    similarity_matrix: np.ndarray, 
    threshold: float = SIMILARITY_THRESHOLD
) -> Dict:
    """
    Build graph data structure for visualization from similarity matrix.
    
    Args:
        filenames: List of document filenames
        similarity_matrix: Cosine similarity matrix
        threshold: Minimum similarity threshold for edges
        
    Returns:
        Dictionary with nodes and edges for graph visualization
    """
    nodes = []
    edges = []
    
    for i in range(len(filenames)):
        fname_i = filenames[i]
        # Create node with truncated label
        nodes.append({
            "id": fname_i,
            "label": fname_i[:25] + "..." if len(fname_i) > 25 else fname_i
        })
        
        # Create edges for similar documents
        for j in range(i + 1, len(filenames)):
            fname_j = filenames[j]
            similarity_score = similarity_matrix[i][j]
            
            if similarity_score > threshold:
                edges.append({
                    "from": fname_i,
                    "to": fname_j,
                    "value": float(similarity_score),
                    "title": f"Similarity: {similarity_score:.3f}"
                })
    
    logger.info(f"📊 Graph data ready: {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": nodes, "edges": edges}


# --- Model Initialization Functions ---
def initialize_keybert_model() -> KeyBERT:
    """Initialize KeyBERT model with all-MiniLM-L6-v2."""
    logger.info("⏳ Loading KeyBERT model (all-MiniLM-L6-v2)...")
    model = KeyBERT(model='all-MiniLM-L6-v2')
    logger.info("✅ KeyBERT model loaded successfully")
    return model


def initialize_summarizer() -> pipeline:
    """Initialize BART summarization pipeline."""
    logger.info("⏳ Loading Summarization model (distilbart-cnn-12-6)...")
    summarizer = pipeline(
        "summarization", 
        model="sshleifer/distilbart-cnn-12-6", 
        device=DEVICE
    )
    logger.info("✅ Summarization model loaded successfully")
    return summarizer


def initialize_embedding_model() -> SentenceTransformer:
    """Initialize SentenceTransformer model."""
    logger.info("⏳ Loading Embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer(
        'all-MiniLM-L6-v2', 
        device='cuda' if DEVICE == 0 else 'cpu'
    )
    logger.info("✅ Embedding model loaded successfully")
    return model
