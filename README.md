# Reference Management System - Backend API

**Refero** - Sistem manajemen referensi ilmiah berbasis AI dengan analisis NLP, integrasi Mendeley/Zotero, dan sistem pembimbingan untuk mahasiswa dan dosen.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

## 🚀 Features

### 🔐 **Authentication & Authorization**
- JWT-based authentication with refresh tokens
- Role-based access control (RBAC)
- Registrasi terpisah untuk Mahasiswa dan Dosen
- Profile management dengan spesialisasi
- Email verification (production-ready)

### 📄 **Document Management**
- Upload multi-format (PDF, DOCX) dengan validasi
- Drag & drop file upload
- Document metadata extraction
- Full-text search dengan PostgreSQL FTS
- Tag management dan kategorisasi
- Download & delete dengan permission control
- Multi-source tracking (Manual, Mendeley, Zotero)
- File storage dengan path optimization

### 🔗 **Third-Party Integration**
- **Mendeley OAuth2 Integration**
  - Secure OAuth2 flow dengan PKCE
  - Automatic library synchronization
  - Token refresh mechanism
  - Document metadata import
  
- **Zotero API Integration**
  - API key-based authentication
  - Library and collection sync
  - Batch document import
  - Progress tracking untuk sync besar

### 🤖 **Advanced NLP Processing**
- **Indonesian Language Support** (Bahasa Indonesia)
  - Custom Indonesian tokenizer
  - Stopword removal untuk bahasa Indonesia
  - TF-IDF keyword extraction
  
- **Keyword Extraction**
  - Multiple algorithms (TF-IDF, BERT-based)
  - Multi-language support (ID/EN)
  - Top-K configurable extraction
  
- **Text Summarization**
  - Extractive summarization (BART-based)
  - Configurable length (min/max)
  - Context-aware processing
  
- **Reference Extraction**
  - Citation pattern detection
  - Multiple citation styles (APA, IEEE, etc.)
  - Automatic validation
  
- **Background Processing**
  - Async document processing dengan Celery (optional)
  - Real-time status tracking
  - Progress monitoring via Redis

### 🤖 **Google Gemini AI Integration**
- **Research Gap Analysis**
  - Gap matrix generation from multiple documents
  - Strength & limitation identification
  - Research opportunity detection
  - Multi-language support (ID/EN)
  - Smart author detection
  
- **Research Idea Generator**
  - AI-powered research topic suggestions
  - Literature-based idea generation
  - Contextual recommendations
  - Bilingual output support
  
- **Thesis Outline Generator**
  - Automatic Chapter 1-3 outline generation
  - Telkom University standard compliant
  - Detailed sub-chapter structure
  - Deductive Chapter 2 format
  - Metodologi Penelitian template
  
- **Powered by Gemini 2.5 Flash**
  - Fast response times
  - High-quality Indonesian text generation
  - Context-aware processing
  - Cost-effective API usage

### 👥 **Pembimbingan System**
- **For Students (Mahasiswa)**
  - Browse dosen by specialization
  - Send guidance requests dengan personal message
  - Track request status (pending/accepted/rejected)
  - View active pembimbing
  - Cancel pending requests
  
- **For Lecturers (Dosen)**
  - Review incoming requests
  - Accept/reject dengan catatan
  - View guided students
  - Manage multiple students
  - Request history tracking

### ✅ **Reference Validation / Review Draft**
- Dosen can validate student references
- Status tracking (pending/validated/rejected)
- Validation notes and feedback
- Filter by document and status
- Validation history

### 🕸️ **Document Visualization**
- Similarity-based document graph
- Adjustable similarity threshold
- Node and edge data for Cytoscape.js
- Community detection (planned)

### 📊 **Research Gap Analysis**
- AI-powered gap identification
- Literature coverage analysis
- Research opportunity suggestions

## 🛠️ Tech Stack

### Core Framework
- **FastAPI** 0.109.0 - Modern, fast web framework
- **Python** 3.11+ - Primary language
- **Uvicorn** - ASGI server with hot reload

