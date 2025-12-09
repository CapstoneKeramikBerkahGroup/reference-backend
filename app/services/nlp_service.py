"""
NLP Service untuk ekstraksi kata kunci, peringkasan, dan analisis kemiripan dokumen
Menggunakan KeyBERT, BART, dan SentenceTransformer
"""

from typing import List, Dict, Optional
import logging
import numpy as np
import hashlib
import re  
from .custom_nlp import (
    extract_keywords_bert,
    extract_keywords_indonesian,
    generate_summary_bart,
    generate_embeddings,
    calculate_similarity_matrix,
    initialize_keybert_model,
    initialize_summarizer,
    initialize_embedding_model,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_references,
    extract_research_gap_sections,
    fix_common_artifacts
    detect_language,
    preprocess_indonesian_text,
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
    
    async def analyze_research_gap(self, text1: str, text2: str) -> Dict:
        from .custom_nlp import extract_research_gap_sections, fix_common_artifacts, generate_summary_bart
        
        sections_doc1 = extract_research_gap_sections(text1)
        sections_doc2 = extract_research_gap_sections(text2)
        
        def clean(t): return fix_common_artifacts(t) if t else ""

        l1 = clean(sections_doc1['limitations'])
        f1 = clean(sections_doc1['future_work'])
        l2 = clean(sections_doc2['limitations'])
        f2 = clean(sections_doc2['future_work'])

        # --- FIX "WE" to "THE AUTHORS" ---
        def neutralize_perspective(text):
            if not text: return ""
            t = re.sub(r'(^|\.\s+)We\s', r'\1The authors ', text, flags=re.IGNORECASE)
            t = re.sub(r'\sour\s', ' their ', t, flags=re.IGNORECASE)
            return t.strip()

        l1 = neutralize_perspective(l1)
        f1 = neutralize_perspective(f1)
        l2 = neutralize_perspective(l2)
        f2 = neutralize_perspective(f2)

        # --- GENERATE SYNTHESIS (Always Try) ---
        # Jangan pakai 'if has_content', langsung coba saja.
        # Jika kosong, tulis "Not stated".
        
        combined_context = (
            f"Compare these two research papers.\n\n"
            f"Paper 1 Text: {l1 if l1 else 'No limitations stated'}. {f1 if f1 != l1 else ''}\n\n" # Hindari duplikasi jika isinya sama
            f"Paper 2 Text: {l2 if l2 else 'No limitations stated'}. {f2 if f2 != l2 else ''}\n\n"
            f"Synthesis of Research Gap (Identify missing aspects and future opportunities):"
        )
        
        # Potong input
        combined_context = combined_context[:4000]
        
        try:
            gap_synthesis = generate_summary_bart(combined_context, self.summarizer)
        except Exception as e:
            logger.error(f"Gap synthesis failed: {e}")
            gap_synthesis = "Could not synthesize research gap."

        # --- CLEAN UP DISPLAY TEXT ---
        # Jika limitation dan future work sama persis (hasil fallback), tampilkan di salah satu saja agar UI rapi
        if l1 == f1 and l1:
            f1 = "See Limitations section."
        if l2 == f2 and l2:
            f2 = "See Limitations section."

        return {
            "doc1_analysis": {
                "limitations_text": l1 if len(l1) > 20 else "No specific limitations detected.",
                "future_work_text": f1 if len(f1) > 20 else "No specific future work detected.",
            },
            "doc2_analysis": {
                "limitations_text": l2 if len(l2) > 20 else "No specific limitations detected.",
                "future_work_text": f2 if len(f2) > 20 else "No specific future work detected.",
            },
            "synthesis": gap_synthesis
        }
    
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
        Extract text from PDF, DOCX, or TXT file
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text or None if failed
        """
        if file_path.lower().endswith('.pdf'):
            return extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            return extract_text_from_docx(file_path)
        elif file_path.lower().endswith('.txt'):
            # Support for plain text files (e.g., from Mendeley import)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading text file {file_path}: {e}")
                return None
        else:
            logger.error(f"Unsupported file type: {file_path}")
            return None
    
    async def extract_keywords(self, text: str, num_keywords: int = 10) -> List[str]:
        """Extract keywords from text using KeyBERT"""
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
            keywords = extract_keywords_bert(
                text, 
                self.keyword_extractor,  # Lazy loading
                top_n=num_keywords
            )
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
        """Generate summary from text using BART"""
        """
        Generate summary from text using BART (English) or extractive method (Indonesian)
        
        Args:
            text: Document text
            max_length: Maximum summary length (not strictly enforced for extractive)
            
        Returns:
            Summary text
        """
        logger.info(f"Generating summary from text of length {len(text)}")
        try:
            # Deteksi bahasa
            lang = detect_language(text)
            
            # Untuk teks pendek atau bahasa Indonesia, gunakan extractive summary
            if lang == 'id' or len(text) < 200:
                logger.info(f"🇮🇩 Generating extractive summary (lang={lang})")
                from .custom_nlp import create_extractive_summary_indonesian
                summary = create_extractive_summary_indonesian(text, num_sentences=3)
            elif self.summarizer is None:
                logger.warning("BART not available, using extractive summary")
                from .custom_nlp import create_extractive_summary_indonesian
                summary = create_extractive_summary_indonesian(text, num_sentences=3)
            else:
                # Gunakan BART untuk teks panjang dalam bahasa Inggris
                summary = generate_summary_bart(text, self.summarizer)
            
            logger.info(f"Generated summary: {summary[:100]}...")
            return summary
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Failed to generate summary"
    
    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using embeddings"""
        logger.info("Calculating similarity between two texts")
        try:
            emb1 = generate_embeddings(text1, self.embedding_model)
            emb2 = generate_embeddings(text2, self.embedding_model)
            
            if emb1 is None or emb2 is None:
                logger.error("Failed to generate embeddings")
                return 0.0
            
            similarity_matrix = calculate_similarity_matrix([emb1, emb2])
            similarity = float(similarity_matrix[0][1])
            
            logger.info(f"Similarity score: {similarity:.3f}")
            return similarity
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text with caching"""
        text_hash = self._get_text_hash(text)
        if text_hash in self.embeddings_cache:
            self.cache_hits += 1
            logger.info(f"✅ Cache hit for embeddings ({self.cache_hits} hits)")
            return self.embeddings_cache[text_hash]
        
        self.cache_misses += 1
        try:
            embedding = generate_embeddings(text, self.embedding_model)  # Lazy load
            if embedding is not None:
                embedding_list = embedding.tolist()
                self.embeddings_cache[text_hash] = embedding_list
                logger.info(f"💾 Cached embeddings")
                return embedding_list
            return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def compute_document_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple documents"""
        logger.info(f"Computing embeddings for {len(texts)} documents")
        embeddings = []
        for i, text in enumerate(texts):
            # logger.info(f"Generating embedding {i+1}/{len(texts)}")
            embedding = generate_embeddings(text, self.embedding_model)
            if embedding is not None:
                embeddings.append(embedding)
            else:
                logger.warning(f"Failed to generate embedding for document {i+1}")
                embeddings.append(np.zeros(384)) 
        return embeddings
    
    def compute_similarity(self, embeddings: List[np.ndarray]) -> np.ndarray:
        """Compute pairwise similarity matrix from embeddings"""
        logger.info(f"Computing similarity matrix for {len(embeddings)} embeddings")
        try:
            similarity_matrix = calculate_similarity_matrix(embeddings)
            logger.info(f"✅ Generated similarity matrix")
            return similarity_matrix
        except Exception as e:
            logger.error(f"Error computing similarity matrix: {e}")
            n = len(embeddings)
            return np.eye(n)


# Singleton instance
nlp_service = NLPService()