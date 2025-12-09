"""
Custom NLP Service - High Performance & Clean Output
Optimized with PyMuPDF (Speed) and Line-Based Cleaning (Quality)
"""

import fitz  # PyMuPDF (Wajib: pip install pymupdf)
import docx
import os
import re
import numpy as np
from keybert import KeyBERT
from transformers import pipeline
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# --- Global Settings ---
MAX_CHARS_FOR_MODEL = 3500 
SIMILARITY_THRESHOLD = 0.50

# Force CPU (Lebih stabil untuk Docker Laptop)
DEVICE = -1 
DEVICE_NAME = "CPU"
logger.info(f"💡 NLP Service running on: {DEVICE_NAME}")

def fix_common_artifacts(text: str) -> str:
    """
    Perbaikan artefak teks, TERUTAMA Hyphenation, Ligatures, dan Page Numbers.
    """
    # 1. FIX LIGATURES
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('ﬀ', 'ff').replace('ﬃ', 'ffi')

    # 2. Hapus Nomor Halaman yang berdiri sendiri di baris baru (Artifact PDF)
    # Menghapus baris yang isinya CUMA angka (1, 2, 3.. 10..)
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
    
    # 3. De-hyphenation lintas baris
    text = re.sub(r'([a-zA-Z])-\s*\n\s*([a-zA-Z])', r'\1\2', text)
    text = re.sub(r'([a-zA-Z])-\s+([a-zA-Z])', r'\1\2', text)

    # 4. Fix scientific notation
    text = re.sub(r'(\d+)\s?e\s?(\d+)', r'\1-\2', text)
    
    # 5. Hapus artefak CID
    text = re.sub(r'\(cid:\d+\)', '', text)

    # 6. Hapus Copyright & License Footer
    text = re.sub(r'©\s*\d{4}\s*(?:IEEE|ACM|Springer|Elsevier)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Authorized licensed use limited to:.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:ISBN|ISSN|Part Number):\s*[\d-]+\s*', '', text, flags=re.IGNORECASE)
    
    # 7. Fix spasi baca
    text = re.sub(r'\s+([.,;:])', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def clean_text_lines(text: str) -> str:
    """"Membersihkan baris sampah (Header/Footer/Metadata Jurnal)."""
    lines = text.split('\n')
    cleaned_lines = []
    
    # Pola yang menandakan baris itu adalah Sampah Metadata
    trash_markers = [
        r'journal of', r'vol\.', r'no\.', r'pp\.', r'doi:', 
        r'accepted', r'received', r'published', r'copyright', 
        r'all rights reserved', r'https?://', r'www\.',
        r'correspondence', r'email:', r'department of', 
        r'university of', r'faculty of', r'school of',
        r'institute of', r'ph\.?d', r'm\.?d', r'm\.?sc', r'frontiers', r'proceedings of',
        r'downloaded from', r'access provided by',
        r'ieee xplore', r'part number', r'isbn:', r'authorized licensed use'
        r'\(cid:\d+\)', # CID artifacts
        r'^\d{4}$', # Tahun doang
        r'^page \d+', # Nomor halaman
    ]
    
    for line in lines:
        line_clean = line.strip()
        if len(line_clean) < 3: continue # Skip baris terlalu pendek
        
        # Cek apakah baris mengandung marker sampah
        is_trash = False
        for marker in trash_markers:
            if re.search(marker, line_clean, re.IGNORECASE):
                is_trash = True
                break
        
        if not is_trash:
            cleaned_lines.append(line_clean)
            
    return "\n".join(cleaned_lines)

def locate_intro_or_abstract(text: str) -> str:
    """
    Mencari posisi Introduction atau Abstract untuk memulai ringkasan.
    """
    match_intro = re.search(r'(?:^|\n)(?:\d+\.|I\.|)\s*Introduction', text, re.IGNORECASE)
    
    if match_intro:
        # Ambil teks mulai dari Introduction
        return text[match_intro.start():]
    
    # Jika tidak ada, cari Abstract
    match_abst = re.search(r'(?:^|\n)Abstract', text, re.IGNORECASE)
    if match_abst:
        return text[match_abst.start():]
        
    return text

def extract_research_gap_sections(text: str) -> Dict[str, str]:
    """
    Ekstraksi Limitations & Future Work dengan logika Fallback yang cerdas.
    """
    # Langkah 1: Bersihkan Hyphenation dulu sebelum diproses regex
    text_clean = fix_common_artifacts(text)
    
    extracted = {"limitations": "", "future_work": ""}

    # --- DEFINISI REGEX HEADER ---
    # Header Prefix: Bisa diawali angka (5.), newline, atau spasi
    h_pre = r'(?:^|\n|\.\s+)\s*(?:\d+(?:\.\d+)*\.?)?\s*'

    limit_patterns = [
        # Menangkap "Limitations", "Limitations and Challenges", "5. Limitations"
        h_pre + r'(?:Limitations?|Weaknesses?|Keterbatasan)(?:\s+(?:and|&)\s+(?:Challenges?|Future|Directions?))?(?:\s*[:.])?\s*(?=\n|[A-Z])',
        h_pre + r'(?:Challenges?|Issues?)(?:\s*[:.])?\s*(?=\n|[A-Z])'
    ]

    # 2. FUTURE WORK HEADERS
    future_patterns = [
        h_pre + r'(?:Future\s+Works?|Future\s+Research|Directions?|Suggestions?|Saran)(?:\s*[:.])?\s*(?=\n|[A-Z])'
    ]

    # 3. CONCLUSION HEADERS (Fallback)
    conclusion_patterns = [
        h_pre + r'(?:Conclusion|Conclusions|Concluding Remarks|Discussion|Summary|Kesimpulan)(?:\s*[:.])?\s*(?=\n|[A-Z])'
    ]

    # Stop Markers: Berhenti jika ketemu bab lain atau Referensi
    stop_markers = [
        r'(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?)?\s*(?:References|Daftar Pustaka|Bibliography|Acknowledgement|Data Availability|Ethics|Funding|Author Contribution)',
        r'(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?)?\s*(?:Conclusion|Future Work|Limitations?)',
        r'http[s]?://'
    ]
    stop_regex = "|".join(stop_markers)
    
    def clean_technical_sentences(raw_text, type="general"):
        if not raw_text: return ""
        
        # Pecah kalimat
        sentences = re.split(r'(?<=[.!?])\s+', raw_text)
        cleaned_sentences = []
        
        # Kata-kata teknis yang HARUS DIBUANG (Noise)
        blacklist = [
            'hyperparameter', 'epoch', 'softmax', 'relu', 'layer', 'convolution', 
            'training data', 'validation set', 'accuracy', 'f1 score', 'precision', 
            'recall', 'table', 'figure', 'shown in', 'we use', 'we utilized',
            'state-of-the-art', 'baseline', 'outperform', 'github', 'code is available'
        ]
        
        # Kata-kata emas (Wajib ada/disimpan)
        whitelist_limit = ['limit', 'lack', 'issue', 'problem', 'constraint', 'fail', 'weakness', 'scarcity', 'sparse', 'unable', 'challenge', 'difficult']
        whitelist_future = ['future', 'intend', 'plan', 'propose', 'suggest', 'recommend', 'extend', 'explore', 'hope', 'next step']

        for s in sentences:
            s_lower = s.lower()
            
            # Jika kalimat terlalu pendek, skip
            if len(s) < 20: continue
            
            # Cek Blacklist (Metodologi/Teknis)
            is_technical = any(word in s_lower for word in blacklist)
            
            # Cek Whitelist
            is_limit_relevant = any(word in s_lower for word in whitelist_limit)
            is_future_relevant = any(word in s_lower for word in whitelist_future)
            
            # ATURAN PENYARINGAN:
            # 1. Jika ini Future Work Section: Ambil kalimat yang mengandung unsur future.
            # 2. Jika ini Limitation Section: Ambil kalimat yang mengandung unsur limitasi.
            # 3. Jika kalimat mengandung blacklist TAPI juga mengandung whitelist (misal: "The accuracy is limited by..."), AMBIL.
            # 4. Jika kalimat murni teknis (hanya blacklist), BUANG.
            
            keep = False
            if type == "limit" and is_limit_relevant: keep = True
            elif type == "future" and is_future_relevant: keep = True
            elif type == "general":
                if is_limit_relevant or is_future_relevant: keep = True
            
            # Exception: Jika ada blacklist tapi tidak ada whitelist, buang.
            if is_technical and not (is_limit_relevant or is_future_relevant):
                keep = False

            if keep:
                cleaned_sentences.append(s)

        # Ambil maksimal 5-6 kalimat terbaik agar tidak kepanjangan
        return " ".join(cleaned_sentences[:6])

    def get_chunk(patterns, section_type, avoid_self=False):
        for pat in patterns:
            match = re.search(pat, text_clean, re.IGNORECASE)
            if match:
                start = match.end()
                chunk = text_clean[start : start + 3500]
                
                # Stop marker logic
                stop_match = re.search(stop_regex, chunk[50:], re.IGNORECASE)
                if stop_match:
                    chunk = chunk[:stop_match.start() + 50]
                
                # Filter kalimat teknis
                return clean_technical_sentences(chunk.strip(), section_type)
        return ""
    
    # --- EKSEKUSI ---
    extracted["limitations"] = get_chunk(limit_patterns, "limit")
    extracted["future_work"] = get_chunk(future_patterns, "future")
    
    # --- FALLBACK TO CONCLUSION ---
    if not extracted["limitations"] or not extracted["future_work"]:
        conclusion_text = get_chunk(conclusion_patterns, "general", avoid_self=True)
        if conclusion_text:
            # Jika Conclusion mengandung kalimat limitasi/future, masukkan
            # Kita panggil ulang filter untuk memisahkan
            if not extracted["limitations"]:
                extracted["limitations"] = clean_technical_sentences(conclusion_text, "limit")
            if not extracted["future_work"]:
                extracted["future_work"] = clean_technical_sentences(conclusion_text, "future")

    return extracted

def clean_and_locate_content(text: str) -> str:
    """Membersihkan header dan mencari konten inti untuk ringkasan."""
    if not text: return ""

    text = fix_common_artifacts(text)

    # Regex untuk membuang Header/Metadata
    metadata_patterns = [
        r'Journal of.*?\d{4}',           
        r'Accepted.*?20\d{2}',           
        r'Received.*?20\d{2}',           
        r'Vol\.\s?\d+',                  
        r'doi:.*?10\.',
        r'arXiv:[\d\.]+',
        r'©.*?20\d{2}',
        r'All rights reserved',
        r'Page \d+ of \d+',
        r'Corresponding author',
        r'The Thirty-Fourth AAAI Conference', 
        r'International Conference on',
        r'Proceedings of',
        r'https?://\S+',
        r'^\d{4}.*?$', 
    ]
    
    for pattern in metadata_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)

    text = re.sub(r'(Department|School|Faculty|University|Institute).*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'-\n', '', text)
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Cari Introduction atau Abstract untuk ringkasan
    # (Kita pakai teks aslinya untuk ekstraksi referensi nanti)
    relevant_text = text 
    intro_match = re.search(r'(?:1\.?|I\.?)?\s*Introduction.{20}', text, re.IGNORECASE)
    if intro_match:
        return text[intro_match.start():]
    
    abst_match = re.search(r'Abstract.{20}', text, re.IGNORECASE)
    if abst_match:
        return text[abst_match.start():]
            
    return relevant_text

# --- Extraction ---
def extract_text_from_pdf(file_path: str) -> Optional[str]:
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"⚠️ Failed to process PDF {os.path.basename(file_path)}: {e}")
        return None