### Database & Cache
- **PostgreSQL** 15 - Primary database with JSONB support
- **Redis** 7 - Caching & session management
- **SQLAlchemy** 2.0 - Modern ORM with async support
- **Alembic** - Database migrations

### NLP & AI
- **Google Gemini API** 2.5 Flash - AI-powered content generation
- **spaCy** 3.x - Core NLP processing
- **Transformers** (Hugging Face) - BART summarization
- **Sentence Transformers** - Document embeddings
- **Scikit-learn** - TF-IDF, clustering

### Authentication & Security
- **python-jose** - JWT token handling
- **passlib** + **bcrypt** - Password hashing
- **python-multipart** - File upload handling

### Integration
- **httpx** - Async HTTP client
- **requests** - Mendeley/Zotero API calls
- **PyPDF2** - PDF text extraction
- **python-docx** - DOCX processing

### Development Tools
- **Docker** & **Docker Compose** - Containerization
- **pytest** - Testing framework
- **black** - Code formatting
- **mypy** - Static type checking

## 📦 Installation & Setup

### Prerequisites

- **Docker** & **Docker Compose** (recommended)
- **Python** 3.11+ (for local development)
- **PostgreSQL** 15+ (if not using Docker)
- **Redis** 7+ (if not using Docker)

### 🐳 Quick Start with Docker (Recommended)

1. **Clone the repository**
```bash
git clone https://github.com/CapstoneKeramikBerkahGroup/reference-backend.git
cd reference-backend/backend
```

2. **Copy environment file**
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

3. **Configure environment variables** (edit `.env`)
```env
# Database
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123
POSTGRES_DB=reference_system

# JWT Secret (CHANGE IN PRODUCTION!)
SECRET_KEY=your-secret-key-here

# Mendeley OAuth (get from https://dev.mendeley.com/myapps.html)
MENDELEY_CLIENT_ID=your-client-id
MENDELEY_CLIENT_SECRET=your-client-secret
MENDELEY_REDIRECT_URI=http://localhost:8000/api/mendeley/oauth/callback

# Google API (optional, for additional features)
GOOGLE_API_KEY=your-google-api-key
```

4. **Build and run containers**
```bash
docker-compose up --build
```

5. **Initialize database** (first time only)
```bash
docker-compose exec backend alembic upgrade head
```

6. **Access the application**
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 💻 Local Development (without Docker)

1. **Create virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

3. **Setup PostgreSQL**
```bash
# Install PostgreSQL 15+
# Create database
psql -U postgres
CREATE DATABASE reference_system;
CREATE USER admin WITH PASSWORD 'admin123';
GRANT ALL PRIVILEGES ON DATABASE reference_system TO admin;
\q
```

4. **Setup Redis**
```bash
# Install Redis 7+
# Start Redis server
redis-server
```

5. **Configure environment**
```bash
copy .env.example .env
# Edit .env with your local database credentials
```

6. **Run database migrations**
```bash
alembic upgrade head
```

7. **Run application**
```bash
# Development mode with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio

# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_api.py
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # API routes
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── documents.py       # Document management
│   │   ├── dosen.py           # Dosen-specific endpoints
│   │   ├── drafts.py          # Draft management
│   │   ├── gap_analysis.py    # Research gap analysis
│   │   ├── integration.py     # Mendeley/Zotero integration
│   │   ├── mendeley.py        # Mendeley OAuth endpoints
│   │   ├── nlp.py             # NLP processing endpoints
│   │   ├── pembimbing.py      # Guidance system
│   │   ├── users.py           # User management
│   │   └── visualization.py   # Graph visualization
│   ├── core/                   # Core functionality
│   │   ├── config.py          # Configuration management
│   │   ├── database.py        # Database connection
│   │   └── security.py        # Security utilities
│   ├── models/                 # SQLAlchemy models
│   │   └── models.py          # Database models
│   ├── schemas/                # Pydantic schemas
│   │   ├── document_schemas.py
│   │   └── user_schemas.py
│   └── services/               # Business logic
│       ├── captcha_service.py
│       ├── custom_nlp.py      # Indonesian NLP support
│       ├── email_service.py
│       ├── mendeley_service.py
│       ├── nlp_service.py     # NLP processing
│       ├── progress_tracker.py
│       ├── redis_service.py
│       └── zotero_service.py
├── alembic/                    # Database migrations
│   ├── versions/              # Migration scripts
│   └── env.py
├── uploads/                    # File storage
│   ├── drafts/
│   └── mahasiswa_*/
├── logs/                       # Application logs
├── tests/                      # Test files
│   ├── test_api.py
│   ├── test_jwt.py
│   └── test_indonesian_support.py
├── .env                        # Environment variables (not in git)
├── .env.example               # Environment template
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Docker image
├── alembic.ini               # Alembic configuration
└── README.md
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

### Integration Endpoints

#### Mendeley - Get OAuth URL
```http
GET /api/integration/mendeley/auth-url
Authorization: Bearer {token}
```

#### Mendeley - Handle OAuth Callback
```http
POST /api/integration/mendeley/callback
Authorization: Bearer {token}
Content-Type: application/json

