FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    # Runtime libs needed by Pillow/ImageCaptcha
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and increase timeout
RUN pip install --upgrade pip

# Install Python dependencies with increased timeout and retries
# Split heavy packages to avoid timeout
RUN pip install --default-timeout=1000 --retries 5 \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.5.3 \
    pydantic-settings==2.1.0 \
    pydantic[email]==2.5.3

RUN pip install --default-timeout=1000 --retries 5 \
    sqlalchemy==2.0.25 \
    alembic==1.13.1 \
    psycopg2-binary==2.9.9 \
    redis==5.0.1

RUN pip install --default-timeout=1000 --retries 5 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4 \
    python-multipart==0.0.6 \
    bcrypt==4.1.2

# Install PyTorch CPU version (lighter)
RUN pip install --default-timeout=1000 --retries 5 \
    torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu

# Install transformers and NLP tools
RUN pip install --default-timeout=1000 --retries 5 \
    transformers==4.36.2 \
    spacy==3.7.2 \
    scikit-learn==1.4.0 \
    nltk==3.8.1 \
    sentence-transformers==2.3.1 \
    keybert==0.8.4 \
    accelerate==0.25.0

# Install document processing
RUN pip install --default-timeout=1000 --retries 5 \
    PyPDF2==3.0.1 \
    pdfplumber==0.10.3 \
    python-docx==1.1.0 \
    pymupdf

# Install remaining dependencies
RUN pip install --default-timeout=1000 --retries 5 \
    python-dotenv==1.0.0 \
    aiofiles==23.2.1 \
    pillow==10.2.0 \
    captcha==0.5.0 \
    pytest==7.4.4 \
    pytest-asyncio==0.23.3 \
    httpx==0.26.0

# Ensure all deps from requirements.txt are installed (safety net)
RUN pip install --default-timeout=1000 --retries 5 --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for file storage
RUN mkdir -p /app/uploads /app/logs

# Expose port
EXPOSE 8000

# Create startup script
RUN echo '#!/bin/bash\n\
# Download spaCy model if not exists\n\
python -m spacy download en_core_web_sm 2>/dev/null || echo "spaCy model already installed or will be downloaded on first use"\n\
\n\
# Start application\n\
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload\n\
' > /app/start.sh && chmod +x /app/start.sh

# Command to run the application
CMD ["/app/start.sh"]
