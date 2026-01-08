from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "Reference Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql://admin:admin123@db:5432/reference_system"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # API Settings
    GOOGLE_API_KEY: str = "AIzaSyBlguqa3reXkZ99"
    
    # Security
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx"]
    UPLOAD_DIR: str = "uploads"
    
    # NLP Models
    SUMMARIZATION_MODEL: str = "facebook/bart-large-cnn"
    KEYWORD_EXTRACTION_MODEL: str = "all-MiniLM-L6-v2"
    
    # Email Configuration
    # Pilih provider: "gmail", "outlook", "office365" (untuk domain ac.id)
    MAIL_PROVIDER: str = "office365"  # Ganti ke office365 untuk Telkom University
    
    # Gmail Configuration
    GMAIL_USERNAME: str = "ariateja1973@gmail.com"
    GMAIL_PASSWORD: str = "doou wzju swmp zpmz"  # App Password
    GMAIL_FROM: str = "ariateja1973@gmail.com"
    
    # Outlook Configuration
    OUTLOOK_USERNAME: str = "ariateja1973@gmail.com"  # Email Telkom Anda
    OUTLOOK_PASSWORD: str = "9XAVF-SHDBC-LVPB9-QTXPF-9JHZ7"  # 16-char App Password dari Step 1
    OUTLOOK_FROM: str = "dhimmas@student.telkomuniversity.ac.id"
    
    # Common Email Settings (auto-configured based on provider)
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = ""
    MAIL_FROM_NAME: str = "Reference Management System"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True
    
    # Verification
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 15
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-configure based on provider
        self.configure_email_provider()
    
    def configure_email_provider(self):
        """Configure email settings based on selected provider"""
        provider = self.MAIL_PROVIDER.lower()
        
        if provider == "gmail":
            self.MAIL_USERNAME = self.GMAIL_USERNAME
            self.MAIL_PASSWORD = self.GMAIL_PASSWORD
            self.MAIL_FROM = self.GMAIL_FROM
            self.MAIL_SERVER = "smtp.gmail.com"
            self.MAIL_PORT = 587
            self.MAIL_STARTTLS = True
            self.MAIL_SSL_TLS = False
            print("📧 Email Provider: Gmail")
        
        
        elif provider == "outlook":
            self.MAIL_USERNAME = self.OUTLOOK_USERNAME or "your-email@university.ac.id"
            self.MAIL_PASSWORD = self.OUTLOOK_PASSWORD or "your-password"
            self.MAIL_FROM = self.OUTLOOK_FROM or self.MAIL_USERNAME
            self.MAIL_SERVER = "smtp.office365.com"
            self.MAIL_PORT = 587
            self.MAIL_STARTTLS = True
            self.MAIL_SSL_TLS = False
            print("📧 Email Provider: Outlook (ac.id domain)")
        
        else:
            print(f"⚠️ Unknown provider '{provider}', using Gmail as fallback")
            self.MAIL_USERNAME = self.GMAIL_USERNAME
            self.MAIL_PASSWORD = self.GMAIL_PASSWORD
            self.MAIL_FROM = self.GMAIL_FROM
            self.MAIL_SERVER = "smtp.gmail.com"
            self.MAIL_PORT = 587
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Ignore extra attributes from .env
        extra = "ignore"


settings = Settings()