def extract_text_from_docx(file_path: str) -> Optional[str]:
    try:
        doc = docx.Document(file_path)
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        return " ".join(paragraphs)
    except Exception as e:
        logger.error(f"⚠️ Failed to process DOCX {os.path.basename(file_path)}: {e}")
        return None
    
def find_end_of_references(text: str) -> str:
    """
    Memotong teks agar berhenti TEPAT setelah Daftar Pustaka selesai.
    Mendeteksi Appendix, Data Samples, atau Judul Bab Baru.
    """
    # Pola Header yang menandakan akhir dari References
    # Kita cari pola Judul Bab yang biasanya Huruf Besar Awal atau All Caps di awal baris
    end_markers = [
        r'(?:^|\n)\s*(?:Appendix|APPENDICES)', 
        r'(?:^|\n)\s*(?:A\s+|B\s+|C\s+)?(?:Data Samples|DATA SAMPLES)', # Case spesifik paper Anda
        r'(?:^|\n)\s*(?:Supplemental|SUPPLEMENTAL)',
        r'(?:^|\n)\s*(?:About the Author)',
        r'(?:^|\n)\s*(?:Table \d+)', # Jika tabel besar muncul setelah referensi
        r'(?:^|\n)\s*(?:Figure \d+)',
    ]
    
    cutoff_index = len(text)
    
    for marker in end_markers:
        match = re.search(marker, text) # Case-sensitive agar tidak salah tangkap kata biasa
        if match:
            # Ambil indeks yang paling awal ketemu
            cutoff_index = min(cutoff_index, match.start())
            
    return text[:cutoff_index]
    
