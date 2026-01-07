from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Text, Boolean, Float, JSON
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.core.database import Base

# --- Association Tables ---
dokumen_tag = Table(
    'dokumen_tag',
    Base.metadata,
    Column('dokumen_id', Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id', ondelete='CASCADE'), primary_key=True)
)

class DokumenKata(Base):
    __tablename__ = 'dokumen_kata'
    dokumen_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), primary_key=True)
    kata_kunci_id = Column(Integer, ForeignKey('kata_kunci.id', ondelete='CASCADE'), primary_key=True)

# --- Core Users ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nama = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    mahasiswa_profile = relationship("Mahasiswa", back_populates="user", uselist=False, cascade="all, delete-orphan")
    dosen_profile = relationship("Dosen", back_populates="user", uselist=False, cascade="all, delete-orphan")
    draft_comments = relationship("DraftComment", back_populates="user")
    
    # Zotero & References
    zotero_account = relationship("UserZotero", back_populates="user", uselist=False)
    external_references = relationship("ExternalReference", back_populates="user")

class Mahasiswa(Base):
    __tablename__ = "mahasiswa"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    nim = Column(String(50), unique=True, index=True)
    program_studi = Column(String(255))
    angkatan = Column(Integer)
    bidang_keahlian = Column(String(255))
    dosen_pembimbing_id = Column(Integer, ForeignKey('dosen.id', ondelete='SET NULL'))
    
    user = relationship("User", back_populates="mahasiswa_profile")
    
    # --- PERBAIKAN: HANYA ADA SATU DEFINISI DRAFTS ---
    drafts = relationship("Draft", back_populates="mahasiswa", cascade="all, delete-orphan")
    
    dosen_pembimbing = relationship("Dosen", back_populates="mahasiswa_bimbingan")
    dokumen = relationship("Dokumen", back_populates="mahasiswa", cascade="all, delete-orphan")
    pembimbing_requests = relationship("PembimbingRequest", back_populates="mahasiswa")
    mendeley_token = relationship("MendeleyToken", back_populates="mahasiswa", uselist=False)
    
    gap_histories = relationship("GapAnalysisHistory", back_populates="mahasiswa", cascade="all, delete-orphan")
    idea_histories = relationship("IdeaHistory", back_populates="mahasiswa", cascade="all, delete-orphan")

class Dosen(Base):
    __tablename__ = "dosen"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    nip = Column(String(50), unique=True, index=True)
    jabatan = Column(String(255))
    bidang_keahlian = Column(String(255))
    
    user = relationship("User", back_populates="dosen_profile")
    mahasiswa_bimbingan = relationship("Mahasiswa", back_populates="dosen_pembimbing")
    catatan = relationship("Catatan", back_populates="dosen")
    pembimbing_requests = relationship("PembimbingRequest", back_populates="dosen")

class IdeaHistory(Base):
    __tablename__ = "idea_history"
    
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'))
    
    # Menyimpan konten ide lengkap dalam JSON
    title = Column(String) 
    content_json = Column(JSON) # Berisi background, problem, method, novelty, dll.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    mahasiswa = relationship("Mahasiswa", back_populates="idea_histories")
    
class Draft(Base):
    __tablename__ = "drafts"
    
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'))
    title = Column(String(255))
    version = Column(Integer, default=1)
    file_path = Column(String(500))
    status = Column(String(50), default='pending') # pending, reviewed, approved
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    mahasiswa = relationship("Mahasiswa", back_populates="drafts")
    comments = relationship("DraftComment", back_populates="draft", cascade="all, delete-orphan")

class DraftComment(Base):
    __tablename__ = "draft_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey('drafts.id', ondelete='CASCADE'))
    user_id = Column(Integer, ForeignKey('users.id')) 
    
    content = Column(Text)
    
    # --- FITUR BARU ---
    parent_id = Column(Integer, ForeignKey('draft_comments.id'), nullable=True) # Untuk Balasan (Reply)
    quoted_text = Column(Text, nullable=True) # Teks yang di-highlight dari PDF
    page_number = Column(Integer, nullable=True) # Halaman berapa
    # ------------------

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    draft = relationship("Draft", back_populates="comments")
    user = relationship("User", back_populates="draft_comments")
    
    # Relasi Self-Referential untuk Threaded Comments
    replies = relationship("DraftComment", 
        backref=backref('parent', remote_side=[id]),
        cascade="all, delete-orphan"
    )

