# Environment & Dependency Fix Documentation

## Tanggal: 1 Desember 2025

## Masalah yang Diperbaiki

### 1. **Missing Backend Endpoint**
- **Error**: "Failed to load dosen list" pada halaman mahasiswa
- **Penyebab**: Endpoint `/api/dosen/available-dosen` belum ada di backend
- **Solusi**: Menambahkan endpoint `get_available_dosen` di `backend/app/api/dosen.py`

```python
@router.get("/available-dosen", response_model=List[Dict[str, Any]])
async def get_available_dosen(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get list of available dosen for mahasiswa to select"""
    dosen_list = db.query(Dosen).all()
    return [
        {
            "id": dosen.id,
            "nama": dosen.nama,
            "email": dosen.email,
            "spesialisasi": dosen.spesialisasi
        }
        for dosen in dosen_list
    ]
```

### 2. **Missing email-validator Package**
- **Error**: `ModuleNotFoundError: No module named 'email_validator'`
- **Penyebab**: Pydantic membutuhkan `email-validator` untuk field `EmailStr` tapi package tidak ada di requirements.txt
- **Solusi**: Menambahkan `email-validator==2.2.0` ke requirements.txt

### 3. **Environment Variable Issues**
- **Error**: Backend tidak bisa parse ALLOWED_EXTENSIONS
- **Penyebab**: Format ALLOWED_EXTENSIONS salah (string biasa bukan JSON array)
- **Solusi**: Update format di `.env` menjadi `ALLOWED_EXTENSIONS=["pdf","docx"]`

### 4. **Incomplete Environment Variables**
- **Masalah**: Banyak environment variables yang seharusnya ada tapi tidak terdefinisi
- **Solusi**: Melengkapi `.env` dengan semua environment variables yang dibutuhkan

## Perubahan File

### File: `backend/requirements.txt`
**Penambahan:**
```
email-validator==2.2.0
```

**Lokasi:** Ditambahkan di bagian Core Framework setelah pydantic-settings

### File: `backend/.env`
**Penambahan environment variables:**
```bash
# Database Configuration
DATABASE_URL=postgresql://admin:admin123@localhost:5432/reference_system

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# File Upload Configuration
UPLOAD_DIR=uploads

# NLP Models Configuration
REFERENCE_EXTRACTION_MODEL=en_core_web_sm

# Email Configuration (Optional)
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=noreply@refero.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_FROM_NAME=Refero System
MAIL_STARTTLS=True
MAIL_SSL_TLS=False
USE_CREDENTIALS=True
VALIDATE_CERTS=True

# CAPTCHA Configuration
CAPTCHA_LENGTH=6
CAPTCHA_TIMEOUT=300

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# Application Configuration
APP_NAME=Reference System API
APP_VERSION=1.0.0
DEBUG=True
```

**Perbaikan:**
```bash
# Before (salah):
ALLOWED_EXTENSIONS=pdf,docx

# After (benar):
ALLOWED_EXTENSIONS=["pdf","docx"]
```

### File: `backend/docker-compose.yml`
**Penghapusan:**
```yaml
# Dihapus karena obsolete
version: '3.8'
```

**Alasan:** Docker Compose versi terbaru tidak memerlukan field `version` dan akan memberikan warning jika ada.

### File: `backend/app/api/dosen.py`
**Penambahan endpoint baru:**
```python
@router.get("/available-dosen", response_model=List[Dict[str, Any]])
async def get_available_dosen(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of available dosen for mahasiswa to select"""
    dosen_list = db.query(Dosen).all()
    return [
        {
            "id": dosen.id,
            "nama": dosen.nama,
            "email": dosen.email,
            "spesialisasi": dosen.spesialisasi
        }
        for dosen in dosen_list
    ]
```

## Langkah-Langkah Docker Rebuild

### 1. Install Dependencies Lokal (untuk development)
```bash
cd backend
pip install email-validator==2.2.0
```