def extract_references(full_text: str) -> List[Dict[str, str]]:
    if not full_text: return []
    
    # 1. Gunakan clean_text_lines agar newline terjaga
    text_clean = clean_text_lines(full_text)
    # 2. Hapus nomor halaman yang nyasar di tengah (1, 2, 3...)
    text_clean = re.sub(r'\n\s*\d+\s*\n', '\n', text_clean)
    
    # 3. Cari Header Referensi
    pattern = re.compile(r'(?:^|\n)\s*(\d+\.?\s*)?(REFERENCES|DAFTAR PUSTAKA|BIBLIOGRAPHY)', re.IGNORECASE)
    match = pattern.search(text_clean)
    
    if not match:
        start_search = int(len(text_clean) * 0.6)
        match_fallback = re.search(r'(References|Daftar Pustaka)', text_clean[start_search:], re.IGNORECASE)
        if match_fallback: 
            text_after = text_clean[start_search + match_fallback.end():].strip()
        else: 
            return []
    else:
        text_after = text_clean[match.end():].strip()

    # 4. Potong Ekor (Appendix/Data Samples)
    text_after = find_end_of_references(text_after)

    # 5. Deteksi Style: Bernomor atau Tidak?
    sample_chunk = text_after[:1000]
    has_brackets = re.search(r'\[\d+\]', sample_chunk)
    has_numbered_dots = re.search(r'(?:^|\n)\s*\d+\.\s+[A-Z]', sample_chunk)
    
    raw_refs = []

    # STYLE A: Bernomor ([1] atau 1.)
    if has_brackets or has_numbered_dots:
        split_pattern = r'(?=(?:^|\n)\s*(?:\[\d+\]|\d+\.\s))'
        if has_brackets and not re.search(r'^\[\d+\]', text_after):
            text_after = "[1] " + text_after
        elif has_numbered_dots and not re.search(r'^\d+\.', text_after):
             text_after = "1. " + text_after
        
        # Flatten newline untuk regex split
        text_flat = re.sub(r'\n', ' ', text_after)
        raw_refs = re.split(split_pattern, text_flat)

    # STYLE B: Author-Year (Tanpa Nomor)
    else:
        lines = text_after.split('\n')
        current_ref = ""
        
        # Regex Awal Referensi Baru (Penting!)
        # Kriteria:
        # 1. Dimulai Huruf Besar (Nama Belakang)
        # 2. Diikuti koma atau " and "
        # 3. Mengandung Tahun (19xx atau 20xx) di baris yang sama ATAU baris berikutnya
        # 4. Panjang minimal 10 karakter
        
        for i, line in enumerate(lines):
            line = line.strip()
            if len(line) < 5: continue
            
            # Cek apakah ini awal referensi baru?
            # Pola: Dimulai huruf besar, tidak diawali spasi kecil (indikasi paragraf nyambung)
            # Dan mengandung tahun dalam kurung atau di akhir kalimat
            is_start = False
            
            # Pola Nama: "Conneau, A." atau "Devlin et al."
            starts_with_name = re.match(r'^[A-Z][a-zA-Z\-\u00C0-\u00FF]+(?:, | and | et al\.)', line)
            has_year = re.search(r'(?:19|20)\d{2}', line)
            
            if starts_with_name and has_year:
                is_start = True
            
            if is_start:
                if current_ref:
                    raw_refs.append(current_ref)
                current_ref = line
            else:
                # Jika tidak terdeteksi sebagai awal, gabung ke sebelumnya
                if current_ref:
                    current_ref += " " + line
                else:
                    current_ref = line # Baris pertama banget
        
        if current_ref:
            raw_refs.append(current_ref)

    # 6. Formatting
    formatted = []
    counter = 1
    
    for r in raw_refs:
        r = r.strip()
        if len(r) < 15: continue # Filter sampah pendek
        
        # Hapus nomor di depan jika ada
        r_clean = re.sub(r'^(?:\[\d+\]|\d+\.)\s*', '', r)
        r_clean = fix_common_artifacts(r_clean)
        
        # Validasi Tahun (Wajib ada tahun 19xx atau 20xx untuk dianggap referensi valid)
        if not re.search(r'(19|20)\d{2}', r_clean):
            continue

        formatted.append({"nomor": str(counter), "teks_referensi": r_clean})
        counter += 1
        
    return formatted[:50]