# --- Documents & NLP ---
class Dokumen(Base):
    __tablename__ = "dokumen"
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'), nullable=False)
    judul = Column(String(500))
    nama_file = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False) # Pastikan nama field konsisten
    format = Column(String(10))
    ukuran_kb = Column(Integer)
    tanggal_unggah = Column(DateTime(timezone=True), server_default=func.now())
    ringkasan = Column(Text)
    status_analisis = Column(String(50), default='pending')
    
    mahasiswa = relationship("Mahasiswa", back_populates="dokumen")
    tags = relationship("Tag", secondary=dokumen_tag, back_populates="dokumen")
    kata_kunci = relationship("KataKunci", secondary="dokumen_kata", back_populates="dokumen")
    referensi = relationship("Referensi", back_populates="dokumen", cascade="all, delete-orphan")
    catatan = relationship("Catatan", back_populates="dokumen", cascade="all, delete-orphan")
    
    similarities_source = relationship("DocumentSimilarity", foreign_keys="[DocumentSimilarity.dokumen_1_id]", back_populates="dokumen_1")
    similarities_target = relationship("DocumentSimilarity", foreign_keys="[DocumentSimilarity.dokumen_2_id]", back_populates="dokumen_2")

class Tag(Base):
    __tablename__ = "tag"
    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    dokumen = relationship("Dokumen", secondary=dokumen_tag, back_populates="tags")

class KataKunci(Base):
    __tablename__ = "kata_kunci"
    id = Column(Integer, primary_key=True, index=True)
    kata = Column(String(255), unique=True, nullable=False)
    frekuensi = Column(Integer, default=1)
    dokumen = relationship("Dokumen", secondary="dokumen_kata", back_populates="kata_kunci")

class Referensi(Base):
    __tablename__ = "referensi"
    id = Column(Integer, primary_key=True, index=True)
    dokumen_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'))
    teks_referensi = Column(Text, nullable=False)
    penulis = Column(String(500))
    tahun = Column(Integer)
    judul_publikasi = Column(String(500))
    nomor = Column(String(50))
    status_validasi = Column(String(50), default='pending')
    catatan_validasi = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    dokumen = relationship("Dokumen", back_populates="referensi")

class Catatan(Base):
    __tablename__ = "catatan"
    id = Column(Integer, primary_key=True, index=True)
    dokumen_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'))
    dosen_id = Column(Integer, ForeignKey('dosen.id', ondelete='CASCADE'))
    isi_catatan = Column(Text, nullable=False)
    halaman = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    dokumen = relationship("Dokumen", back_populates="catatan")
    dosen = relationship("Dosen", back_populates="catatan")

class PembimbingRequest(Base):
    __tablename__ = "pembimbing_request"
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'))
    dosen_id = Column(Integer, ForeignKey('dosen.id', ondelete='CASCADE'))
    status = Column(String(20), default='pending')
    pesan_mahasiswa = Column(Text)
    pesan_dosen = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    mahasiswa = relationship("Mahasiswa", back_populates="pembimbing_requests")
    dosen = relationship("Dosen", back_populates="pembimbing_requests")

class DocumentSimilarity(Base):
    __tablename__ = "document_similarity"
    id = Column(Integer, primary_key=True, index=True)
    dokumen_1_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'))
    dokumen_2_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'))
    similarity_score = Column(Float, nullable=False)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    dokumen_1 = relationship("Dokumen", foreign_keys=[dokumen_1_id], back_populates="similarities_source")
    dokumen_2 = relationship("Dokumen", foreign_keys=[dokumen_2_id], back_populates="similarities_target")

# --- Integrations ---

class MendeleyToken(Base):
    __tablename__ = "mendeley_tokens"
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'), unique=True)
    access_token = Column(String(1000), nullable=False)
    refresh_token = Column(String(1000))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    mahasiswa = relationship("Mahasiswa", back_populates="mendeley_token")

class UserZotero(Base):
    __tablename__ = "user_zotero"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    zotero_user_id = Column(String)
    api_key = Column(String)
    library_type = Column(String, default="user")
    last_sync = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="zotero_account")

class ExternalReference(Base):
    __tablename__ = "external_references"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    source = Column(String, default="zotero")
    source_id = Column(String)
    title = Column(String)
    authors = Column(String)
    year = Column(String)
    abstract = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    has_pdf = Column(Boolean, default=False)
    is_analyzed = Column(Boolean, default=False)
    local_document_id = Column(Integer, ForeignKey("dokumen.id", ondelete='SET NULL'), nullable=True)
    user = relationship("User", back_populates="external_references")

# --- FITUR GAP ANALYSIS (WAJIB ADA) ---
class GapAnalysisHistory(Base):
    __tablename__ = "gap_analysis_history"
    
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'))
    query_description = Column(String)  # Judul analisis
    result_json = Column(JSON)          # Hasil matriks AI
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    mahasiswa = relationship("Mahasiswa", back_populates="gap_histories")