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

def clean_text_lines(text: str) -> str:
    """
    Membersihkan teks dengan memfilter baris per baris.
    Sangat efektif membuang Header/Footer/Metadata.
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    # Pola yang menandakan baris itu adalah Sampah Metadata
    trash_markers = [
        r'journal of', r'vol\.', r'no\.', r'pp\.', r'doi:', 
        r'accepted', r'received', r'published', r'copyright', 
        r'all rights reserved', r'https?://', r'www\.',
        r'correspondence', r'email:', r'department of', 
        r'university of', r'faculty of', r'school of',
        r'institute of', r'ph\.?d', r'm\.?d', r'm\.?sc',
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
            
    return " ".join(cleaned_lines)

def locate_intro_or_abstract(text: str) -> str:
    """
    Mencari posisi Introduction atau Abstract untuk memulai ringkasan.
    """
    # Coba cari Introduction dulu (Isi paling daging)
    # Regex menangkap "1. Introduction" atau "I. Introduction" atau "Introduction"
    match_intro = re.search(r'(?:^|\n)(?:\d+\.|I\.|)\s*Introduction', text, re.IGNORECASE)
    
    if match_intro:
        # Ambil teks mulai dari Introduction
        return text[match_intro.start():]
    
    # Jika tidak ada, cari Abstract
    match_abst = re.search(r'(?:^|\n)Abstract', text, re.IGNORECASE)
    if match_abst:
        return text[match_abst.start():]
        
    return text # Fallback: pakai semua teks yang sudah dibersihkan

def fix_common_artifacts(text: str) -> str:
    """Perbaikan kosmetik akhir."""
    text = re.sub(r'(\d+)\s?e\s?(\d+)', r'\1-\2', text) # 16e18 -> 16-18
    text = re.sub(r'\s+([.,;:])', r'\1', text) # Spasi sebelum titik
    text = re.sub(r'([.,;:])([a-zA-Z])', r'\1 \2', text) # Spasi setelah titik
    text = text.replace('', '')
    text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text) # Hapus sitasi angka [12]
    text = text.replace('ClassiRAcation', 'Classification')
    text = "".join(ch for ch in text if ch.isprintable() or ch in ['\n', '\t', '\r'])
    return text.strip()

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
    """
    Ekstraksi Cepat dengan PyMuPDF.
    Membaca SELURUH halaman agar referensi di akhir terbaca.
    """
    text = ""
    try:
        doc = fitz.open(file_path)
        # Loop semua halaman tanpa batas (agar daftar pustaka di akhir kena)
        for page in doc:
            # get_text() default sudah cukup baik dan sangat cepat
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


# --- NLP Functions ---
def extract_keywords_bert(text: str, kw_model_instance: KeyBERT, top_n: int = 10, ngram_range: Tuple[int, int] = (1, 2)) -> List[str]:
    if not text or len(text.strip()) < 50: return []
    try:
        # Bersihkan dulu sebelum ekstraksi keyword
        clean_text = clean_text_lines(text)
        target_text = locate_intro_or_abstract(clean_text)[:MAX_CHARS_FOR_MODEL]
        
        keywords = kw_model_instance.extract_keywords(
            target_text,
            keyphrase_ngram_range=ngram_range,
            stop_words='english',
            use_maxsum=True, nr_candidates=20, top_n=top_n
        )
        return [kw for kw, s in keywords if len(kw) > 3 and not kw.isdigit()]
    except Exception as e:
        logger.error(f"❌ Error KeyBERT: {e}")
        return []


def generate_summary_bart(text: str, summarizer_instance) -> str:
    """
    Generate Summary (Optimized for Speed & Insight).
    """
    if not text or len(text.strip()) < 100: return "Text too short."
    
    try:
        # 1. Cleaning (Line Filter)
        clean_text = clean_text_lines(text)
        
        # 2. Locating (Intro First)
        target_text = locate_intro_or_abstract(clean_text)
        
        # 3. Truncate (Biar memori aman)
        input_text = target_text[:MAX_CHARS_FOR_MODEL]

        # 4. Generate (SPEED OPTIMIZED)
        summary = summarizer_instance(
            input_text, 
            max_length=200,
            min_length=60,
            # SETTINGAN KECEPATAN:
            num_beams=1,       # Greedy Search (Paling Cepat)
            do_sample=False,   # Deterministik (Cepat & Stabil)
            no_repeat_ngram_size=3 # Cegah pengulangan kata
        )
        final_summary = summary[0]['summary_text']
    
    except Exception as e:
        logger.warning(f"⚠️ Summary failed: {e}")
        return "Failed to generate summary."

    return fix_common_artifacts(final_summary)


def extract_references(full_text: str) -> List[Dict[str, str]]:
    """
    Mengekstrak daftar referensi dari teks lengkap dengan deteksi [Nomor] yang kuat.
    Menggunakan lookahead regex untuk memisahkan setiap referensi secara akurat,
    mencegah beberapa referensi bergabung menjadi satu.
    """
    if not full_text:
        return []

    # 1. Normalisasi Teks
    # Standarkan newline dan hapus newline berlebih
    normalized_text = re.sub(r'\r\n', '\n', full_text)
    normalized_text = re.sub(r'\n+', '\n', normalized_text)

    # 2. Cari Header Referensi
    # Pattern mencari "REFERENCES", "DAFTAR PUSTAKA", dll. di awal baris atau setelah newline
    header_pattern = re.compile(r'(?:^|\n)\s*(\d+\.?\s*)?(REFERENCES|DAFTAR PUSTAKA|BIBLIOGRAPHY|Literature Cited)\s*(?:\n|$)', re.IGNORECASE)
    match = header_pattern.search(normalized_text)
    
    text_after = ""
    # Jika header tidak ketemu di awal baris, coba cari di 30% akhir dokumen sebagai fallback
    if not match:
        start_search = int(len(normalized_text) * 0.7)
        last_part = normalized_text[start_search:]
        # Cari kata kunci di bagian akhir tanpa harus di awal baris yang ketat
        match_fallback = re.search(r'(References|Daftar Pustaka|Bibliography)', last_part, re.IGNORECASE)
        if match_fallback:
            # Ambil teks setelah header fallback ditemukan
            text_after = last_part[match_fallback.end():].strip()
            logger.info("⚠️ Reference header not found at start of lines, used fallback search in last 30%.")
        else:
            logger.warning("⚠️ No reference section header found. Cannot extract references.")
            return []
    else:
        # Ambil teks setelah header ditemukan
        text_after = normalized_text[match.end():].strip()

    if not text_after:
        logger.warning("⚠️ Reference section header found, but no text follows it.")
        return []

    # 3. Pisahkan per Referensi menggunakan Regex Lookahead (INTI PERBAIKAN)
    # `(?=...)` adalah positive lookahead. `\[\d+\]` cocok dengan format [1], [12], dll.
    # Regex ini akan memotong teks tepat PADA POSISI SEBELUM setiap pola `[Angka]` dimulai.
    # Ini menjamin bahwa teks di antara dua potongan adalah satu referensi utuh.
    split_pattern = r'(?=\[\d+\])'
    raw_references = re.split(split_pattern, text_after)

    formatted_refs = []
    ref_counter = 1

    for raw_ref in raw_references:
        # Bersihkan whitespace di awal/akhir
        clean_ref_text = raw_ref.strip()
        
        # Abaikan string kosong atau yang terlalu pendek (biasanya sampah sebelum [1])
        if not clean_ref_text or len(clean_ref_text) < 10:
            continue
            
        # Validasi: Pastikan blok ini benar-benar dimulai dengan [Nomor]
        # Ini penting untuk memastikan kita hanya mengambil blok referensi yang valid.
        if not re.match(r'^\[\d+\]', clean_ref_text):
             continue

        # Hapus nomor referensi asli dari teksnya agar bersih
        # Contoh: mengubah "[14] Penulis..." menjadi "Penulis..."
        final_ref_text = re.sub(r'^\[\d+\]\s*', '', clean_ref_text).strip()

        # Gabungkan kembali baris-baris yang terputus dalam satu referensi menjadi satu baris rapi
        final_ref_text = re.sub(r'\n', ' ', final_ref_text)
        # Hapus spasi berlebih yang mungkin muncul akibat penggabungan baris
        final_ref_text = re.sub(r'\s+', ' ', final_ref_text).strip()

        if final_ref_text:
            formatted_refs.append({
                # Gunakan counter kita sendiri untuk nomor urut yang rapi di output
                "nomor": str(ref_counter), 
                "teks_referensi": final_ref_text
            })
            ref_counter += 1

    logger.info(f"📚 Successfully extracted {len(formatted_refs)} references using split pattern '{split_pattern}'.")
    # Kembalikan 50 referensi pertama (atau sesuaikan kebutuhan batas maksimum)
    return formatted_refs[:50]


def generate_embeddings(text: str, embedding_model_instance: SentenceTransformer) -> Optional[np.ndarray]:
    if not text or len(text.strip()) < 50: return None
    try:
        # Bersihkan dikit biar embedding lebih akurat ke konten
        clean_text = clean_text_lines(text)
        target_text = locate_intro_or_abstract(clean_text)[:MAX_CHARS_FOR_MODEL]
        return embedding_model_instance.encode(target_text, convert_to_numpy=True)
    except Exception as e:
        logger.error(f"❌ Error Embedding: {e}")
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