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

# Upgrade pip first
RUN pip install --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .

# Install all Python dependencies from requirements.txt
RUN pip install --no-cache-dir --default-timeout=1000 --retries 5 -r requirements.txt

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