{
  "code": "oauth_code_from_mendeley"
}
```

#### Mendeley - Sync Library
```http
POST /api/integration/mendeley/sync
Authorization: Bearer {token}
```

#### Mendeley - Disconnect
```http
POST /api/integration/mendeley/disconnect
Authorization: Bearer {token}
```

#### Zotero - Configure API
```http
POST /api/integration/zotero/configure
Authorization: Bearer {token}
Content-Type: application/json

{
  "api_key": "your_zotero_api_key",
  "library_id": "your_library_id"
}
```

#### Zotero - Sync Library
```http
POST /api/integration/zotero/sync
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
  "top_k": 10,
  "language": "id"  # "id" untuk Indonesia, "en" untuk English
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

#### Extract References
```http
POST /api/nlp/extract-references
Authorization: Bearer {token}
Content-Type: application/json

{
  "dokumen_id": 1
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

### Pembimbingan System

#### Get Available Dosen
```http
GET /api/dosen/available-dosen?specialization=Machine+Learning
Authorization: Bearer {token}
```

#### Send Guidance Request
```http
POST /api/pembimbing/request
Authorization: Bearer {token}
Content-Type: application/json

{
  "dosen_id": 1,
  "pesan": "Saya tertarik dengan penelitian di bidang NLP..."
}
```

#### Get My Requests (Student)
```http
GET /api/pembimbing/my-requests
Authorization: Bearer {token}
```

#### Get Incoming Requests (Dosen)
```http
GET /api/pembimbing/incoming-requests
Authorization: Bearer {token}
```

#### Respond to Request (Dosen)
```http
PUT /api/pembimbing/request/{request_id}/respond
Authorization: Bearer {token}
Content-Type: application/json

{
  "status": "accepted",  # or "rejected"
  "catatan": "Silakan hubungi saya untuk diskusi lebih lanjut"
}
```

### Google Gemini AI Features

#### Generate Research Gap Analysis
```http
POST /api/nlp/gap-analysis
Authorization: Bearer {token}
Content-Type: application/json

{
  "dokumen_ids": [1, 2, 3],
  "language": "id"  # "id" atau "en"
}
```

Response:
```json
{
  "papers": [
    {
      "title": "Paper Title",
      "author": "Author Name",
      "strength": "Kekuatan penelitian...",
      "limitation": "Keterbatasan penelitian..."
    }
  ],
  "research_opportunities": [
    "Peluang penelitian 1",
    "Peluang penelitian 2"
  ]
}
```

#### Generate Research Ideas
```http
POST /api/nlp/generate-ideas
Authorization: Bearer {token}
Content-Type: application/json

