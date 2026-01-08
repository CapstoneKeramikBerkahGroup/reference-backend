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
import google.generativeai as genai
import json
from app.core.config import settings


# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --Import & Config--
try:
    import google.generativeai as genai
    HAS_GEMINI_LIB = True
except ImportError:
    HAS_GEMINI_LIB = False

try:
    from app.core.config import settings
    GEMINI_API_KEY = getattr(settings, 'GOOGLE_API_KEY', None)
except ImportError:
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# --- Global Settings ---
MAX_CHARS_FOR_MODEL = 12000 
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
<<<<<<< Updated upstream

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
=======
    
def extract_key_technical_details(text: str, lang: str = 'en') -> List[str]:
>>>>>>> Stashed changes
    """
    Ekstraksi 'Jarum dalam Jerami': Performa, Metode, dan Hasil (Positif/Negatif).
    [FIX] Sekarang mendeteksi 'NO significant relationship' dan 'Hypothesis NOT rejected'.
    """
    extras = []
    seen_metrics = set()
    
    terms = {
        'en': {
            'perf': 'Performance', 'reach': 'reached', 
            'method': 'Method', 'desc': 'This study utilizes',
            'res': 'Key Finding', 
        },
        'id': {
            'perf': 'Performa', 'reach': 'mencapai', 
            'method': 'Metode', 'desc': 'Penelitian ini menggunakan',
            'res': 'Temuan Utama', 
        }
    }
    t = terms.get(lang, terms['en'])

    # --- 1. Cari Angka Performa (Sama) ---
    metric_pattern = re.compile(r'\b(accuracy|akurasi|precision|presisi|recall|f1[- ]score|mse|rmse|auc|map)\b.{0,20}\b(\d{1,3}(?:\.\d+)?\s?%|0\.\d{2,4})', re.IGNORECASE)
    matches_metric = metric_pattern.findall(text)
    for m in matches_metric:
        raw_name = m[0].lower()
        if raw_name in seen_metrics: continue
        seen_metrics.add(raw_name)
        metric_name = raw_name.title()
        if lang == 'en':
            metric_name = metric_name.replace('Akurasi', 'Accuracy').replace('Presisi', 'Precision').replace('Auc', 'AUC')
        else:
            metric_name = metric_name.replace('Auc', 'AUC')
        extras.append(f"• 📊 {t['perf']}: {metric_name} {t['reach']} {m[1]}")

    # --- 2. Cari Nama Metode (Sama) ---
    known_models = [
        'SVM', 'Support Vector Machine', 'Naive Bayes', 'Random Forest', 'Decision Tree',
        'LSTM', 'CNN', 'RNN', 'BERT', 'Transformer', 'YOLO', 'ResNet', 'VGG', 
        'K-Nearest Neighbor', 'KNN', 'Logistic Regression', 'Gradient Boosting', 'XGBoost',
        'Prophet', 'ARIMA', 'PLS-SEM', 'SPSS', 'Chi-Square', 'Mann-Whitney' # Tambah metode statistik
    ]
    found_models = []
    seen_models = set()
    for model in known_models:
        if re.search(r'\b' + re.escape(model) + r'\b', text, re.IGNORECASE):
            model_key = model.upper()
            if model_key == 'SUPPORT VECTOR MACHINE': model_key = 'SVM'
            if model_key == 'K-NEAREST NEIGHBOR': model_key = 'KNN'
            if model_key not in seen_models:
                found_models.append(model)
                seen_models.add(model_key)
    
    if found_models:
        models_str = ", ".join(sorted(found_models))
        extras.append(f"• ⚙️ {t['method']}: {t['desc']} {models_str}.")

    # --- 3. [FIX] Cari Pernyataan Hasil dengan Konteks Negatif ---
    
    # Prioritas 1: Cek Hasil NEGATIF dulu (No significant, Not rejected)
    negative_patterns = [
        r'(no|not|fail\w* to|did not)\s+(find\w* )?(any )?(significant|meaningful)\s+(relationship|correlation|effect|impact|influence|association)', # "no significant relationship"
        r'(null )?hypothesis.*?not\s+(rejected|supported)', # "hypothesis was not rejected"
        r'(no|not)\s+(significantly)\s+(influence|affect|impact)', # "did not significantly influence"
        r'found no evidence',
        r'tidak\s+(ada\s+)?(hubungan|pengaruh|dampak)\s+(yang\s+)?(signifikan)',
    ]
    
    # Prioritas 2: Cek Hasil POSITIF (Hanya jika tidak ada negatif di kalimat yg sama)
    positive_patterns = [
        r'significant\s+(positive|negative)?\s*(relationship|correlation|effect|impact|influence|association)',
        r'(positive|negative)\s+(relationship|correlation|effect|impact|influence)',
        r'hypothesis\s+(was|is)\s+(accepted|supported)', # Hati-hati dengan "rejected" (bisa berarti hipotesis nol ditolak = ada hubungan)
        r'null hypothesis\s+(was|is)\s+rejected', # Null ditolak = Signifikan
        r'significantly\s+(influence|affect|impact)'
    ]

    sentences = re.split(r'(?<=[.!?])\s+', text)
    found_result = None
    
    for sent in sentences:
        sent_clean = sent.strip()
        if len(sent_clean) < 20 or len(sent_clean) > 300: continue 
        
        # Cek Negatif Dulu
        is_negative = False
        for pat in negative_patterns:
            if re.search(pat, sent_clean, re.IGNORECASE):
                is_negative = True
                # Bersihkan sitasi
                sent_clean = re.sub(r'\[.*?\]', '', sent_clean)
                sent_clean = re.sub(r'\(.*?\d{4}.*?\)', '', sent_clean)
                # Ambil kalimat penuh atau bagian setelah 'that'
                if "that " in sent_clean:
                     parts = sent_clean.split("that ", 1)
                     if len(parts[1]) > 20: found_result = parts[1]
                else:
                    found_result = sent_clean
                break
        
        if is_negative and found_result: break # Prioritaskan temuan negatif/tidak adanya hubungan (biasanya ini poin utama paper tsb)

        # Jika tidak negatif, cek positif
        if not found_result:
            for pat in positive_patterns:
                if re.search(pat, sent_clean, re.IGNORECASE):
                    # Double check: pastikan tidak ada kata "no" atau "not" tepat di depan match (jika regex lolos)
                    # Misal: "showed no significant effect"
                    if re.search(r'\b(no|not)\b.{0,10}' + pat, sent_clean, re.IGNORECASE):
                        continue # Skip, ini sebenarnya negatif
                        
                    sent_clean = re.sub(r'\[.*?\]', '', sent_clean)
                    sent_clean = re.sub(r'\(.*?\d{4}.*?\)', '', sent_clean)
                    if "that " in sent_clean:
                        parts = sent_clean.split("that ", 1)
                        if len(parts[1]) > 20: found_result = parts[1]
                    else:
                        found_result = sent_clean
                    break
        
        if found_result: break

    if found_result:
        found_result = found_result.strip().strip('.')
        found_result = found_result[0].upper() + found_result[1:]
        extras.append(f"• 📈 {t['res']}: {found_result}.")

    return extras


