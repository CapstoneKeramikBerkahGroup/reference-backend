"""
Custom NLP Service - High Performance & Hybrid Multilingual Support
Version: V6 (Anti-Data Summary & Phrase-Aware Keywords)
"""

import fitz  # PyMuPDF
import docx
import os
import re
import numpy as np
from keybert import KeyBERT
from transformers import pipeline
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
from typing import List, Dict, Tuple, Optional
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global Settings ---
MAX_CHARS_FOR_MODEL = 3500 
SIMILARITY_THRESHOLD = 0.50
DEVICE = -1 
DEVICE_NAME = "CPU"
logger.info(f"💡 NLP Service running on: {DEVICE_NAME}")

# --- Indonesian Language Support ---
INDONESIAN_STOPWORDS = {
    # Kata Sambung
    'dan', 'atau', 'yang', 'di', 'ke', 'dari', 'dengan', 'untuk', 'oleh', 'pada',
    'dalam', 'adalah', 'ini', 'itu', 'akan', 'telah', 'dapat', 'tidak', 'ia',
    'hanya', 'juga', 'sangat', 'lebih', 'lagi', 'lalu', 'saat', 'sementara', 'ketika',
    'sebelum', 'sesudah', 'selama', 'sejak', 'hingga', 'karena', 'melalui', 'atas',
    'bawah', 'antara', 'anda', 'kami', 'kita', 'mereka', 'dia', 'nya', 'ku', 'mu',
    'saya', 'kalian', 'siapa', 'apa', 'mana', 'berapa', 'kapan', 'dimana',
    'bagaimana', 'mengapa', 'setiap', 'semua', 'beberapa', 'banyak', 'sedikit', 'suatu',
    'ya', 'pula', 'pun', 'nah', 'tapi', 'tetapi', 'malah', 'padahal', 'namun', 
    'sebaliknya', 'selain', 'meskipun', 'walaupun', 'jika', 'kalau', 'jikalau', 
    'asalkan', 'biarpun', 'sambil', 'sekaligus', 'yaitu', 'yakni', 'seperti', 'merupakan',
    'terhadap', 'secara', 'maka', 'tentang', 'serta',
    
    # Kata Umum Jurnal (Agar tidak jadi keyword sampah)
    'menggunakan', 'penggunaan', 'digunakan', 'dilakukan', 'melakukan',
    'hasil', 'penelitian', 'studi', 'analisis', 'metode', 'metodologi', 'data',
    'berdasarkan', 'menunjukkan', 'kesimpulan', 'saran', 'daftar', 'pustaka',
    'jurnal', 'volume', 'halaman', 'nomor', 'tahun', 'vol', 'no', 'pp', 'hal',
    'et', 'al', 'etc', 'abstrak', 'pendahuluan', 'latar', 'belakang',
    'gambar', 'tabel', 'grafik', 'lampiran', 'bab', 'penulis', 'karya',
    'universitas', 'program', 'studi', 'fakultas', 'teknik', 'informatika',
    'model', 'nilai', 'score', 'compound', '2020', '2021', '2022', '2023', '2024', '2025',
    
    # English Stopwords
    'the', 'a', 'an', 'as', 'at', 'be', 'by', 'for', 'if', 'in', 'into', 'is', 'it',
    'not', 'of', 'on', 'or', 'such', 'that', 'to', 'was', 'will', 'with', 'and', 
    'using', 'based', 'result', 'results', 'method', 'study', 'research'
}

# --- HELPER FUNCTIONS ---

def preprocess_indonesian_text(text: str) -> str:
    if not text: return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = "".join(ch for ch in text if ch.isprintable() or ch in ['\n', '\t', '\r'])
    return text.lower()

def remove_indonesian_stopwords(tokens: List[str]) -> List[str]:
    return [token for token in tokens if token.lower() not in INDONESIAN_STOPWORDS and len(token) > 2]

def detect_language(text: str) -> str:
    text_lower = text.lower()
    id_markers = ['yang', 'dengan', 'untuk', 'dari', 'dalam', 'adalah', 'telah', 
                  'dapat', 'tidak', 'oleh', 'ini', 'itu', 'dan', 'atau', 'pada']
    id_count = sum(1 for marker in id_markers if f" {marker} " in text_lower)
    return 'id' if id_count >= 5 else 'en'

