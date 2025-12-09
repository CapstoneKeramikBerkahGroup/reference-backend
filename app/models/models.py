from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Text, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

# --- Association Tables (Many-to-Many) ---

# Tabel Asosiasi Dokumen <-> Tag
dokumen_tag = Table(
    'dokumen_tag',
    Base.metadata,
    Column('dokumen_id', Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id', ondelete='CASCADE'), primary_key=True)
)

# Tabel Asosiasi Dokumen <-> Kata Kunci (Menggunakan Class agar bisa diimport eksplisit)
class DokumenKata(Base):
    __tablename__ = 'dokumen_kata'
    dokumen_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), primary_key=True)
    kata_kunci_id = Column(Integer, ForeignKey('kata_kunci.id', ondelete='CASCADE'), primary_key=True)


# --- Main Models ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nama = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'mahasiswa' or 'dosen'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    mahasiswa_profile = relationship("Mahasiswa", back_populates="user", uselist=False, cascade="all, delete-orphan")
    dosen_profile = relationship("Dosen", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Mahasiswa(Base):
    __tablename__ = "mahasiswa"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    nim = Column(String(50), unique=True, index=True, nullable=False)
    program_studi = Column(String(255), default='Sistem Informasi')  # Default S1 Sistem Informasi
    angkatan = Column(Integer)
    bidang_keahlian = Column(String(255))  # Specialization: EISD, EDM, EIM, ERP, SAG
    dosen_pembimbing_id = Column(Integer, ForeignKey('dosen.id', ondelete='SET NULL'))
    
    # Relationships
    user = relationship("User", back_populates="mahasiswa_profile")
    dosen_pembimbing = relationship("Dosen", back_populates="mahasiswa_bimbingan")
    dokumen = relationship("Dokumen", back_populates="mahasiswa", cascade="all, delete-orphan")
    pembimbing_requests = relationship("PembimbingRequest", back_populates="mahasiswa", cascade="all, delete-orphan")


class Dosen(Base):
    __tablename__ = "dosen"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    nip = Column(String(50), unique=True, index=True, nullable=False)
    jabatan = Column(String(255))      # Disesuaikan dari 'departemen' ke 'jabatan' agar konsisten dengan schema
    bidang_keahlian = Column(String(255)) # Tambahan agar konsisten dengan schema
    
    # Relationships
    user = relationship("User", back_populates="dosen_profile")
    mahasiswa_bimbingan = relationship("Mahasiswa", back_populates="dosen_pembimbing")
    catatan = relationship("Catatan", back_populates="dosen", cascade="all, delete-orphan")
    pembimbing_requests = relationship("PembimbingRequest", back_populates="dosen", cascade="all, delete-orphan")


class Dokumen(Base):
    __tablename__ = "dokumen"
    
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'), nullable=False)
    judul = Column(String(500))
    nama_file = Column(String(255), nullable=False)
    path_file = Column(String(500), nullable=False)
    format = Column(String(10))  # 'pdf' or 'docx'
    ukuran_kb = Column(Integer)
    tanggal_unggah = Column(DateTime(timezone=True), server_default=func.now())
    
    # Hasil Analisis NLP
    ringkasan = Column(Text)
    status_analisis = Column(String(50), default='pending')  # pending, processing, completed, failed
    
    # Relationships
    mahasiswa = relationship("Mahasiswa", back_populates="dokumen")
    
    # Many-to-Many
    tags = relationship("Tag", secondary=dokumen_tag, back_populates="dokumen")
    kata_kunci = relationship("KataKunci", secondary="dokumen_kata", back_populates="dokumen")
    
    # One-to-Many
    referensi = relationship("Referensi", back_populates="dokumen", cascade="all, delete-orphan")
    catatan = relationship("Catatan", back_populates="dokumen", cascade="all, delete-orphan")
    
    # Similarity Relationships
    similarities_source = relationship("DocumentSimilarity", 
                                     foreign_keys="[DocumentSimilarity.dokumen_1_id]",
                                     back_populates="dokumen_1",
                                     cascade="all, delete-orphan")
    similarities_target = relationship("DocumentSimilarity", 
                                     foreign_keys="[DocumentSimilarity.dokumen_2_id]",
                                     back_populates="dokumen_2",
                                     cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tag"
    
    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    dokumen = relationship("Dokumen", secondary=dokumen_tag, back_populates="tags")


class KataKunci(Base):
    __tablename__ = "kata_kunci"
    
    id = Column(Integer, primary_key=True, index=True)
    kata = Column(String(255), unique=True, nullable=False, index=True)
    frekuensi = Column(Integer, default=1)
    
    # Relationships
    dokumen = relationship("Dokumen", secondary="dokumen_kata", back_populates="kata_kunci")


class Referensi(Base):
    __tablename__ = "referensi"
    
    id = Column(Integer, primary_key=True, index=True)
    dokumen_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), nullable=False)
    teks_referensi = Column(Text, nullable=False)
    penulis = Column(String(500))
    tahun = Column(Integer)
    judul_publikasi = Column(String(500))
    nomor = Column(String(50)) # Menambahkan kolom nomor (misal "1", "[12]")
    status_validasi = Column(String(50), default='pending')  # 'pending', 'validated', 'rejected'
    catatan_validasi = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    dokumen = relationship("Dokumen", back_populates="referensi")