def generate_smart_summary_gemini(text: str, lang: str = 'id') -> Optional[str]:
    """
    Generate summary Deep Dive menggunakan Gemini.
    Fitur:
    1. Format JUDUL BESAR + Bullet Points Murni (Bukan Narasi).
    2. Universal: Adaptif untuk Audit, Dev, atau Data Mining.
    3. Conciseness: Poin-poin padat dan langsung pada intinya.
    """
    if not HAS_GEMINI_LIB or not GEMINI_API_KEY:
        logger.warning("❌ Gemini Lib missing or API Key not set.")
        return None

    try:
        # 1. Cleaning & Truncating
        clean_text = clean_text_lines(text)
        clean_text = fix_common_artifacts(clean_text)
        
        # Ambil konteks luas
        head_text = clean_text[:6000]
        mid_index = len(clean_text) // 2
        mid_text = clean_text[mid_index : mid_index+4500] 
        tail_text = clean_text[-4500:]
        
        combined_text = f"{head_text}\n...\n{mid_text}\n...\n{tail_text}"

        # 2. PROMPT STRICT FORMAT (Header + Bullets)
        base_instruction = """
        Peran: Lead Technical Reviewer.
        Tugas: Ekstrak "Deep Dive Summary" dari paper ini.
        
        ATURAN FORMAT (WAJIB PATUH):
        1. GUNAKAN JUDUL BAGIAN (HEADER) DALAM HURUF KAPITAL.
        2. ISI WAJIB DALAM BULLET POINTS (*). JANGAN GUNAKAN PARAGRAF NARASI.
        3. JANGAN GUNAKAN EMOJI.
        4. Setiap bullet point harus RINGKAS (maksimal 2 kalimat).
        5. Deskripsikan rumus matematika dengan kata-kata sederhana.

        LOGIKA ADAPTIF (SESUAIKAN DENGAN TIPE PAPER):
        - Tipe AUDIT/TATA KELOLA (COBIT/ITIL): Fokus pada Domain Audit, Gap Analysis, dan Level Kapabilitas.
        - Tipe PENGEMBANGAN SISTEM: Fokus pada Stack Teknologi, Metode SDLC, dan Hasil Testing (UAT/Blackbox).
        - Tipe DATA/AI: Fokus pada Dataset, Preprocessing, Algoritma, dan Metrik Evaluasi.

        FORMAT OUTPUT YANG DIHARAPKAN:

        [English]
        ### CONTEXT & RESEARCH GAP
        * [Point 1: Specific problem or gap being addressed]
        * [Point 2: Why current solutions are insufficient]

        ### TECHNICAL IMPLEMENTATION
        * [Point 1: Core method/algorithm/framework used]
        * [Point 2: Specific tools, dataset size, or audit domains]
        * [Point 3: How the process works (step-by-step logic)]

        ### CRITICAL FINDINGS & INSIGHTS
        * [Point 1: Main result (accuracy numbers, capability levels, etc.)]
        * [Point 2: Anomalies, limitations, or user feedback found]

        [Indonesia]
        ### KONTEKS & MASALAH
        * [Poin 1: Masalah spesifik atau gap penelitian]
        * [Poin 2: Mengapa solusi yang ada belum cukup]

        ### IMPLEMENTASI TEKNIS
        * [Poin 1: Metode/Algoritma/Framework inti yang digunakan]
        * [Poin 2: Tools spesifik, ukuran dataset, atau domain audit]
        * [Poin 3: Logika cara kerja (jelaskan rumus secara deskriptif)]

        ### TEMUAN KRITIS & INSIGHT
        * [Poin 1: Hasil utama (angka akurasi, level kapabilitas, dll)]
        * [Poin 2: Temuan unik, anomali, atau limitasi yang diakui]
        """

        # 3. Eksekusi Request
        genai.configure(api_key=GEMINI_API_KEY)
        models_to_try = [            
            'gemini-pro-latest',          
            'gemini-3-flash-preview',     
            'gemini-pro' 
        ]
        
        for model_name in models_to_try:
            try:
                real_model_name = model_name.replace("models/", "")
                logger.info(f"⏳ Summarizing with {real_model_name}...")
                model = genai.GenerativeModel(real_model_name)
                
                final_prompt = f"{base_instruction}\n\nTEKS DOKUMEN:\n{combined_text}"
                
                response = model.generate_content(final_prompt)
                result = response.text.strip()
                
                # Bersihkan markdown bold (**teks**) agar lebih bersih
                result = result.replace('**', '')
                
                if result and len(result) > 50:
                    logger.info(f"✅ Deep Summary generated with {real_model_name}")
                    return result
            except Exception as e:
                logger.warning(f"⚠️ Model {model_name} failed: {e}")
                continue
        
        return None

    except Exception as e:
        logger.error(f"❌ Error in Gemini Summary: {e}")
        return None
        