def extract_keywords_indonesian(text: str, top_n: int = 10) -> List[str]:
    """Fallback manual jika KeyBERT gagal."""
    if not text or len(text.strip()) < 50: return []
    try:
        text_clean = preprocess_indonesian_text(text)
        tokens = re.findall(r'\b[a-zA-Z0-9-]+\b', text_clean)
        tokens = remove_indonesian_stopwords(tokens)
        freq = Counter(tokens)
        return [word for word, count in freq.most_common(top_n)]
    except Exception as e:
        logger.error(f"❌ Error extracting Indonesian keywords: {e}")
        return []

# --- Cleaning & Locating ---

def clean_text_lines(text: str) -> str:
    lines = text.split('\n')
    cleaned_lines = []
    
    trash_markers = [
        r'journal of', r'vol\.', r'no\.', r'pp\.', r'doi:', 
        r'accepted', r'received', r'published', r'copyright', 
        r'all rights reserved', r'https?://', r'www\.',
        r'correspondence', r'email:', r'department of', 
        r'university of', r'faculty of', r'school of',
        r'institute of', r'ph\.?d', r'm\.?d', r'm\.?sc',
        r'\(cid:\d+\)', r'^\d{4}$', r'^page \d+',
        r'jurnal', r'volume', r'halaman', r'diterima', r'disetujui',
        r'^authors?:', r'^written by:', r'^by\s+:'
    ]
    
    for line in lines:
        line_clean = line.strip()
        if len(line_clean) < 3: continue
        is_trash = False
        for marker in trash_markers:
            if re.search(marker, line_clean, re.IGNORECASE):
                is_trash = True
                break
        if not is_trash:
            cleaned_lines.append(line_clean)
            
    return " ".join(cleaned_lines)

def locate_intro_or_abstract(text: str) -> str:
    match_intro = re.search(r'(?:^|\n)(?:\d+\.|I\.|)\s*(Introduction|Pendahuluan)', text, re.IGNORECASE)
    if match_intro:
        return text[match_intro.start():]
    match_abst = re.search(r'(?:^|\n)(Abstract|Abstrak)', text, re.IGNORECASE)
    if match_abst:
        return text[match_abst.start():]
    return text

def fix_common_artifacts(text: str) -> str:
    text = re.sub(r'(\d+)\s?e\s?(\d+)', r'\1-\2', text)
    text = re.sub(r'\s+([.,;:])', r'\1', text)
    text = re.sub(r'([.,;:])([a-zA-Z])', r'\1 \2', text)
    text = text.replace('', '')
    text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text) 
    text = "".join(ch for ch in text if ch.isprintable() or ch in ['\n', '\t', '\r'])
    return text.strip()

# --- Extraction Functions ---
def extract_text_from_pdf(file_path: str) -> Optional[str]:
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"⚠️ Failed to process PDF: {e}")
        return None

def extract_text_from_docx(file_path: str) -> Optional[str]:
    try:
        doc = docx.Document(file_path)
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        return " ".join(paragraphs)
    except Exception as e:
        logger.error(f"⚠️ Failed to process DOCX: {e}")
        return None

# --- NLP Core Functions ---

def extract_keywords_bert(text: str, kw_model_instance: KeyBERT, top_n: int = 10, ngram_range: Tuple[int, int] = (1, 2)) -> List[str]:
    """
    Ekstraksi Keyword dengan KeyBERT.
    Support N-gram (1, 2) untuk menangkap 'Analisis Sentimen'.
    """
    if not text or len(text.strip()) < 50: return []
    try:
        clean_text = clean_text_lines(text)
        target_text = locate_intro_or_abstract(clean_text)[:MAX_CHARS_FOR_MODEL]
        
        stopwords_list = list(INDONESIAN_STOPWORDS)
        
        keywords = kw_model_instance.extract_keywords(
            target_text,
            keyphrase_ngram_range=(1, 2), # Paksa ambil 1 atau 2 kata
            stop_words=stopwords_list,         
            use_maxsum=True, 
            nr_candidates=20, 
            top_n=top_n
        )
        
        # Filter ketat: Hapus jika cuma angka, atau cuma 1 huruf
        final_keywords = []
        for kw, s in keywords:
            if len(kw) > 3 and not kw.replace(' ', '').isdigit():
                final_keywords.append(kw)
                
        return final_keywords

    except Exception as e:
        logger.error(f"❌ Error KeyBERT: {e}")
        return []

