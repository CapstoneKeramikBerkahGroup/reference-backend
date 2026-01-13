from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, Base
# Import routers dengan benar
from app.api import auth, documents, users, nlp, visualization, dosen, pembimbing, mendeley, integration, gap_analysis, drafts

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

# CORS Middleware - Must be added before routes
# Allow specific origins for proper CORS support
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(nlp.router, prefix="/api/nlp", tags=["NLP Processing"])
app.include_router(visualization.router, prefix="/api/visualization", tags=["Visualization"])
app.include_router(dosen.router, prefix="/api/dosen", tags=["Dosen"])
app.include_router(pembimbing.router, prefix="/api/pembimbing", tags=["Pembimbing Requests"])
app.include_router(mendeley.router, prefix="/api/mendeley", tags=["Mendeley Integration"])
app.include_router(integration.router, prefix="/api/integration", tags=["Zotero Integration"])
app.include_router(gap_analysis.router, prefix="/api/gap-analysis", tags=["Gap Analysis"])
app.include_router(drafts.router, prefix="/api/drafts", tags=["Drafting"])

# Custom routes for file serving with proper CORS
@app.options("/uploads/{file_path:path}")
async def uploads_options(file_path: str):
    """Handle CORS preflight for uploads"""
    from fastapi import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

@app.get("/uploads/{file_path:path}")
async def serve_uploaded_file(file_path: str, request: Request):
    """Serve uploaded files with CORS headers"""
    from fastapi import HTTPException, Response
    
    print(f"🔍 Serving file: {file_path}")
    
    full_path = Path("uploads") / file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Read file content
    with open(full_path, "rb") as f:
        content = f.read()
    
    # Determine media type
    media_type = "application/pdf" if file_path.endswith('.pdf') else "application/octet-stream"
    
    print(f"✅ Sending file with CORS headers: {len(content)} bytes")
    
    # Create response with explicit CORS headers
    response = Response(
        content=content,
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cache-Control": "public, max-age=3600",
        }
    )
    
    return response

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