def generate_summary_bart(text: str, summarizer_instance) -> str:
    """
    Hybrid Summary: 
    1. Try Gemini (High Accuracy & Perfect Formatting).
    2. Fallback to BART + Regex Extraction (Offline mode).
    """
    if not text or len(text.strip()) < 100: return "Text too short."
    
    # --- 1. PRIORITY: GEMINI API ---
    gemini_result = generate_smart_summary_gemini(text, lang='en')
    if gemini_result:
        return gemini_result
    
    # --- 2. FALLBACK: LOCAL BART + REGEX ---
    logger.info("🔄 Using Fallback BART Summary for English...")
    try:
        clean_text = clean_text_lines(text)
        target_text = locate_intro_or_abstract(clean_text)
<<<<<<< Updated upstream
=======
        input_text = target_text[:MAX_CHARS_FOR_MODEL]
        
        # Generate Summary by AI
        summary = summarizer_instance(
            input_text, max_length=200, min_length=60, 
            num_beams=1, do_sample=False, no_repeat_ngram_size=3
        )
        raw_summary = summary[0]['summary_text']
        
        # Format Bullet Points
        polished_summary = polish_english_summary(raw_summary)
        
        # Extract Technical Details (Manual Regex)
        technical_bullets = extract_key_technical_details(target_text, lang='en')
        
        if technical_bullets:
            polished_summary += "\n" + "\n".join(technical_bullets)
            
        return polished_summary
        
    except Exception as e:
        logger.warning(f"⚠️ BART Summary failed: {e}")
        return "Failed to generate summary."
    