# --- SUMMARY LOGIC (ANTI-DATA V6) ---

def polish_english_summary(text: str) -> str:
    if not text: return ""
    text = text.strip()
    text = re.sub(r'^\s*(Authors?|Abstract|Introduction|Written by|By)\s*[:\-\.]\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[A-Z][a-z]+ [A-Z][a-z]+[:\-\.]\s*', '', text)

    replacements = [
        (r'\bWe\b', 'The authors'), (r'\bwe\b', 'the authors'),
        (r'\b(Our|My)\b', 'The'), (r'\b(us)\b', 'the study'),
        (r'\b(I)\b', 'The author'), (r'(?<=\.\s)They\b', 'The authors'),
        (r'^They\b', 'The authors'), (r'\b(This paper|This article)\b', 'This study')
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text) 
        if pattern == r'\b(Our|My)\b': text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    text = text.strip()
    if text: text = text[0].upper() + text[1:]
    return text

def create_extractive_summary_indonesian(text: str, num_sentences: int = 3) -> str:
    """
    [ENHANCED V6] Summary Indo 'Abstractive-Like'.
    Filter ketat terhadap kalimat yang berisi tanggal spesifik/angka raw.
    """
    if not text or len(text.strip()) < 50: return text
    
    # 1. Cleaning Metadata
    text = re.sub(r'Jurnal.*?(\n|$)', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'Vol.*?(\n|$)', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'ISSN.*?(\n|$)', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'(Keywords|Kata Kunci):.*?(\n|$)', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\d+\]', '', text) 
    text = re.sub(r'\([A-Za-z\s\.,]+?\d{4}\)', '', text)

    # 2. Smart Split
    text = re.sub(r'([A-Z][a-z]+)\.\s(?=[A-Z][a-z]+)', r'\1 ', text) # Fix New. York.
    raw_sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s+(?=[A-Z])', text)
    
    sentences = []
    
    # 3. FILTER DATA MENTAH (Ini yang memperbaiki masalah tanggal/angka)
    for s in raw_sentences:
        s = s.strip()
        if len(s.split()) < 5: continue
        
        # Buang jika ada tanggal spesifik (misal: "6 Juni 2024", "10 Juli")
        if re.search(r'\d{1,2}\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)', s, re.IGNORECASE):
            continue
            
        # Buang jika banyak angka desimal/raw score (misal: "score 0.0999", "2906.57")
        if re.search(r'\d+\.\d{2,}', s):
            continue
            
        sentences.append(s)
    
    if len(sentences) <= num_sentences: return ' '.join(sentences)

    best_sentences = {'goal': None, 'method': None, 'result': None}
    best_scores = {'goal': 0, 'method': 0, 'result': 0}

    markers = {
        'goal': ['bertujuan', 'tujuannya', 'fokus', 'membahas', 'menganalisis', 'meneliti'],
        'method': ['menggunakan', 'metode', 'algoritma', 'pendekatan', 'penerapan', 'melalui', 'integrasi'],
        'result': ['hasil', 'kesimpulan', 'menunjukkan', 'terbukti', 'didapatkan', 'kontribusi', 'secara keseluruhan']
    }

    for sent in sentences:
        sent_lower = sent.lower()
        if any(x in sent_lower for x in ['keywords', 'kata kunci', 'doi:', 'pp.']): continue
        
        for category, keywords in markers.items():
            score = 0
            matches = sum(1 for k in keywords if k in sent_lower)
            if matches > 0:
                score += matches * 10
                word_len = len(sent.split())
                if 10 < word_len < 40: score += 5
                
                idx = sentences.index(sent)
                if category == 'goal' and idx < len(sentences)*0.3: score += 5
                if category == 'result' and idx > len(sentences)*0.6: score += 5

                if score > best_scores[category]:
                    best_scores[category] = score
                    best_sentences[category] = sent

    final_parts = []
    
    # A. Goal
    goal_sent = best_sentences['goal']
    if not goal_sent and sentences: goal_sent = sentences[0]
    if goal_sent:
        goal_sent = re.sub(r'^(ABSTRAK|PENDAHULUAN|Latar Belakang)\s*', '', goal_sent, flags=re.IGNORECASE)
        goal_sent = re.sub(r'^(Penelitian|Tulisan|Artikel|Jurnal|Paper) ini', 'Studi ini', goal_sent, flags=re.IGNORECASE)
        if not re.match(r'^(Studi|Penelitian|Makalah)', goal_sent):
            goal_sent = "Studi ini " + goal_sent[0].lower() + goal_sent[1:]
        final_parts.append(goal_sent)

    # B. Method
    method_sent = best_sentences['method']
    if method_sent and method_sent != goal_sent:
        method_sent = re.sub(r'^(Adapun|Dalam|Pada)\s*', '', method_sent, flags=re.IGNORECASE)
        if re.match(r'^[A-Z]{3,}', method_sent): 
            method_sent = "Metode " + method_sent
        method_sent = method_sent[0].upper() + method_sent[1:]
        final_parts.append(method_sent)

    # C. Result
    result_sent = best_sentences['result']
    if result_sent and result_sent != goal_sent and result_sent != method_sent:
        result_sent = re.sub(r'^(Berdasarkan|Dari|Maka)\s*(hasil|data|penelitian|analisis|kesimpulan).*?(bahwa|maka)\s*', 'Hasil evaluasi menunjukkan bahwa ', result_sent, flags=re.IGNORECASE)
        result_sent = re.sub(r'^Evaluasi model Prophet menunjukkan', 'Hasil evaluasi menunjukkan', result_sent, flags=re.IGNORECASE)
        if len(result_sent) > 1:
            result_sent = result_sent[0].upper() + result_sent[1:]
        final_parts.append(result_sent)

    summary = ' '.join(final_parts)
    return re.sub(r'\s+', ' ', summary).strip()

