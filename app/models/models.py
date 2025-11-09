from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Text, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

# Association tables for many-to-many relationships
dokumen_tag = Table(
    'dokumen_tag',
    Base.metadata,
    Column('dokumen_id', Integer, ForeignKey('dokumen.id', ondelete='CASCADE')),
    Column('tag_id', Integer, ForeignKey('tag.id', ondelete='CASCADE'))
)

dokumen_kata = Table(
    'dokumen_kata',
    Base.metadata,
    Column('dokumen_id', Integer, ForeignKey('dokumen.id', ondelete='CASCADE')),
    Column('kata_kunci_id', Integer, ForeignKey('kata_kunci.id', ondelete='CASCADE'))
)


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
    mahasiswa = relationship("Mahasiswa", back_populates="user", uselist=False, cascade="all, delete-orphan")
    dosen = relationship("Dosen", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Mahasiswa(Base):
    __tablename__ = "mahasiswa"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    nim = Column(String(50), unique=True, index=True, nullable=False)
    program_studi = Column(String(255))
    angkatan = Column(Integer)
    dosen_pembimbing_id = Column(Integer, ForeignKey('dosen.id', ondelete='SET NULL'))
    
    # Relationships
    user = relationship("User", back_populates="mahasiswa")
    dosen_pembimbing = relationship("Dosen", back_populates="mahasiswa_bimbingan", foreign_keys=[dosen_pembimbing_id])
    dokumen = relationship("Dokumen", back_populates="mahasiswa", cascade="all, delete-orphan")


class Dosen(Base):
    __tablename__ = "dosen"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    nip = Column(String(50), unique=True, index=True, nullable=False)
    departemen = Column(String(255))
    
    # Relationships
    user = relationship("User", back_populates="dosen")
    mahasiswa_bimbingan = relationship("Mahasiswa", back_populates="dosen_pembimbing", foreign_keys=[Mahasiswa.dosen_pembimbing_id])
    catatan = relationship("Catatan", back_populates="dosen", cascade="all, delete-orphan")


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
    ringkasan = Column(Text)
    status_analisis = Column(String(50), default='pending')  # pending, processing, completed, failed
    
    # Relationships
    mahasiswa = relationship("Mahasiswa", back_populates="dokumen")
    tags = relationship("Tag", secondary=dokumen_tag, back_populates="dokumen")
    kata_kunci = relationship("KataKunci", secondary=dokumen_kata, back_populates="dokumen")
    referensi = relationship("Referensi", back_populates="dokumen", cascade="all, delete-orphan")
    catatan = relationship("Catatan", back_populates="dokumen", cascade="all, delete-orphan")


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
    dokumen = relationship("Dokumen", secondary=dokumen_kata, back_populates="kata_kunci")


class Referensi(Base):
    __tablename__ = "referensi"
    
    id = Column(Integer, primary_key=True, index=True)
    dokumen_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), nullable=False)
    teks_referensi = Column(Text, nullable=False)
    penulis = Column(String(500))
    tahun = Column(Integer)
    judul_publikasi = Column(String(500))
    is_valid = Column(Boolean, default=False)
    catatan_validasi = Column(Text)
    
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


class DocumentSimilarity(Base):
    """Model untuk menyimpan similarity score antar dokumen"""
    __tablename__ = "document_similarity"
    
    id = Column(Integer, primary_key=True, index=True)
    dokumen_1_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), nullable=False)
    dokumen_2_id = Column(Integer, ForeignKey('dokumen.id', ondelete='CASCADE'), nullable=False)
    similarity_score = Column(Float, nullable=False)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