{
  "dokumen_ids": [1, 2, 3],
  "language": "id"
}
```

Response:
```json
{
  "ideas": [
    {
      "title": "Judul Penelitian",
      "description": "Deskripsi lengkap...",
      "methodology": "Metodologi yang disarankan...",
      "expected_contribution": "Kontribusi yang diharapkan..."
    }
  ]
}
```

#### Generate Thesis Outline
```http
POST /api/nlp/thesis-outline
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Judul Penelitian Anda",
  "language": "id"  # "id" atau "en"
}
```

Response:
```json
{
  "bab1": {
    "title": "BAB I PENDAHULUAN",
    "sections": [
      {
        "section": "1.1",
        "title": "Latar Belakang",
        "description": "..."
      }
    ]
  },
  "bab2": { ... },
  "bab3": { ... }
}
```

#### Save Gap Analysis History
```http
POST /api/gap-analysis/save
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Analisis Gap - ML in Healthcare",
  "result": { ... }  # Full gap analysis result
}
```

#### Get Gap Analysis History
```http
GET /api/gap-analysis/list
Authorization: Bearer {token}
```

#### Get Gap Analysis Detail
```http
GET /api/gap-analysis/{history_id}
Authorization: Bearer {token}
```

### Reference Validation

#### Get Student References
```http
GET /api/mahasiswa/references?dokumen_id=1&status=pending
Authorization: Bearer {token}
```

#### Validate Reference (Dosen)
```http
PUT /api/dosen/references/{referensi_id}/validate
Authorization: Bearer {token}
Content-Type: application/json

{
  "is_valid": true,
  "catatan_validasi": "Referensi valid dan relevan"
}
```

### Visualization

#### Get Document Graph
```http
GET /api/visualization/graph?min_similarity=0.3
Authorization: Bearer {token}
```

#### Get Similar Documents
```http
GET /api/visualization/similarity/{dokumen_id}?threshold=0.5
Authorization: Bearer {token}
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `POSTGRES_USER` | PostgreSQL username | `admin` | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQL password | - | ✅ |
| `POSTGRES_DB` | Database name | `reference_system` | ✅ |
| `DATABASE_URL` | Full database connection URL | - | ✅ |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` | ✅ |
| `SECRET_KEY` | JWT secret key (CHANGE IN PRODUCTION!) | - | ✅ |
| `ALGORITHM` | JWT algorithm | `HS256` | ✅ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | `30` | ✅ |
| `MENDELEY_CLIENT_ID` | Mendeley app ID | - | For Mendeley integration |
| `MENDELEY_CLIENT_SECRET` | Mendeley app secret | - | For Mendeley integration |
| `MENDELEY_REDIRECT_URI` | OAuth callback URL | - | For Mendeley integration |
| `GOOGLE_API_KEY` | Google Gemini API key for AI features | - | ✅ Required for AI features |
| `FRONTEND_URL` | Frontend application URL | `http://localhost:3000` | ✅ |
| `CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` | ✅ |
| `DEBUG` | Debug mode | `False` | ❌ |

### Google Gemini API Setup

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **Get API Key** or **Create API Key**
3. Select or create a Google Cloud project
4. Copy the generated API key
5. Add to `.env` file:
   ```env
   GOOGLE_API_KEY=AIzaSy...your-api-key-here
   ```

**Features Enabled with Gemini API:**
- ✅ Research Gap Analysis with multiple documents
- ✅ AI-powered Research Idea Generator
- ✅ Automatic Thesis Outline Generation (Bab 1-3)
- ✅ Indonesian & English language support
- ✅ Context-aware content generation

**Model Used:** `gemini-2.5-flash`
- Fast response times (<2 seconds)
- Cost-effective for academic use
- High-quality Indonesian text generation
- Supports up to 32K tokens context

**Free Tier:**
- 60 requests per minute
- 1,500 requests per day
- 1 million tokens per day