def translate_summary_to_indonesian(english_summary: str) -> str:
    """
    Translate English summary to Indonesian using Helsinki-NLP neural translation model.
    Automatically handles ANY English terms without requiring manual dictionary updates.
    
    Falls back to dictionary-based translation if model unavailable.
    """
    if not english_summary:
        return ""
    
    try:
        # Try to use neural translation model (automatic, comprehensive)
        return _translate_with_neural_model(english_summary)
    except Exception as e:
        logger.warning(f"Neural translation failed ({e}), falling back to dictionary...")
        # Fallback to dictionary if model fails
        return _translate_with_dictionary(english_summary)


def _translate_with_neural_model(english_summary: str) -> str:
    try:
        from transformers import pipeline
        translator = pipeline(
            'translation_en_to_id',
            model='Helsinki-NLP/opus-mt-en-id',
            device=-1
        )

        # merge broken bullets
        raw_lines = english_summary.split('\n')
        merged_lines, current = [], ""

        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("•"):
                if current:
                    merged_lines.append(current.strip())
                current = line
            else:
                current += " " + line
        if current:
            merged_lines.append(current.strip())

        translated_bullets = []

        for line in merged_lines:
            # ===== STEP 0: CLEAN DASAR =====
            clean_input = re.sub(r'^[•\-\*]\s*', '', line)
            clean_input = re.sub(r'\s+', ' ', clean_input).strip()
            if len(clean_input) < 3:
                continue

            # ===== STEP 1: NORMALISASI LABEL (DI SINI!) =====
            label_fixes = {
                r'^📈\s*Key Finding[:\s]*': 'Key Finding: ',
                r'^📊\s*Performance[:\s]*': 'Performance: ',
                r'^⚙️\s*Method[:\s]*': 'Method: '
            }
            for p, rpl in label_fixes.items():
                clean_input = re.sub(p, rpl, clean_input, flags=re.IGNORECASE)

            # ===== PROTEKSI METODE =====
            if 'Method: This study utilizes' in clean_input:
                parts = clean_input.split('utilizes')
                if len(parts) > 1:
                    translated_bullets.append(
                        f"• ⚙️ Metode: Penelitian ini menggunakan {parts[1].strip()}"
                    )
                    continue

            try:
                # ===== TRANSLATE =====
                res = translator(clean_input, max_length=512)[0]['translation_text']

                # ===== STEP 2: FIX LABEL & AKADEMIK =====
                res = re.sub(r'^Key Finding[:\s]*', '📈 Temuan Utama: ', res, flags=re.IGNORECASE)
                res = re.sub(r'^Performance[:\s]*', '📊 Kinerja: ', res, flags=re.IGNORECASE)
                res = re.sub(r'^Method[:\s]*', '⚙️ Metode: ', res, flags=re.IGNORECASE)

                academic_fixes = {
                    r'Penampilan': 'Kinerja',
                    r'kesempatan politik': 'dinamika politik',
                    r'menerapkan jam': 'menggunakan analisis per jam',
                    r'prakiraan': 'prediksi'
                }
                for p, rpl in academic_fixes.items():
                    res = re.sub(p, rpl, res, flags=re.IGNORECASE)

                res = res.replace('\n', ' ')
                res = re.sub(r'\s+', ' ', res).strip()
                res = res[0].upper() + res[1:]

                translated_bullets.append(f"• {res}")

            except Exception as e:
                logger.warning(f"Translation skip: {e}")
                translated_bullets.append(f"• {clean_input}")

        return '\n'.join(translated_bullets)

    except Exception as e:
        logger.error(f"Neural translation error: {e}")
        return _translate_with_dictionary(english_summary)

