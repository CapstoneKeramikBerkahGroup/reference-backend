# Reference Management System - Backend API

Sistem pengelolaan dan analisis hubungan antar referensi ilmiah menggunakan FastAPI, PostgreSQL, dan NLP dengan dukungan integrasi Mendeley dan Zotero.

## 🚀 Features

- ✅ **Authentication & Authorization** (JWT-based)
  - Registrasi & login untuk Mahasiswa dan Dosen
  - Role-based access control
  - Profile management dengan bidang keahlian
  
- 📄 **Document Management**
  - Upload dokumen (PDF, DOCX)
  - Multi-source support (Manual Upload, Mendeley, Zotero)
  - Download & delete dokumen
  - Tag management
  - Advanced search and filtering
  
- 🔗 **Integration Services**
  - **Mendeley Integration** - OAuth2 authentication, library sync
  - **Zotero Integration** - API key authentication, automatic import
  - Token persistence and refresh handling
  - Duplicate prevention across sources
  
- 🤖 **NLP Processing**
  - Indonesian language support with custom NLP
  - Automatic keyword extraction (lightweight)
  - Extractive text summarization
  - Reference extraction and validation
  - Research gap analysis
  
- 👥 **Pembimbingan System**
  - Request pembimbing workflow
  - Dosen-mahasiswa relationship management
  - Request approval/rejection with notes
  
- 📊 **Reference Management**
  - Automatic reference detection from documents
  - Reference validation by dosen
  - Status tracking (pending/validated/rejected)
  - Notes and feedback system
  
- 🕸️ **Visualization**
  - Document similarity graph
  - Interactive network visualization data
  
## 🛠️ Tech Stack

- **Framework**: FastAPI 0.109.0
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **NLP**: Custom Indonesian NLP, spaCy, Sentence Transformers
- **Authentication**: JWT (python-jose)
- **ORM**: SQLAlchemy 2.0
- **Integrations**: Mendeley API (OAuth2), Zotero API
- **Email**: SMTP (MailHog for development)
- **File Processing**: PyPDF2, python-docx

## 📦 Installation

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (if running locally)

### Quick Start with Docker

1. **Clone repository**
```bash
cd backend
```

2. **Copy environment file**
```bash
copy .env.example .env
```

3. **Build and run containers**
```bash
docker-compose up --build
```

4. **API will be available at:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Local Development (without Docker)

1. **Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

3. **Setup PostgreSQL & Redis**
```bash
# Install PostgreSQL and Redis locally
# Update DATABASE_URL and REDIS_URL in .env
```

4. **Run application**
```bash
uvicorn app.main:app --reload
```

## 📚 API Documentation

### Authentication Endpoints

#### Register Mahasiswa
```http
POST /api/auth/register/mahasiswa
Content-Type: application/json

{
  "nim": "1202223217",
  "program_studi": "Sistem Informasi",
  "angkatan": 2022,
  "user": {
    "email": "dhimmas@student.telkomuniversity.ac.id",
    "nama": "Dhimmas Parikesit",
    "password": "password123",
    "role": "mahasiswa"
  }
}
```

#### Register Dosen
```http
POST /api/auth/register/dosen
Content-Type: application/json

{
  "nip": "198001012020121001",
  "departemen": "Sistem Informasi",
  "user": {
    "email": "dosen@telkomuniversity.ac.id",
    "nama": "Dr. Taufik Nur Adi",
    "password": "password123",
    "role": "dosen"
  }
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=dhimmas@student.telkomuniversity.ac.id&password=password123
```

Response:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

#### Get Current User
```http
GET /api/auth/me
Authorization: Bearer {token}
```

### Document Management

#### Upload Document
```http
POST /api/documents/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: [PDF/DOCX file]
judul: "Machine Learning in Healthcare"
```

#### Get All Documents
```http
GET /api/documents/
Authorization: Bearer {token}
```

#### Get Document by ID
```http
GET /api/documents/{dokumen_id}
Authorization: Bearer {token}
```

#### Download Document
```http
GET /api/documents/{dokumen_id}/download
Authorization: Bearer {token}
```

#### Delete Document
```http
DELETE /api/documents/{dokumen_id}
Authorization: Bearer {token}
```

#### Add Tag to Document
```http
POST /api/documents/{dokumen_id}/tags
Authorization: Bearer {token}
Content-Type: application/json

{
  "nama": "machine-learning"
}
```

#### Search Documents
```http
GET /api/documents/search/?q=machine+learning
Authorization: Bearer {token}
```

### NLP Processing

#### Extract Keywords
```http
POST /api/nlp/extract-keywords
Authorization: Bearer {token}
Content-Type: application/json

{
  "dokumen_id": 1,
  "top_k": 10
}
```

#### Generate Summary
```http
POST /api/nlp/summarize
Authorization: Bearer {token}
Content-Type: application/json

{
  "dokumen_id": 1,
  "max_length": 150,
  "min_length": 50
}
```

#### Process Document (Background)
```http
POST /api/nlp/process/{dokumen_id}
Authorization: Bearer {token}
```

#### Check Processing Status
```http
GET /api/nlp/status/{dokumen_id}
Authorization: Bearer {token}
```

### Visualization

#### Get Document Graph
```http
GET /api/visualization/graph?min_similarity=0.3
Authorization: Bearer {token}
```