For more information: [Google AI Documentation](https://ai.google.dev/)

### Mendeley OAuth Setup

1. Register your application at [Mendeley Developers](https://dev.mendeley.com/myapps.html)
2. Set redirect URI to: `http://localhost:8000/api/mendeley/oauth/callback`
3. Copy **App ID** (not Client ID) to `MENDELEY_CLIENT_ID`
4. Copy **Client Secret** to `MENDELEY_CLIENT_SECRET`

For detailed guide, see: [MENDELEY_OAUTH_GUIDE.md](MENDELEY_OAUTH_GUIDE.md)

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# View migration history
alembic history
```

## 🚀 Deployment

### Docker Production

```bash
# Build production image
docker build -f Dockerfile -t refero-backend:latest .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run with Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or with Uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Production Checklist

- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=False`
- [ ] Use strong database passwords
- [ ] Configure proper CORS origins
- [ ] Setup SSL/TLS certificates
- [ ] Configure email service for notifications
- [ ] Setup backup strategy for database
- [ ] Configure logging and monitoring
- [ ] Setup Redis password protection
- [ ] Use environment-specific `.env` files

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app --cov-report=html

# Run specific test module
pytest tests/test_api.py -v

# Run tests with markers
pytest -m "slow"  # Only slow tests
pytest -m "not slow"  # Skip slow tests
```

## 📝 Development Guidelines

### Code Style

```bash
# Format code with black
black app/

# Sort imports
isort app/

# Type checking
mypy app/

# Linting
flake8 app/
```

### Adding New Endpoints

1. Create route in `app/api/your_endpoint.py`
2. Define schemas in `app/schemas/`
3. Add business logic in `app/services/`
4. Update models if needed in `app/models/`
5. Create tests in `tests/`
6. Update this README with endpoint documentation

## 🐛 Troubleshooting

### Common Issues

**Database connection error**
```bash
# Check PostgreSQL is running
docker-compose ps

# Check connection settings in .env
# Ensure DATABASE_URL is correct
```

**Redis connection error**
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Or with Docker
docker-compose exec redis redis-cli ping
```

**NLP model download issues**
```bash
# Manually download spaCy model
python -m spacy download en_core_web_sm

# Or install from requirements
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0-py3-none-any.whl
```

**Mendeley OAuth errors**
- Ensure you're using **App ID** (21567) not Client ID
- Check redirect URI matches exactly
- See [MENDELEY_FIX_AUTH_ERROR.md](MENDELEY_FIX_AUTH_ERROR.md)

**File upload issues**
```bash
# Check uploads directory exists and has proper permissions
mkdir -p uploads/drafts
chmod 755 uploads
```

## 📖 Additional Documentation

- [Quick Start Migration Guide](QUICK_START_MIGRASI.md)
- [Mendeley OAuth Guide](MENDELEY_OAUTH_GUIDE.md)
- [Indonesian Language Support](INDONESIAN_SUPPORT.md)
- [Environment Setup Fix](ENVIRONMENT_FIX.md)
- [Migration Guide](MIGRATION_GUIDE.md)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 License

This project is part of a capstone project at Telkom University.

## 👥 Team

**Capstone Keramik Berkah Group**
- Backend Development
- NLP Integration
- System Architecture

## 🙏 Acknowledgments

- FastAPI framework and community
- Hugging Face for NLP models
- Mendeley API documentation
- Telkom University

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Contact: dhimmas@student.telkomuniversity.ac.id

---

**Refero** - Making academic reference management smarter with AI 🚀

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

### Tables
- `users` - User accounts
- `mahasiswa` - Student profiles
- `dosen` - Lecturer profiles
- `dokumen` - Documents/references
- `tag` - Document tags
- `kata_kunci` - Keywords
- `referensi` - References
- `catatan` - Lecturer notes
- `document_similarity` - Similarity scores

### Relationships
- User → Mahasiswa/Dosen (1:1)
- Mahasiswa → Dokumen (1:N)
- Dokumen ↔ Tag (N:M)
- Dokumen ↔ KataKunci (N:M)
- Dokumen → Referensi (1:N)

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

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Upload
MAX_FILE_SIZE_MB=10
ALLOWED_EXTENSIONS=pdf,docx

# NLP Models
SUMMARIZATION_MODEL=facebook/bart-large-cnn
KEYWORD_EXTRACTION_MODEL=all-MiniLM-L6-v2
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/           # API endpoints
│   │   ├── auth.py
│   │   ├── documents.py
│   │   ├── nlp.py
│   │   ├── users.py
│   │   └── visualization.py
│   ├── core/          # Core configurations
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── models/        # SQLAlchemy models
│   │   └── models.py
│   ├── schemas/       # Pydantic schemas
│   │   ├── user_schemas.py
│   │   └── document_schemas.py
│   ├── services/      # Business logic
│   │   └── nlp_service.py
│   └── main.py        # FastAPI application
├── uploads/           # Uploaded files
├── logs/              # Application logs
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
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
