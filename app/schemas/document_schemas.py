from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# ============= Tag Schemas =============
class TagBase(BaseModel):
    nama: str

class TagCreate(TagBase):
    pass

class TagResponse(TagBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============= Kata Kunci Schemas =============
class KataKunciBase(BaseModel):
    kata: str

class KataKunciResponse(KataKunciBase):
    id: int
    frekuensi: int
    
    class Config:
        from_attributes = True

# ============= Referensi Schemas =============
class ReferensiBase(BaseModel):
    teks_referensi: str
    penulis: Optional[str] = None
    tahun: Optional[int] = None
    judul_publikasi: Optional[str] = None
    nomor: Optional[str] = None  # Ditambahkan agar sesuai dengan frontend

class ReferensiCreate(ReferensiBase):
    dokumen_id: int

class ReferensiResponse(ReferensiBase):
    id: int
    dokumen_id: int
    is_valid: bool
    catatan_validasi: Optional[str] = None
    
    class Config:
        from_attributes = True

# ============= Catatan Schemas =============
class CatatanBase(BaseModel):
    isi_catatan: str
    halaman: Optional[int] = None

class CatatanCreate(CatatanBase):
    dokumen_id: int

class CatatanUpdate(BaseModel):
    isi_catatan: str
    halaman: Optional[int] = None

class CatatanResponse(CatatanBase):
    id: int
    dokumen_id: int
    dosen_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============= Validasi Referensi Schemas =============
class ReferensiValidationRequest(BaseModel):
    is_valid: bool
    catatan_validasi: Optional[str] = None

# ============= Dokumen Schemas =============
class DokumenBase(BaseModel):
    judul: Optional[str] = None

class DokumenCreate(DokumenBase):
    pass

class DokumenResponse(DokumenBase):
    id: int
    mahasiswa_id: int
    nama_file: str
    path_file: str
    format: str
    ukuran_kb: int
    tanggal_unggah: datetime
    ringkasan: Optional[str] = None
    status_analisis: str
    
    # Relasi
    tags: List[TagResponse] = []
    kata_kunci: List[KataKunciResponse] = []
    referensi: List[ReferensiResponse] = [] # Penting: Agar referensi terkirim ke frontend
    
    class Config:
        from_attributes = True

class DokumenDetailResponse(DokumenResponse):
    # Menambahkan detail ekstra jika diperlukan (misal catatan dosen)
    catatan: List[CatatanResponse] = []

# ============= NLP Processing Schemas =============
class KeywordExtractionRequest(BaseModel):
    dokumen_id: int
    top_k: int = 10

class KeywordExtractionResponse(BaseModel):
    dokumen_id: int
    keywords: List[str]
    status: str

class SummarizationRequest(BaseModel):
    dokumen_id: int
    max_length: int = 150
    min_length: int = 50

class SummarizationResponse(BaseModel):
    dokumen_id: int
    summary: str
    status: str

# ============= Visualization Schemas =============
class DocumentNode(BaseModel):
    id: int
    label: str
    tags: List[str]
    keywords: List[str]

class DocumentEdge(BaseModel):
    source: int
    target: int
    weight: float

class VisualizationResponse(BaseModel):
    nodes: List[DocumentNode]
    edges: List[DocumentEdge]