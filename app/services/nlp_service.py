from typing import List, Dict, Optional
from app.core.config import settings
import logging
import numpy as np
import hashlib
import re
import json
import google.generativeai as genai
from PyPDF2 import PdfReader
from docx import Document

logger = logging.getLogger(__name__)

# Configure Gemini API
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

# Global Settings
MAX_CHARS_FOR_MODEL = 12000

class NLPService:
    def __init__(self):
        """Initialize NLP Service"""
        logger.info("Initializing NLP Service with Gemini API...")
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.embeddings_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info("✅ NLP Service initialized (Gemini API)")
    
    def _get_text_hash(self, text: str) -> str:
        """Generate hash for caching"""
        return hashlib.md5(text[:500].encode()).hexdigest()
    
    def _clean_text_lines(self, text: str) -> str:
        """Basic text cleaning"""
        lines = text.split('\n')
        cleaned_lines = []
        
        trash_markers = [
            r'journal of', r'vol\.', r'no\.', r'pp\.', r'doi:', 
            r'accepted', r'received', r'published', r'copyright'
        ]
        
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) < 3:
                continue
            
            is_trash = any(re.search(marker, line_clean, re.IGNORECASE) for marker in trash_markers)
            if not is_trash:
                cleaned_lines.append(line_clean)
        
        return "\n".join(cleaned_lines)
    
    def _fix_common_artifacts(self, text: str) -> str:
        """Fix common PDF artifacts"""
        text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
        text = re.sub(r'([a-zA-Z])-\s*\n\s*([a-zA-Z])', r'\1\2', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    async def extract_keywords(self, text: str, num_keywords: int = 10) -> List[str]:
        """Extract keywords using Gemini API"""
        logger.info(f"Extracting {num_keywords} keywords from text of length {len(text)}")
        try:
            prompt = f"""Extract {num_keywords} most important keywords from this text. 
Return only the keywords as a comma-separated list, no numbering or explanation.

Text:
{text[:2000]}"""
            
            response = self.model.generate_content(prompt)
            keywords = [kw.strip() for kw in response.text.split(',')]
            logger.info(f"Extracted {len(keywords)} keywords")
            return keywords[:num_keywords]
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    async def generate_gap_matrix(self, docs_data: list, lang: str = "id") -> dict:
        """
        Versi 4.0: Force Output Strength & Limitation.
        """
        import json
        import re

        context_text = ""
        for i, doc in enumerate(docs_data):
            safe_text = doc['text'].replace('\n', ' ')[:3000]
            db_auth = doc.get('author', 'Unknown')
            hint_auth = f"(Database: {db_auth})" if db_auth != 'Unknown Author' else "(Database: Unknown, please detect)"
            context_text += f"\n--- PAPER_{i} ---\n{hint_auth}\nIsi Teks: {safe_text}...\n"

        prompt = f"""
        Peran: Akademisi Senior. Tugas: Systematic Literature Review.
        Bahasa Output: {lang}
        
        INSTRUKSI KHUSUS (WAJIB PATUH):
        1. Kolom 'method': Isi dengan algoritma/framework inti.
        2. Kolom 'strength': WAJIB DIISI. Cari kontribusi utama, akurasi tinggi, atau kebaruan ide. JANGAN PERNAH KOSONGKAN INI. Jika tidak ada, tulis "Kontribusi pada [topik paper]".
        3. Kolom 'limitation': Kekurangan metodologi atau batasan data.
        4. Sintesis Gap: Gunakan tag <br/><br/> untuk ganti paragraf. Gunakan **teks tebal** untuk poin kunci.

        FORMAT OUTPUT JSON:
        {{
            "matrix": [
                {{
                    "index": 0, 
                    "detected_citation": "Nama Penulis (Tahun)", 
                    "method": "...",
                    "strength": "...",
                    "limitation": "..."
                }}
            ],
            "synthesis": {{
                "gap": "Paragraf 1... <br/><br/> Paragraf 2...",
                "recommendation": "..."
            }}
        }}

        DATA PAPER:
        {context_text}
        """

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text
            
            # Cleaning JSON Markdown
            clean_text = re.sub(r'```json\s*', '', raw_text)
            clean_text = re.sub(r'```\s*', '', clean_text)
            clean_text = clean_text.strip()
            
            start_idx = clean_text.find('{')
            end_idx = clean_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                clean_text = clean_text[start_idx : end_idx + 1]
            
            ai_result = json.loads(clean_text)

            final_matrix = []
            ai_matrix_map = {item.get('index', i): item for i, item in enumerate(ai_result.get('matrix', []))}

            for i, doc in enumerate(docs_data):
                ai_data = ai_matrix_map.get(i, {})
                
                # Logic Author
                db_author = doc.get('author', 'Unknown Author')
                db_year = doc.get('year', 'n.d.')
                final_citation = f"{db_author} ({db_year})"
                
                if "Unknown" in str(db_author) or not db_author:
                    detected = ai_data.get('detected_citation', 'Unknown Author')
                    if len(detected.split()) < 10: 
                        final_citation = detected
                    else:
                        final_citation = "Unknown (Manual Upload)"

                final_matrix.append({
                    "title": doc['title'],
                    "display_author": final_citation,
                    "method": ai_data.get('method', '-'),
                    "strength": ai_data.get('strength', '-'), # Pastikan key ini sesuai
                    "limitation": ai_data.get('limitation', '-')
                })

            return {
                "matrix": final_matrix,
                "synthesis": ai_result.get('synthesis', {})
            }

        except Exception as e:
            logger.error(f"❌ Error Gemini Processing: {str(e)}")
            return {
                "matrix": [], 
                "synthesis": {"gap": "Gagal memproses AI.", "recommendation": "Coba lagi nanti."}
            }
    
    async def generate_summary(self, text: str, lang: str = 'id') -> Optional[str]:
        """
        Generate Structured Summary dalam format JSON String.
        Agar frontend bisa merendernya dalam kotak warna-warni (Context, Technical, Findings).
        """
        if not settings.GOOGLE_API_KEY:
            return None

        try:
            # Cleaning text (sama seperti sebelumnya)
            clean_text = self._clean_text_lines(text)
            clean_text = self._fix_common_artifacts(clean_text)
            head_text = clean_text[:6000]
            tail_text = clean_text[-4500:]
            combined_text = f"{head_text}\n...\n{tail_text}"

            # Prompt Adaptif Bahasa
            if lang == 'en':
                system_role = "You are a Senior Technical Reviewer."
                lang_instruction = "English"
            else:
                system_role = "Anda adalah Senior Reviewer Jurnal Ilmiah."
                lang_instruction = "Bahasa Indonesia yang baku dan akademis"

            # PROMPT JSON STRICT
            prompt = f"""
            {system_role}
            
            Tugas: Analisis teks dokumen berikut dan ekstrak ringkasan mendalam.
            Bahasa Output: {lang_instruction}

            Output HARUS berupa JSON valid dengan struktur persis seperti ini (tanpa markdown ```json):
            {{
                "context_problem": [
                    "Poin 1: Latar belakang masalah atau gap penelitian...",
                    "Poin 2: Urgensi masalah..."
                ],
                "technical_implementation": [
                    "Poin 1: Metode/Algoritma utama yang digunakan...",
                    "Poin 2: Dataset atau tools yang dipakai...",
                    "Poin 3: Alur implementasi..."
                ],
                "critical_findings": [
                    "Poin 1: Hasil utama (akurasi, performa, dll)...",
                    "Poin 2: Insight atau kesimpulan penting..."
                ]
            }}

            TEKS DOKUMEN:
            {combined_text}
            """

            model = genai.GenerativeModel('gemini-2.5-flash')
            response = await model.generate_content_async(prompt)
            result_text = response.text.strip()

            # Bersihkan Markdown JSON jika ada
            if result_text.startswith("```json"):
                result_text = result_text.replace("```json", "").replace("```", "").strip()
            elif result_text.startswith("```"):
                result_text = result_text.replace("```", "").strip()

            # Validasi JSON (Pastikan string ini valid JSON)
            json.loads(result_text) 
            
            return result_text # Kembalikan sebagai string JSON untuk disimpan di DB Text Column

        except Exception as e:
            logger.error(f"❌ Error in Gemini Summary: {e}")
            # Fallback jika gagal JSON, return text biasa agar tidak error null
            return json.dumps({
                "context_problem": ["Gagal memproses konteks."],
                "technical_implementation": ["Gagal memproses teknis."],
                "critical_findings": ["Gagal memproses hasil."]
            })
    
    async def generate_thesis_outline(self, title: str, lang: str = "id") -> dict:
        """
        Generate thesis outline (Bab 1-3) berdasarkan judul menggunakan Gemini AI.
        Disesuaikan dengan Standar Prodi Sistem Informasi Telkom University.
        """
        try:
            if lang == "en":
                # Versi Inggris (Disesuaikan strukturnya)
                system_role = "You are an academic expert assistant."
                user_request = f"""
                Create a DETAILED Thesis Proposal Outline based on the title: "{title}".
                
                REQUIREMENTS:
                1. Chapter 2 must be DEDUCTIVE (General -> Specific) and detailed (approx 8-10 sub-chapters). Last sub-chapter must be "Related Works & State of the Art".
                2. Chapter 3 must follow this exact sequence: Research Method -> Problem Solving Systematics -> Specific Stages -> Data Collection -> Evaluation Method.

                Return valid JSON object matching the exact keys below.
                """
            else:
                # Versi Indonesia (Standar Tel-U SI Strict)
                system_role = "Anda adalah Dosen Pembimbing Senior di Prodi Sistem Informasi Telkom University."
                user_request = f"""
                Buatkan Kerangka Proposal Skripsi (Bab 1-3) yang SANGAT DETAIL dan PANJANG berdasarkan judul: "{title}".
                
                IKUTI ATURAN STRUKTUR BAKU BERIKUT (JANGAN DIUBAH):

                BAB 1: PENDAHULUAN
                - 1.1 Latar Belakang
                - 1.2 Rumusan Masalah
                - 1.3 Tujuan Penelitian
                - 1.4 Batasan Penelitian
                - 1.5 Manfaat Penelitian
                - 1.6 Sistematika Penulisan

                BAB 2: TINJAUAN PUSTAKA (ALUR DEDUKTIF & DETAIL)
                - Buatlah minimal 8 sampai 12 sub-bab.
                - Alur Wajib (Umum ke Khusus):
                  1. Grand Theory (Teori paling umum, misal: Sistem Informasi, Manajemen, atau Kecerdasan Buatan).
                  2. Middle Range Theory (Topik spesifik, misal: CRM, Data Mining, Tata Kelola IT).
                  3. Applied Theory (Variabel spesifik, Algoritma, Rumus, Framework).
                  4. Tools/Teknologi (misal: Python, COBIT 2019, Odoo).
                - Sub-bab TERAKHIR WAJIB (misal 2.10 atau 2.11): "Penelitian Terdahulu dan State of the Art".

                BAB 3: METODOLOGI PENELITIAN (URUTAN BAKU)
                Urutan sub-bab HARUS seperti ini:
                3.1 Metode Penelitian (Jelaskan metode yang dipilih sebagai guidance/payung penelitian).
                3.2 Sistematika Penyelesaian Masalah (Jelaskan alur diagram/flowchart sistematis dari awal sampai akhir).
                3.3 [Nama Tahapan 1 Spesifik] (Detailkan langkah teknis pertama sesuai judul).
                3.4 [Nama Tahapan 2 Spesifik] (Detailkan langkah teknis kedua).
                3.5 [Nama Tahapan 3 Spesifik] (Dan seterusnya sesuai kebutuhan teknis).
                3.6 Metode Pengumpulan dan Pengolahan Data (Jelaskan sumber data, primer/sekunder, dan teknik pengolahannya).
                3.7 Metode Evaluasi (Jelaskan metrik ukur, validasi, atau pengujian akurasi).

                Output HARUS JSON valid dengan struktur keys persis seperti ini (tanpa format markdown):
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
                        {{"sub": "2.1 [Teori Sangat Umum]", "guide": "..."}},
                        {{"sub": "2.2 [Teori Umum]", "guide": "..."}},
                        {{"sub": "2.3 [Teori Menengah]", "guide": "..."}},
                        {{"sub": "2.4 [Teori Spesifik]", "guide": "..."}},
                        {{"sub": "2.5 [Algoritma/Framework]", "guide": "..."}},
                        {{"sub": "2.6 [Detail Teknis]", "guide": "..."}},
                        {{"sub": "2.7 [Tools]", "guide": "..."}},
                        {{"sub": "2.8 Penelitian Terdahulu dan State of the Art", "guide": "Bandingkan dengan penelitian sejenis untuk menunjukkan gap."}}
                    ],
                    "BAB 3: Metodologi Penelitian": [
                        {{"sub": "3.1 Metode Penelitian", "guide": "Jelaskan metode guidance (misal: Design Science, Kuantitatif, dll)."}},
                        {{"sub": "3.2 Sistematika Penyelesaian Masalah", "guide": "Gambaran flowchart alur sistematis penelitian."}},
                        {{"sub": "3.3 Tahap [Inisiasi/Analisis]", "guide": "Langkah awal teknis..."}},
                        {{"sub": "3.4 Tahap [Implementasi/Pengembangan]", "guide": "Langkah utama pembuatan/analisis..."}},
                        {{"sub": "3.5 Metode Pengumpulan dan Pengolahan Data", "guide": "Sumber data (kuesioner/repo) dan cara olah statistik/preprocessing."}},
                        {{"sub": "3.6 Metode Evaluasi", "guide": "Cara mengukur keberhasilan (akurasi, user acceptance, dll)."}}
                    ]
                }}
                """

            # Gabungkan prompt
            final_prompt = f"{system_role}\n\n{user_request}"

            # Inisialisasi Model
            model = genai.GenerativeModel('gemini-2.5-flash')

            # Generate
            try:
                response = await model.generate_content_async(final_prompt)
            except AttributeError:
                response = model.generate_content(final_prompt)

            text_response = response.text.strip()

            # Cleaning JSON
            if text_response.startswith("```json"):
                text_response = text_response.replace("```json", "").replace("```", "").strip()
            elif text_response.startswith("```"):
                text_response = text_response.replace("```", "").strip()
            
            return json.loads(text_response)

        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            return {
                "Error": [{"sub": "Gagal", "guide": "Tidak dapat membuat kerangka. Silakan coba lagi."}]
            }
    
    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        logger.info("Calculating similarity between two texts")
        try:
            prompt = f"""Rate the similarity between these two texts on a scale of 0.0 to 1.0.
                Return ONLY the number, nothing else.

                Text 1:
                {text1[:1000]}

                Text 2:
                {text2[:1000]}"""
            
            response = self.model.generate_content(prompt)
            similarity = float(response.text.strip())
            logger.info(f"Similarity score: {similarity:.3f}")
            return max(0.0, min(1.0, similarity))
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    async def generate_research_ideas(self, docs_data: list, lang: str = "id") -> dict:
        """
        Fitur Premium: Menghasilkan Ide Skripsi Baru dari Sintesis Beberapa Paper.
        Menggunakan teknik 'Recombination' & 'Contextual Transfer'.
        """
        import json
        import re

        # Batasi konteks untuk hemat token
        context_text = ""
        for i, doc in enumerate(docs_data):
            safe_text = doc['text'].replace('\n', ' ')[:2500] 
            context_text += f"\n--- PAPER_{i} (Judul: {doc['title']}) ---\n{safe_text}...\n"

        # Prompt tingkat tinggi (Level S2/S3)
        prompt = f"""
        Bertindaklah sebagai Profesor Pembimbing Tesis Senior di bidang Sistem Informasi & Ilmu Komputer.
        Bahasa Output: {lang}

        TUGAS:
        Berdasarkan {len(docs_data)} paper yang diberikan, sintesiskan 3 IDE TOPIK TUGAS AKHIR BARU yang inovatif tapi realistis untuk mahasiswa S1.
        
        Gunakan teknik sintesis berikut:
        1. Hybrid Method: Menggabungkan metode dari Paper A dengan Paper B.
        2. Domain Transfer: Menerapkan metode Paper A ke masalah/studi kasus yang berbeda (konteks Indonesia/UMKM/dll).
        3. Improvement: Memperbaiki kelemahan yang ditemukan di paper-paper tersebut.

        FORMAT OUTPUT JSON (Wajib Valid JSON):
        {{
            "ideas": [
                {{
                    "title": "Judul Skripsi yang Disarankan (Harus Akademis & Spesifik)",
                    "type": "Tulis tipe inovasi (misal: Hybrid Method / Studi Kasus Baru)",
                    "background": "Jelaskan singkat mengapa topik ini penting (1-2 kalimat).",
                    "problem_statement": "Rumusan masalah utama.",
                    "proposed_method": "Metode/Algoritma yang diusulkan (Sebutkan tools/algoritma spesifik).",
                    "novelty": "Jelaskan letak kebaruannya (beda dari paper referensi).",
                    "source_inspiration": "Inspirasi dari Paper [X] dan Paper [Y]..."
                }}
            ]
        }}

        DAFTAR PAPER REFERENSI:
        {context_text}
        """

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text
            
            # Cleaning JSON
            clean_text = re.sub(r'```json\s*', '', raw_text)
            clean_text = re.sub(r'```\s*', '', clean_text)
            clean_text = clean_text.strip()
            
            start_idx = clean_text.find('{')
            end_idx = clean_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                clean_text = clean_text[start_idx : end_idx + 1]
            
            return json.loads(clean_text)

        except Exception as e:
            logger.error(f"❌ Error Generating Ideas: {str(e)}")
            return {"ideas": []}
    
    def extract_text_from_file(self, file_path: str) -> str:
        """
        Ekstraksi teks robust dengan fallback library.
        """
        import os
        import fitz  # PyMuPDF (Lebih kuat daripada pypdf)
        
        full_path = file_path if os.path.isabs(file_path) else os.path.join(os.getcwd(), file_path)
        
        if not os.path.exists(full_path):
            return ""

        text = ""
        try:
            # COBA 1: Gunakan PyMuPDF (fitz) - Paling cepat & tahan banting
            doc = fitz.open(full_path)
            for page in doc:
                text += page.get_text() + "\n"
            return text
        except Exception as e:
            logger.warning(f"PyMuPDF gagal, mencoba pypdf: {e}")
            
            # COBA 2: Fallback ke pypdf (jika PyMuPDF gagal/tidak ada)
            try:
                from pypdf import PdfReader
                reader = PdfReader(full_path)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except Exception as e2:
                logger.error(f"Gagal ekstrak teks: {e2}")
                return ""
    
    def _extract_text_from_pdf(self, file_path: str) -> Optional[str]:
        """Extract text from PDF using PyPDF2"""
        try:
            text = ""
            with open(file_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            logger.info(f"✅ Extracted text from PDF: {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"❌ Failed to extract text from PDF: {e}")
            return None
    
    def _extract_text_from_docx(self, file_path: str) -> Optional[str]:
        """Extract text from DOCX using python-docx"""
        try:
            doc = Document(file_path)
            paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            text = "\n".join(paragraphs)
            logger.info(f"✅ Extracted text from DOCX: {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"❌ Failed to extract text from DOCX: {e}")
            return None
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text"""
        text_hash = self._get_text_hash(text)
        if text_hash in self.embeddings_cache:
            self.cache_hits += 1
            return self.embeddings_cache[text_hash]
        
        self.cache_misses += 1
        return None
    
    def compute_document_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple documents"""
        logger.info(f"Computing embeddings for {len(texts)} documents")
        return [np.zeros(384) for _ in texts]
    
    def compute_similarity(self, embeddings: List[np.ndarray]) -> np.ndarray:
        """Compute pairwise similarity matrix"""
        n = len(embeddings)
        return np.eye(n)


# Singleton instance
nlp_service = NLPService()