def _translate_with_dictionary(english_summary: str) -> str:
    """
    Fallback: Emergency-only translation using minimal dictionary.
    Only used if neural model fails. Neural model should handle 99% of cases.
    """
    if not english_summary:
        return ""
    
    # Minimal fallback - only critical terms for emergency use
    minimal_dict = {
        'research': 'penelitian', 'study': 'studi', 'analysis': 'analisis',
        'result': 'hasil', 'method': 'metode', 'conclusion': 'kesimpulan',
        'data': 'data', 'model': 'model', 'system': 'sistem',
        'important': 'penting', 'significant': 'signifikan', 'presented': 'disajikan',
    }
    
    result = english_summary
    for eng, indo in minimal_dict.items():
        pattern = r'\b' + re.escape(eng) + r'\b'
        result = re.sub(pattern, indo, result, flags=re.IGNORECASE)
    
    return result

def generate_embeddings(text: str, model: SentenceTransformer) -> Optional[np.ndarray]:
    if not text or len(text.strip()) < 50: return None
    try:
        clean = fix_common_artifacts(text)
        target = locate_intro_or_abstract(clean)[:MAX_CHARS_FOR_MODEL]
        return model.encode(target, convert_to_numpy=True)
>>>>>>> Stashed changes
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
    """[FIXED] Nuclear Reference Splitter - Enhanced untuk English References."""
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
        # AGGRESSIVE Blob Splitting - Multiple strategies to find reference boundaries
        blob_fix = text_after
        
        # STRATEGY 1: Split sebelum pola "Author, Initial" yang jelas
        # Contoh: "...Workshops. Alexander P, Ilya R"
        # Pola: ". " atau ") " diikuti Capital Letter, Capital Letter pattern
        blob_fix = re.sub(
            r'([.)\],])\s+(?=[A-Z][a-z\-]*(?:\s+[A-Z][a-z\-]*)*\s+[A-Z])',
            r'\1\n',
            blob_fix
        )
        
        # STRATEGY 2: Split sebelum "et al"
        blob_fix = re.sub(
            r'(?<!\w)\s+([A-Z][a-z\-]+\s+et\s+al\.)',
            r'\n\1',
            blob_fix
        )
        
        # STRATEGY 3: Split setelah year pattern ketika diikuti author baru
        # Contoh: "2021. Mehta et al." atau "2020. Barot V"
        blob_fix = re.sub(
            r'(\d{4}[a-z]?[,.\)]\s*)(?=[A-Z][a-z\-]*\s+[A-Z][a-z\-]*)',
            r'\1\n',
            blob_fix
        )
        
        # STRATEGY 4: Split setelah metadata (DOI, ISBN, page numbers)
        # Contoh: "10.3390/s20205780. Mehta et al"
        blob_fix = re.sub(
            r'(DOI\s+[\d.\/]+|ISBN[\d\-]*|pp\.\s*[\d\-]+)\s+(?=[A-Z])',
            r'\1\n',
            blob_fix
        )
        
        # STRATEGY 5: Split sebelum bracketed references
        blob_fix = re.sub(r'(?<!\n)\s*(\[\d+\])', r'\n\1', blob_fix)
        
        # STRATEGY 6: Split setelah closing bracket/paren ketika diikuti author
        # Contoh: "...imaging. Sensors 20(20):5780. Mehta et al"
        blob_fix = re.sub(
            r'(:\d+)\s+(?=[A-Z][a-z\-]+\s+[A-Z])',
            r'\1\n',
            blob_fix
        )
        
        lines = blob_fix.split('\n')
        
        initial_refs = []
        buffer = ""
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Deteksi awal referensi baru dengan MULTIPLE dan AGGRESSIVE patterns
            is_new_ref = False
            
            # Pattern 1: [n] bracket style
            if re.match(r'^\[\s*\d+\s*\]', line):
                is_new_ref = True
            # Pattern 2: "1. Author..." numbered style
            elif re.match(r'^\d+\.\s+[A-Z]', line):
                is_new_ref = True
            # Pattern 3: "Smith, J." - Author, Initial style
            elif re.match(r'^[A-Z][a-z\-]+,\s*[A-Z]\.', line):
                is_new_ref = True
            # Pattern 4: "Smith et al." - et al style
            elif re.match(r'^[A-Z][a-z\-]+\s+et\s+al\.', line):
                is_new_ref = True
            # Pattern 5: "Smith and Jones" atau "Smith, J. and Jones, A."
            elif re.match(r'^[A-Z][a-z\-]+(?:\s+(?:and|&|\,))', line):
                is_new_ref = True
            # Pattern 6: Multiple authors "FirstName LastName, FirstName LastName"
            elif re.match(r'^[A-Z][a-z\-]+\s+[A-Z][a-z\-]+\s+[A-Z]', line):
                is_new_ref = True
            # Pattern 7: Year at start (dari split strategy)
            elif re.match(r'^\d{4}[a-z]?[,.\):]', line):
                is_new_ref = True
            else:
                # Default: jika buffer kosong dan line ok, treat sebagai start baru
                if not buffer:
                    is_new_ref = True
            
            if is_new_ref and len(buffer) > 15:
                initial_refs.append({"nomor": None, "teks_referensi": buffer.strip()})
                buffer = line
            else:
                if buffer:
                    buffer += " " + line
                else:
                    buffer = line
                    
        if buffer and len(buffer) > 15:
            initial_refs.append({"nomor": None, "teks_referensi": buffer.strip()})
        
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