# --- NLP Functions ---
def extract_keywords_bert(text: str, kw_model_instance: KeyBERT, top_n: int = 10) -> List[str]:
    if not text or len(text.strip()) < 50: return []
    try:
        clean = clean_text_lines(text)
        clean = fix_common_artifacts(clean)
        target = locate_intro_or_abstract(clean)[:MAX_CHARS_FOR_MODEL]
        keywords = kw_model_instance.extract_keywords(
            target, keyphrase_ngram_range=(1, 2), stop_words='english',
            use_maxsum=True, nr_candidates=20, top_n=top_n
        )
        return [kw for kw, s in keywords if len(kw) > 3 and not kw.isdigit()]
    except Exception as e:
        logger.error(f"KeyBERT error: {e}")
        return []

def generate_summary_bart(text: str, summarizer_instance) -> str:
    """Generate Summary (Optimized for Speed & Insight)."""
    if not text or len(text.strip()) < 100: return "Text too short."
    try:
        clean_text = clean_text_lines(text)
        target_text = locate_intro_or_abstract(clean_text)
        input_text = target_text[:MAX_CHARS_FOR_MODEL]
        summary = summarizer_instance(
            input_text, max_length=200, min_length=60, 
            num_beams=1, do_sample=False, no_repeat_ngram_size=3
        )
        return fix_common_artifacts(summary[0]['summary_text'])
    except Exception as e:
        logger.warning(f"⚠️ Summary failed: {e}")
        return "Failed to generate summary."

