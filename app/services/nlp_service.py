"""
NLP Service untuk ekstraksi kata kunci, peringkasan, dan analisis kemiripan dokumen
Menggunakan KeyBERT, BART, dan SentenceTransformer
"""

from typing import List, Dict, Optional
import logging
import numpy as np
import hashlib
from .custom_nlp import (
    extract_keywords_bert,
    extract_keywords_indonesian,
    generate_smart_summary_gemini,
    generate_summary_bart,
    generate_embeddings,
    calculate_similarity_matrix,
    initialize_keybert_model,
    initialize_summarizer,
    initialize_embedding_model,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_references,
    detect_language,
    preprocess_indonesian_text,
    translate_summary_to_indonesian,
    generate_thesis_outline,
)

logger = logging.getLogger(__name__)


class NLPService:
    def __init__(self):
        """Initialize NLP Service with lazy loading"""
        logger.info("Initializing NLP Service (models will be loaded on first use)...")
        
        # Use lazy loading - models will be initialized when first needed
        self._keyword_extractor = None
        self._summarizer = None
        self._embedding_model = None
        
        # Cache for embeddings
        self.embeddings_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.info("✅ NLP Service initialized (lazy loading + caching enabled)")
    
    def _get_text_hash(self, text: str) -> str:
        """Generate hash for caching"""
        # Hash first 500 chars for cache key
        return hashlib.md5(text[:500].encode()).hexdigest()
    
    @property
    def keyword_extractor(self):
        """Lazy load KeyBERT model"""
        if self._keyword_extractor is None:
            logger.info("Loading KeyBERT model for the first time...")
            try:
                self._keyword_extractor = initialize_keybert_model()
            except Exception as e:
                logger.error(f"Failed to load KeyBERT: {e}")
                raise
        return self._keyword_extractor
    
    @property
    def summarizer(self):
        """Lazy load BART summarizer"""
        if self._summarizer is None:
            logger.info("Loading BART summarizer for the first time...")
            try:
                self._summarizer = initialize_summarizer()
            except Exception as e:
                logger.error(f"Failed to load BART: {e}")
                raise
        return self._summarizer
    
    @property
    def embedding_model(self):
        """Lazy load SentenceTransformer model"""
        if self._embedding_model is None:
            logger.info("Loading SentenceTransformer for the first time...")
            try:
                self._embedding_model = initialize_embedding_model()
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer: {e}")
                raise
        return self._embedding_model
    
    def extract_references_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        Wrapper untuk mengekstrak referensi dari teks
        """
        logger.info(f"Extracting references from text length: {len(text)}")
        try:
            refs = extract_references(text)
            logger.info(f"Found {len(refs)} references")
            return refs
        except Exception as e:
            logger.error(f"Error extracting references: {e}")
            return []
    
    def extract_text_from_file(self, file_path: str) -> Optional[str]:
        """
        Extract text from PDF or DOCX file
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text or None if failed
        """
        if file_path.lower().endswith('.pdf'):
            return extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            return extract_text_from_docx(file_path)
        else:
            logger.error(f"Unsupported file type: {file_path}")
            return None
    
    async def extract_keywords(self, text: str, num_keywords: int = 10) -> List[str]:
        """
        Extract keywords from text using KeyBERT (English) or lightweight method (Indonesian)
        
        Args:
            text: Document text
            num_keywords: Number of keywords to extract
            
        Returns:
            List of keywords
        """
        logger.info(f"Extracting {num_keywords} keywords from text of length {len(text)}")
        
        try:
            # Deteksi bahasa
            lang = detect_language(text)
            
            # Untuk bahasa Indonesia, gunakan lightweight extraction (no model needed)
            if lang == 'id':
                logger.info("🇮🇩 Detected Indonesian - using lightweight keyword extraction")
                keywords = extract_keywords_indonesian(text, top_n=num_keywords)
            else:
                # Untuk Inggris, gunakan KeyBERT jika available
                if self.keyword_extractor is None:
                    logger.warning("KeyBERT not available, falling back to Indonesian method")
                    keywords = extract_keywords_indonesian(text, top_n=num_keywords)
                else:
                    keywords = extract_keywords_bert(
                        text, 
                        self.keyword_extractor,
                        top_n=num_keywords
                    )
            
            logger.info(f"Extracted {len(keywords)} keywords: {keywords}")
            return keywords
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    async def generate_summary(self, text: str, max_length: int = 150) -> str:
        """
        Generate summary using Gemini (Priority) -> BART -> Extractive (Fallback).
        """
        logger.info(f"Generating summary from text of length {len(text)}")
        
        try:
            # --- 1. DETEKSI BAHASA ---
            lang = detect_language(text)

            # --- 2. COBA GEMINI (SMART SUMMARY) ---
            # Kita import di sini untuk memastikan fungsi terbaru terpanggil
            try:
                from .custom_nlp import generate_smart_summary_gemini
                
                # Panggil Gemini (akan otomatis handle format bullet points)
                gemini_summary = generate_smart_summary_gemini(text, lang=lang)
                
                if gemini_summary:
                    logger.info("✨ Using Gemini Smart Summary")
                    return gemini_summary
            except ImportError:
                logger.warning("⚠️ Function generate_smart_summary_gemini not found in custom_nlp")
            except Exception as e:
                logger.warning(f"⚠️ Gemini Summary failed: {e}")

            # --- 3. FALLBACK KE METODE LAMA (JIKA GEMINI GAGAL/KEY INVALID) ---
            logger.info("🔄 Falling back to standard summarization")
            
            if lang == 'id' or len(text) < 200:
                logger.info(f"🇮🇩 Generating Indonesian summary (Extractive)")
                from .custom_nlp import create_extractive_summary_indonesian
                summary = create_extractive_summary_indonesian(text, num_sentences=3)
            elif self.summarizer is None:
                logger.warning("BART not available, using extractive summary")
                from .custom_nlp import create_extractive_summary_indonesian
                summary = create_extractive_summary_indonesian(text, num_sentences=3)
            else:
                # BART untuk Inggris
                from .custom_nlp import generate_summary_bart, translate_summary_to_indonesian
                summary_en = generate_summary_bart(text, self.summarizer)
                summary_id = translate_summary_to_indonesian(summary_en)
                summary = f"[English]\n{summary_en}\n\n[Indonesia]\n{summary_id}"
            
            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Failed to generate summary"
        
    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using embeddings
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1)
        """
        logger.info("Calculating similarity between two texts")
        
        try:
            # Generate embeddings (lazy load model)
            emb1 = generate_embeddings(text1, self.embedding_model)
            emb2 = generate_embeddings(text2, self.embedding_model)
            
            if emb1 is None or emb2 is None:
                logger.error("Failed to generate embeddings")
                return 0.0
            
            # Calculate cosine similarity
            similarity_matrix = calculate_similarity_matrix([emb1, emb2])
            similarity = float(similarity_matrix[0][1])
            
            logger.info(f"Similarity score: {similarity:.3f}")
            return similarity
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for text with caching
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list or None if failed
        """
        # Check cache first
        text_hash = self._get_text_hash(text)
        if text_hash in self.embeddings_cache:
            self.cache_hits += 1
            logger.info(f"✅ Cache hit for embeddings ({self.cache_hits} hits, {self.cache_misses} misses)")
            return self.embeddings_cache[text_hash]
        
        self.cache_misses += 1
        
        try:
            embedding = generate_embeddings(text, self.embedding_model)  # Lazy load
            if embedding is not None:
                embedding_list = embedding.tolist()
                # Cache the result
                self.embeddings_cache[text_hash] = embedding_list
                logger.info(f"💾 Cached embeddings for {text_hash[:8]}... (cache size: {len(self.embeddings_cache)})")
                return embedding_list
            return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def compute_document_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple documents
        
        Args:
            texts: List of text documents
            
        Returns:
            List of embedding vectors (numpy arrays)
        """
        logger.info(f"Computing embeddings for {len(texts)} documents")
        
        embeddings = []
        for i, text in enumerate(texts):
            logger.info(f"Generating embedding {i+1}/{len(texts)}")
            embedding = generate_embeddings(text, self.embedding_model)
            if embedding is not None:
                embeddings.append(embedding)
            else:
                # Use zero vector as fallback
                logger.warning(f"Failed to generate embedding for document {i+1}, using zero vector")
                embeddings.append(np.zeros(384))  # Default dimension for all-MiniLM-L6-v2
        
        return embeddings
    
    def compute_similarity(self, embeddings: List[np.ndarray]) -> np.ndarray:
        """
        Compute pairwise similarity matrix from embeddings
        
        Args:
            embeddings: List of embedding vectors
            
        Returns:
            Similarity matrix (numpy array)
        """
        logger.info(f"Computing similarity matrix for {len(embeddings)} embeddings")
        
        try:
            similarity_matrix = calculate_similarity_matrix(embeddings)
            logger.info(f"✅ Generated {similarity_matrix.shape} similarity matrix")
            return similarity_matrix
        except Exception as e:
            logger.error(f"Error computing similarity matrix: {e}")
            # Return identity matrix as fallback
            n = len(embeddings)
            return np.eye(n)


# Singleton instance
nlp_service = NLPService()
