from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, documents, users, nlp, visualization, dosen, pembimbing, mendeley

# Create uploads directory if not exists
os.makedirs("uploads", exist_ok=True)
os.makedirs("logs", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting up Reference Management System...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
    
    yield
    
    # Shutdown
    print("👋 Shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="Reference Management System API",
    description="API untuk sistem pengelolaan dan analisis hubungan antar referensi ilmiah",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(nlp.router, prefix="/api/nlp", tags=["NLP Processing"])
app.include_router(visualization.router, prefix="/api/visualization", tags=["Visualization"])
app.include_router(dosen.router, prefix="/api/dosen", tags=["Dosen"])
app.include_router(pembimbing.router, prefix="/api/pembimbing", tags=["Pembimbing Requests"])
app.include_router(mendeley.router, prefix="/api/mendeley", tags=["Mendeley Integration"])


@app.get("/")
async def root():
    return {
        "message": "Reference Management System API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