### 2. Stop & Clean Docker Containers
```bash
cd backend
docker-compose down -v
```

**Flags:**
- `-v`: Menghapus volumes (database akan di-reset)

### 3. Build Ulang Images
```bash
docker-compose build --no-cache
```

**Flags:**
- `--no-cache`: Build dari awal tanpa menggunakan cache layer sebelumnya

### 4. Start Containers
```bash
docker-compose up -d
```

**Flags:**
- `-d`: Run in detached mode (background)

### 5. Verify Containers
```bash
docker-compose ps
docker-compose logs backend
```

## Dependency List (Backend)

### Core Framework
- fastapi==0.109.0
- uvicorn[standard]==0.27.0
- pydantic==2.7.0
- pydantic-settings==2.3.0
- **email-validator==2.2.0** ← BARU DITAMBAHKAN

### Database
- sqlalchemy==2.0.25
- alembic==1.13.1
- psycopg2-binary==2.9.9
- redis==5.0.1

### Authentication & Security
- python-jose[cryptography]==3.3.0
- passlib[bcrypt]==1.7.4
- python-multipart==0.0.6
- bcrypt==4.1.2

### NLP & ML
- torch==2.1.2 (CPU version)
- transformers==4.36.2
- spacy==3.7.2
- sentence-transformers==2.3.1
- keybert==0.8.4
- scikit-learn==1.4.0
- nltk==3.8.1
- accelerate==0.25.0

### Document Processing
- PyPDF2==3.0.1
- pdfplumber==0.10.3
- python-docx==1.1.0
- pymupdf

### Utilities
- python-dotenv==1.0.0
- aiofiles==23.2.1
- pillow==10.2.0
- captcha==0.5.0

### Testing
- pytest==7.4.4
- pytest-asyncio==0.23.3
- httpx==0.26.0

## Testing Checklist

Setelah Docker rebuild selesai:

### Backend Testing
- [ ] Container backend start tanpa error
- [ ] Container postgres start dan bisa di-connect
- [ ] Container redis start
- [ ] Endpoint `/api/dosen/available-dosen` bisa diakses
- [ ] Email validation bekerja pada registrasi user
- [ ] File upload dengan PDF dan DOCX bekerja

### Frontend Testing
- [ ] Halaman mahasiswa load tanpa error
- [ ] Dropdown dosen list terisi
- [ ] Select dosen dan assign bekerja
- [ ] Upload dokumen bekerja

### Integration Testing
- [ ] Full flow: register → login → upload dokumen → assign dosen → validasi referensi

## Notes

1. **Database Reset**: Karena menggunakan flag `-v`, database akan direset. Perlu run migration ulang jika ada.

2. **Email Validator Version**: Menggunakan 2.2.0 karena 2.1.0 adalah yanked version (deprecated).

3. **Environment Variables**: Semua environment variables sekarang terdefinisi dengan lengkap di `.env` file.

4. **Docker Compose Version**: Field `version` dihapus karena sudah obsolete di Docker Compose versi terbaru.

5. **ALLOWED_EXTENSIONS Format**: HARUS menggunakan format JSON array `["pdf","docx"]` agar bisa di-parse oleh Pydantic sebagai `List[str]`.

## Troubleshooting

### Jika backend masih error saat start:
```bash
# Check logs
docker-compose logs backend

# Check jika ada typo di .env
cat .env

# Restart specific service
docker-compose restart backend
```

### Jika database tidak bisa connect:
```bash
# Check postgres logs
docker-compose logs db

# Test connection
docker exec -it reference_db psql -U admin -d reference_system
```

### Jika email validator masih error:
```bash
# Masuk ke container
docker exec -it reference_backend bash

# Check installed packages
pip list | grep email

# Manual install jika perlu
pip install email-validator==2.2.0
```

## Kesimpulan

Semua dependency dan environment variables sudah diperbaiki dan dilengkapi. Docker rebuild akan memastikan environment yang bersih dan konsisten antara development dan production.