class Catatan(Base):
    __tablename__ = "catatan"
    
    id = Column(Integer, primary_key=True, index=True)
    dokumen_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), nullable=False)
    dosen_id = Column(Integer, ForeignKey('dosen.id', ondelete='CASCADE'), nullable=False)
    isi_catatan = Column(Text, nullable=False)
    halaman = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    dokumen = relationship("Dokumen", back_populates="catatan")
    dosen = relationship("Dosen", back_populates="catatan")


class PembimbingRequest(Base):
    """Model untuk request pembimbing dari mahasiswa ke dosen"""
    __tablename__ = "pembimbing_request"
    
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'), nullable=False)
    dosen_id = Column(Integer, ForeignKey('dosen.id', ondelete='CASCADE'), nullable=False)
    status = Column(String(20), default='pending')  # pending, accepted, rejected
    pesan_mahasiswa = Column(Text)
    pesan_dosen = Column(Text)  # Pesan feedback dari dosen
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    mahasiswa = relationship("Mahasiswa", back_populates="pembimbing_requests")
    dosen = relationship("Dosen", back_populates="pembimbing_requests")


class DocumentSimilarity(Base):
    """Model untuk menyimpan similarity score antar dokumen"""
    __tablename__ = "document_similarity"
    
    id = Column(Integer, primary_key=True, index=True)
    dokumen_1_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), nullable=False)
    dokumen_2_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), nullable=False)
    similarity_score = Column(Float, nullable=False)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    dokumen_1 = relationship("Dokumen", foreign_keys=[dokumen_1_id], back_populates="similarities_source")
    dokumen_2 = relationship("Dokumen", foreign_keys=[dokumen_2_id], back_populates="similarities_target")


class MendeleyToken(Base):
    """Model untuk menyimpan Mendeley OAuth tokens"""
    __tablename__ = "mendeley_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    mahasiswa_id = Column(Integer, ForeignKey('mahasiswa.id', ondelete='CASCADE'), nullable=False, unique=True)
    access_token = Column(String(500), nullable=False)
    refresh_token = Column(String(500))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    mahasiswa = relationship("Mahasiswa", backref="mendeley_token")


class UserZotero(Base):
    """Menyimpan akses token Zotero milik user"""
    __tablename__ = "user_zotero"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    zotero_user_id = Column(String) # ID unik dari Zotero
    api_key = Column(String) # Token akses
    library_type = Column(String, default="user") # 'user' atau 'group'
    last_sync = Column(DateTime, nullable=True)
    
    user = relationship("User", backref="zotero_account")


class ExternalReference(Base):
    """
    Menyimpan metadata referensi dari Zotero/Mendeley.
    PDF TIDAK disimpan di sini, tapi di-download on-demand.
    """
    __tablename__ = "external_references"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    source = Column(String, default="zotero") # 'zotero' or 'mendeley'
    source_id = Column(String) # ID item di Zotero (Key)
    
    title = Column(String)
    authors = Column(String) # Disimpan sebagai JSON string atau teks gabungan
    year = Column(String)
    abstract = Column(Text, nullable=True)
    url = Column(String, nullable=True) # Link ke file PDF di Zotero
    has_pdf = Column(Boolean, default=False)
    
    # Status sinkronisasi ke sistem AI Nalar-Net
    is_analyzed = Column(Boolean, default=False) 
    local_document_id = Column(Integer, ForeignKey("dokumen.id", ondelete='SET NULL'), nullable=True) # Link ke tabel Dokumen jika sudah di-analisis
    
    user = relationship("User", backref="external_references")