def generate_embeddings(text: str, model: SentenceTransformer) -> Optional[np.ndarray]:
    if not text or len(text.strip()) < 50: return None
    try:
        clean = fix_common_artifacts(text)
        target = locate_intro_or_abstract(clean)[:MAX_CHARS_FOR_MODEL]
        return model.encode(target, convert_to_numpy=True)
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None

def calculate_similarity_matrix(embeddings: List[np.ndarray]) -> np.ndarray:
    if len(embeddings) < 2: raise ValueError("Need >1 embeddings")
    return cosine_similarity(np.array(embeddings))


def build_graph_data(
    filenames: List[str], 
    similarity_matrix: np.ndarray, 
    threshold: float = SIMILARITY_THRESHOLD
) -> Dict:
    """
    Build graph data structure for visualization from similarity matrix.
    """
    nodes = []
    edges = []
    
    for i in range(len(filenames)):
        fname_i = filenames[i]
        nodes.append({
            "id": fname_i,
            "label": fname_i[:25] + "..." if len(fname_i) > 25 else fname_i
        })
        
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


## --- Init Functions ---
def initialize_keybert_model(): return KeyBERT(model='all-MiniLM-L6-v2')
def initialize_summarizer(): return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=DEVICE)
def initialize_embedding_model(): return SentenceTransformer('all-MiniLM-L6-v2', device='cuda' if DEVICE == 0 else 'cpu')