def generate_summary_bart(text: str, summarizer_instance) -> str:
    """Hybrid Summary: Indo (Enhanced), Eng (BART + Polish)."""
    if not text or len(text.strip()) < 100: return "Text too short."
    try:
        clean_text = clean_text_lines(text)
        target_text = locate_intro_or_abstract(clean_text)
        lang = detect_language(target_text)
        
        if lang == 'id':
            logger.info("🇮🇩 Indo text. Using Enhanced V6 Summary.")
            final_summary = create_extractive_summary_indonesian(target_text, num_sentences=4)
        else:
            logger.info("🇬🇧 English text. Using BART + Polishing.")
            input_text = target_text[:MAX_CHARS_FOR_MODEL]
            
            if summarizer_instance:
                summary = summarizer_instance(input_text, max_length=200, min_length=60, num_beams=1, do_sample=False)
                raw_summary = summary[0]['summary_text']
                final_summary = polish_english_summary(raw_summary)
            else:
                final_summary = create_extractive_summary_indonesian(input_text)
    except Exception as e:
        logger.warning(f"⚠️ Summary failed: {e}")
        return create_extractive_summary_indonesian(text) 
        
    return fix_common_artifacts(final_summary)

def extract_references(full_text: str) -> List[Dict[str, str]]:
    """[FIXED] Nuclear Reference Splitter."""
    if not full_text: return []

    normalized_text = re.sub(r'\r\n', '\n', full_text)
    normalized_text = re.sub(r'\n+', '\n', normalized_text)

    text_after = ""
    header_patterns = [r'(?:^|\n)\s*(\d+\.?\s*)?(REFERENCES|REFERENSI|DAFTAR PUSTAKA|BIBLIOGRAPHY)\s*(?:\n|$)']
    
    for pattern in header_patterns:
        match = re.search(pattern, normalized_text, re.IGNORECASE)
        if match:
            text_after = normalized_text[match.end():].strip()
            break
            
    if not text_after:
        start_search = int(len(normalized_text) * 0.7)
        last_part = normalized_text[start_search:]
        match_fallback = re.search(r'(REFERENCES|REFERENSI|DAFTAR PUSTAKA)', last_part, re.IGNORECASE)
        if match_fallback:
            text_after = last_part[match_fallback.end():].strip()
        else:
            return [] 

    is_blob = len(text_after) > 500 and text_after.count('\n') < 5
    if is_blob:
        blob_fix = re.sub(r'(\(\d{4}[a-z]?\))', r'\1\n', text_after)
        blob_fix = re.sub(r'(\[\d+\])', r'\n\1', blob_fix)
        lines = blob_fix.split('\n')
        
        initial_refs = []
        buffer = ""
        for line in lines:
            line = line.strip()
            if not line: continue
            if re.match(r'^[A-Z][a-z]+', line) and len(buffer) > 20:
                initial_refs.append({"nomor": None, "teks_referensi": buffer.strip()})
                buffer = line
            else:
                buffer += " " + line
        if buffer: initial_refs.append({"nomor": None, "teks_referensi": buffer.strip()})
        
        return [{"nomor": str(i+1), "teks_referensi": r['teks_referensi']} for i, r in enumerate(initial_refs[:50])]

    split_pattern = r'(?=\[\s*\d+\s*\])' 
    if re.search(split_pattern, text_after):
        raw_references = re.split(split_pattern, text_after)
    else:
        split_pattern_b = r'(?=\n\s*\d+\.\s)'
        raw_references = re.split(split_pattern_b, text_after)

    initial_refs = []
    for raw_ref in raw_references:
        clean_ref_text = raw_ref.strip()
        if len(clean_ref_text) < 5: continue

        match_bracket = re.match(r'^\[\s*(\d+)\s*\]', clean_ref_text)
        match_dot = re.match(r'^(\d+)\.\s', clean_ref_text)
        
        current_number = None
        final_ref_text = ""
        
        if match_bracket:
            current_number = match_bracket.group(1)
            final_ref_text = re.sub(r'^\[\s*\d+\s*\]\s*', '', clean_ref_text).strip()
        elif match_dot:
            current_number = match_dot.group(1)
            final_ref_text = re.sub(r'^\d+\.\s*', '', clean_ref_text).strip()
        else:
            final_ref_text = clean_ref_text

        final_ref_text = re.sub(r'\n', ' ', final_ref_text)
        final_ref_text = re.sub(r'\s+', ' ', final_ref_text).strip()

        if final_ref_text:
            initial_refs.append({"nomor": current_number, "teks_referensi": final_ref_text})

    merged_refs = []
    for ref in initial_refs:
        text = ref['teks_referensi']
        if not merged_refs:
            merged_refs.append(ref)
            continue
        prev_ref = merged_refs[-1]
        
        is_continuation = False
        if re.match(r'^[\d\–\-]+\s*[\–\-]\s*\d+', text) or re.match(r'^\d{4}\b', text): is_continuation = True
        elif re.match(r'^(vol\.|no\.|pp\.|doi:|isbn|issn)', text.lower()): is_continuation = True
        elif ref['nomor'] is None and re.match(r'^[a-z]', text): is_continuation = True

        if is_continuation:
            prev_ref['teks_referensi'] += " " + text
        else:
            merged_refs.append(ref)

    for i, ref in enumerate(merged_refs):
        ref['nomor'] = str(i + 1)

    return merged_refs[:50]