Response:
```json
{
  "nodes": [
    {
      "id": 1,
      "label": "Machine Learning Research",
      "tags": ["ml", "ai"],
      "keywords": ["neural", "network", "deep learning"]
    }
  ],
  "edges": [
    {
      "source": 1,
      "target": 2,
      "weight": 0.85
    }
  ]
}
```

#### Get Similar Documents
```http
GET /api/visualization/similarity/{dokumen_id}?limit=5
Authorization: Bearer {token}
```

## 🗄️ Database Schema

### Main Tables
- `users` - User accounts (email, password, role)
- `mahasiswa` - Student profiles (NIM, program, angkatan, bidang_keahlian)
- `dosen` - Lecturer profiles (NIP, departemen, bidang_keahlian, max_bimbingan)
- `dokumen` - Documents/references (judul, file_path, source: manual/mendeley/zotero)
- `tag` - Document tags
- `kata_kunci` - Keywords extracted from documents
- `referensi` - References with validation status
- `catatan` - Lecturer validation notes
- `document_similarity` - Similarity scores between documents
- `pembimbing_request` - Guidance requests (status, messages)
- `pembimbing_mahasiswa` - Active guidance relationships

### Integration Tables
- `mendeley_tokens` - Mendeley OAuth tokens (access_token, refresh_token, expires_at)
- `zotero_config` - Zotero API configuration (user_id, api_key)

### Key Relationships
- User → Mahasiswa/Dosen (1:1)
- Mahasiswa → Dokumen (1:N)
- Mahasiswa ↔ Dosen via pembimbing_request & pembimbing_mahasiswa
- Dokumen ↔ Tag (N:M)
- Dokumen ↔ KataKunci (N:M)
- Dokumen → Referensi (1:N)
- Referensi → Catatan (1:N)

## 🧪 Testing

### Using Swagger UI
Visit http://localhost:8000/docs for interactive API testing

### Using curl
```bash
# Login
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password123"

# Upload document
curl -X POST "http://localhost:8000/api/documents/upload" \
  -H "Authorization: Bearer {token}" \
  -F "file=@paper.pdf" \
  -F "judul=Research Paper"
```

## 🔧 Configuration

Edit `.env` file:

```env
# Database
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123
POSTGRES_DB=reference_system
DATABASE_URL=postgresql://admin:admin123@localhost:5432/reference_system

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Upload
MAX_FILE_SIZE_MB=10
ALLOWED_EXTENSIONS=pdf,docx
UPLOAD_DIR=uploads

# Integration APIs
MENDELEY_CLIENT_ID=your-mendeley-client-id
MENDELEY_CLIENT_SECRET=your-mendeley-client-secret
MENDELEY_REDIRECT_URI=http://localhost:3000/dashboard

# Email (Development with MailHog)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@refmanager.com

# NLP Settings
USE_LIGHTWEIGHT_NLP=true
KEYWORD_EXTRACTION_TOP_K=10
SUMMARY_SENTENCES=3
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/              # API endpoints
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── documents.py  # Document management
│   │   ├── nlp.py        # NLP processing
│   │   ├── users.py      # User management
│   │   ├── dosen.py      # Dosen-specific endpoints
│   │   ├── pembimbing.py # Guidance system
│   │   ├── integration.py # Mendeley/Zotero integration
│   │   ├── mendeley.py   # Mendeley OAuth callbacks
│   │   └── visualization.py # Graph data
│   ├── core/             # Core configurations
│   │   ├── config.py     # Settings
│   │   ├── database.py   # Database connection
│   │   └── security.py   # JWT & password hashing
│   ├── models/           # SQLAlchemy models
│   │   └── models.py     # All database models
│   ├── schemas/          # Pydantic schemas
│   │   ├── user_schemas.py
│   │   └── document_schemas.py
│   ├── services/         # Business logic
│   │   ├── nlp_service.py      # NLP processing
│   │   ├── custom_nlp.py       # Indonesian NLP
│   │   ├── mendeley_service.py # Mendeley integration
│   │   ├── zotero_service.py   # Zotero integration
│   │   ├── email_service.py    # Email notifications
│   │   └── redis_service.py    # Redis caching
│   └── main.py           # FastAPI application
├── uploads/              # Uploaded files (organized by user)
├── logs/                 # Application logs
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Multi-container setup
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables
```

## 🐳 Docker Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down

# Rebuild containers
docker-compose up --build

# Access database
docker exec -it reference_db psql -U admin -d reference_system

# Access backend shell
docker exec -it reference_backend bash
```

## 🚨 Troubleshooting

### Port already in use
```bash
# Stop existing containers
docker-compose down

# Check ports
netstat -ano | findstr :8000
netstat -ano | findstr :5432
```

### Database connection error
```bash
# Check database is running
docker-compose ps

# Restart database
docker-compose restart db
```

### NLP models not downloading
```bash
# Download manually inside container
docker exec -it reference_backend python -m spacy download en_core_web_sm
```

## 📝 License

MIT License - Telkom University Capstone Project 2025

## 👥 Contributors

- Dhimmas Parikesit (1202223217)
- Alisha Deanova Oemar (1202223105)
- Balqis Eka Nurfadisyah (1202220223)

## 📞 Support

For issues and questions, please contact: dhimmas@student.telkomuniversity.ac.id