def generate_thesis_outline(title: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Menghasilkan Kerangka Skripsi.
    Strategi: Gunakan model yang TERSEDIA di akun user (gemini-pro-latest).
    """
    if not title: return {}

    available_models = [
        'gemini-pro-latest',          
        'gemini-3-flash-preview',     
        'gemini-pro'                  
    ]

    if HAS_GEMINI_LIB and GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        
        for model_name in available_models:
            try:
                clean_model_name = model_name.replace("models/", "")
                logger.info(f"⏳ Mencoba generate outline dengan model: {clean_model_name}...")
                
                model = genai.GenerativeModel(clean_model_name)
                
                # --- PROMPT DISESUAIKAN DENGAN REQUEST USER ---
                prompt = f"""
                Berperanlah sebagai Dosen Pembimbing Tugas Akhir Program Studi Sistem Informasi/Informatika.
                
                Tugas: Buatkan Kerangka Tugas Akhir (Bab 1-3) yang SANGAT SPESIFIK untuk judul: "{title}".
                
                ATURAN KHUSUS BAB 2 (TINJAUAN PUSTAKA):
                1. Pecah teori menjadi sub-bab terpisah (JANGAN digabung, misal "2.1 NLP & Text Mining" itu SALAH. Harusnya "2.1 NLP", "2.2 Text Mining").
                2. Urutkan dari Teori Paling Umum (Grand Theory) ke Teori Paling Khusus (Applied Theory/Metode Spesifik).
                3. Sub-bab TERAKHIR di Bab 2 WAJIB berisi "Penelitian Terdahulu (State of the Art)".
                
                STRUKTUR YANG DIHARAPKAN:
                
                BAB 1: PENDAHULUAN
                1.1 Latar Belakang: Masalah, Data/Gap, Urgensi.
                1.2 Rumusan Masalah: Pertanyaan penelitian.
                1.3 Tujuan Penelitian.
                1.4 Batasan Penelitian: Lingkup dan batasan.
                1.5 Manfaat Penelitian.
                1.6 Sistematika Penulisan.

                BAB 2: TINJAUAN PUSTAKA
                2.1 [Teori Paling Dasar/Umum yang relevan dengan judul]
                2.2 [Teori Menengah/Variabel Utama]
                2.3 [Teori Spesifik/Metode/Algoritma]
                ... (Tambahkan sub-bab sesuai kebutuhan teori) ...
                2.X Penelitian Terdahulu (State of the Art) <- WAJIB DI AKHIR BAB 2

                BAB 3: METODE PENYELESAIAN MASALAH
                3.1 Metode Penelitian: Alasan pemilihan metode.
                3.2 Sistematika Penyelesaian Masalah: Langkah-langkah/Flowchart.
                3.3 Metode Pengumpulan & Pengolahan Data.
                3.4 Metode Evaluasi: Cara ukur keberhasilan.

                OUTPUT HARUS FORMAT JSON MURNI (Tanpa Markdown):
                {{
                    "BAB 1: Pendahuluan": [
                        {{"sub": "1.1 Latar Belakang", "guide": "..."}},
                        {{"sub": "1.2 Rumusan Masalah", "guide": "..."}},
                        {{"sub": "1.3 Tujuan Penelitian", "guide": "..."}},
                        {{"sub": "1.4 Batasan Penelitian", "guide": "..."}},
                        {{"sub": "1.5 Manfaat Penelitian", "guide": "..."}},
                        {{"sub": "1.6 Sistematika Penulisan", "guide": "..."}}
                    ],
                    "BAB 2: Tinjauan Pustaka": [
                        {{"sub": "2.1 [Nama Teori Umum]", "guide": "Jelaskan konsep dasar..."}},
                        {{"sub": "2.2 [Nama Teori Lanjutan]", "guide": "Jelaskan kaitan dengan objek..."}},
                        {{"sub": "2.3 [Nama Algoritma/Metode]", "guide": "Jelaskan cara kerja teknis..."}},
                        {{"sub": "2.4 Penelitian Terdahulu (State of The Art)", "guide": "Bandingkan dengan penelitian sejenis..."}}
                    ],
                    "BAB 3: Metode Penyelesaian Masalah": [
                        {{"sub": "3.1 Metode Penelitian", "guide": "..."}},
                        {{"sub": "3.2 Sistematika Penyelesaian Masalah", "guide": "..."}},
                        {{"sub": "3.3 Metode Pengumpulan & Pengolahan Data", "guide": "..."}},
                        {{"sub": "3.4 Metode Evaluasi", "guide": "..."}}
                    ]
                }}
                """
                
                response = model.generate_content(prompt)
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                result = json.loads(clean_json)
                
                logger.info(f"✅ Outline berhasil dibuat dengan {clean_model_name}!")
                return result

            except Exception as e:
                logger.warning(f"⚠️ Gagal dengan {model_name}: {e}. Mencoba model berikutnya...")
                continue
    
    # --- FALLBACK MANUAL ---
    logger.warning("❌ Semua AI gagal. Menggunakan template manual.")
    
    title_lower = title.lower()
    # Deteksi teori kasar untuk fallback
    teori_umum = "Teori Sistem Informasi"
    teori_khusus = "Metode Pengembangan"
    
    if "sistem pakar" in title_lower: 
        teori_umum = "Kecerdasan Buatan"
        teori_khusus = "Sistem Pakar"
    elif "data mining" in title_lower:
        teori_umum = "Knowledge Discovery in Database (KDD)"
        teori_khusus = "Data Mining"

    return {
        "BAB 1: Pendahuluan": [
            {"sub": "1.1 Latar Belakang", "guide": "Deskripsikan gap masalah."},
            {"sub": "1.2 Rumusan Masalah", "guide": "Pertanyaan penelitian."},
            {"sub": "1.3 Tujuan Penelitian", "guide": "Sasaran penelitian."},
            {"sub": "1.4 Batasan Penelitian", "guide": "Ruang lingkup."},
            {"sub": "1.5 Manfaat Penelitian", "guide": "Kontribusi."},
            {"sub": "1.6 Sistematika Penulisan", "guide": "Ringkasan bab."}
        ],
        "BAB 2: Tinjauan Pustaka": [
            {"sub": f"2.1 {teori_umum}", "guide": "Teori grand/dasar."},
            {"sub": f"2.2 {teori_khusus}", "guide": "Teori spesifik topik."},
            {"sub": "2.3 Penelitian Terdahulu", "guide": "State of the art."}
        ],
        "BAB 3: Metode Penyelesaian Masalah": [
            {"sub": "3.1 Metode Penelitian", "guide": "Justifikasi metode."},
            {"sub": "3.2 Sistematika Penyelesaian Masalah", "guide": "Tahapan sistematis."},
            {"sub": "3.3 Metode Pengumpulan & Pengolahan Data", "guide": "Sumber data & teknik."},
            {"sub": "3.4 Metode Evaluasi", "guide": "Metrik pengukuran."}
        ]
    }

# --- Init Functions ---
def initialize_keybert_model(): 
    try: return KeyBERT(model='paraphrase-multilingual-MiniLM-L12-v2')
    except: return None

def initialize_summarizer(): 
    try: return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=DEVICE)
    except: return None

def initialize_embedding_model(): 
    return SentenceTransformer('all-MiniLM-L6-v2', device='cuda' if DEVICE == 0 else 'cpu')