def generate_embeddings(text: str, embedding_model_instance: SentenceTransformer) -> Optional[np.ndarray]:
    if not text or len(text.strip()) < 50: return None
    try:
        clean_text = clean_text_lines(text)
        target_text = locate_intro_or_abstract(clean_text)[:MAX_CHARS_FOR_MODEL]
        return embedding_model_instance.encode(target_text, convert_to_numpy=True)
    except Exception as e:
        logger.error(f"❌ Error Embedding: {e}")
        return None

def calculate_similarity_matrix(embeddings: List[np.ndarray]) -> np.ndarray:
    if len(embeddings) < 2: raise ValueError("Need >1 embeddings")
    return cosine_similarity(np.array(embeddings))

def build_graph_data(filenames: List[str], similarity_matrix: np.ndarray, threshold: float = SIMILARITY_THRESHOLD) -> Dict:
    nodes = []
    edges = []
    for i in range(len(filenames)):
        fname_i = filenames[i]
        nodes.append({"id": fname_i, "label": fname_i[:25] + "..." if len(fname_i) > 25 else fname_i})
        for j in range(i + 1, len(filenames)):
            fname_j = filenames[j]
            similarity_score = similarity_matrix[i][j]
            if similarity_score > threshold:
                edges.append({"from": fname_i, "to": fname_j, "value": float(similarity_score), "title": f"Similarity: {similarity_score:.3f}"})
    return {"nodes": nodes, "edges": edges}

# --- Init Functions ---
def initialize_keybert_model(): 
    try: return KeyBERT(model='paraphrase-multilingual-MiniLM-L12-v2')
    except: return None

def initialize_summarizer(): 
    try: return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=DEVICE)
    except: return None

def initialize_embedding_model(): 
    return SentenceTransformer('all-MiniLM-L6-v2', device='cuda' if DEVICE == 0 else 'cpu')