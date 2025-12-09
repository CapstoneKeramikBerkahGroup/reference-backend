from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
import json
import os
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.models import Dokumen, Referensi, Mahasiswa, MendeleyToken
from app.api.auth import get_current_mahasiswa
from app.services.mendeley_service import mendeley_service

router = APIRouter()


def parse_bibtex_entry(entry):
    """Parse a single BibTeX entry into our referensi format"""
    referensi_data = {
        'teks_referensi': '',
        'penulis': '',
        'tahun': '',
        'judul_publikasi': ''
    }
    
    # Extract author
    if 'author' in entry:
        referensi_data['penulis'] = entry['author']
    
    # Extract year
    if 'year' in entry:
        referensi_data['tahun'] = entry['year']
    
    # Extract title/publication
    if 'title' in entry:
        referensi_data['judul_publikasi'] = entry['title']
    
    # Build full reference text
    parts = []
    if referensi_data['penulis']:
        parts.append(referensi_data['penulis'])
    if referensi_data['tahun']:
        parts.append(f"({referensi_data['tahun']})")
    if referensi_data['judul_publikasi']:
        parts.append(referensi_data['judul_publikasi'])
    
    # Add journal/booktitle if available
    if 'journal' in entry:
        parts.append(f"In: {entry['journal']}")
    elif 'booktitle' in entry:
        parts.append(f"In: {entry['booktitle']}")
    
    # Add volume, pages, etc.
    if 'volume' in entry:
        parts.append(f"Vol. {entry['volume']}")
    if 'pages' in entry:
        parts.append(f"pp. {entry['pages']}")
    if 'publisher' in entry:
        parts.append(entry['publisher'])
    if 'doi' in entry:
        parts.append(f"DOI: {entry['doi']}")
    
    referensi_data['teks_referensi'] = '. '.join(parts)
    
    return referensi_data


def parse_ris_entry(line_dict):
    """Parse RIS format entry into our referensi format"""
    referensi_data = {
        'teks_referensi': '',
        'penulis': '',
        'tahun': '',
        'judul_publikasi': ''
    }
    
    # RIS format mapping
    if 'AU' in line_dict or 'A1' in line_dict:
        authors = line_dict.get('AU', []) or line_dict.get('A1', [])
        if isinstance(authors, list):
            referensi_data['penulis'] = ', '.join(authors)
        else:
            referensi_data['penulis'] = authors
    
    if 'PY' in line_dict or 'Y1' in line_dict:
        year = line_dict.get('PY') or line_dict.get('Y1')
        if isinstance(year, list):
            year = year[0]
        # Extract year from YYYY/MM/DD format
        if '/' in str(year):
            year = str(year).split('/')[0]
        referensi_data['tahun'] = str(year)
    
    if 'TI' in line_dict or 'T1' in line_dict:
        title = line_dict.get('TI') or line_dict.get('T1')
        if isinstance(title, list):
            title = ' '.join(title)
        referensi_data['judul_publikasi'] = title
    
    # Build full reference text
    parts = []
    if referensi_data['penulis']:
        parts.append(referensi_data['penulis'])
    if referensi_data['tahun']:
        parts.append(f"({referensi_data['tahun']})")
    if referensi_data['judul_publikasi']:
        parts.append(referensi_data['judul_publikasi'])
    
    # Add journal
    if 'JO' in line_dict or 'T2' in line_dict:
        journal = line_dict.get('JO') or line_dict.get('T2')
        if isinstance(journal, list):
            journal = journal[0]
        parts.append(f"In: {journal}")
    
    # Add volume and pages
    if 'VL' in line_dict:
        vol = line_dict['VL']
        if isinstance(vol, list):
            vol = vol[0]
        parts.append(f"Vol. {vol}")
    
    if 'SP' in line_dict:
        pages = line_dict['SP']
        if isinstance(pages, list):
            pages = pages[0]
        if 'EP' in line_dict:
            ep = line_dict['EP']
            if isinstance(ep, list):
                ep = ep[0]
            pages = f"{pages}-{ep}"
        parts.append(f"pp. {pages}")
    
    if 'PB' in line_dict:
        pub = line_dict['PB']
        if isinstance(pub, list):
            pub = pub[0]
        parts.append(pub)
    
    if 'DO' in line_dict:
        doi = line_dict['DO']
        if isinstance(doi, list):
            doi = doi[0]
        parts.append(f"DOI: {doi}")
    
    referensi_data['teks_referensi'] = '. '.join(parts)
    
    return referensi_data


def parse_ris_file(content: str):
    """Parse RIS file content"""
    entries = []
    current_entry = {}
    
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('TY  -'):
            # Start of new entry
            if current_entry:
                entries.append(current_entry)
            current_entry = {}
        elif line.startswith('ER  -'):
            # End of entry
            if current_entry:
                entries.append(current_entry)
                current_entry = {}
        elif '  -' in line:
            # Parse tag and value
            tag, value = line.split('  -', 1)
            tag = tag.strip()
            value = value.strip()
            
            if tag in current_entry:
                if isinstance(current_entry[tag], list):
                    current_entry[tag].append(value)
                else:
                    current_entry[tag] = [current_entry[tag], value]
            else:
                current_entry[tag] = value
    
    # Add last entry if exists
    if current_entry:
        entries.append(current_entry)
    
    return [parse_ris_entry(entry) for entry in entries]


@router.post("/import-mendeley/{dokumen_id}")
async def import_mendeley_references(
    dokumen_id: int,
    file: UploadFile = File(...),
    current_mahasiswa: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """
    Import references from Mendeley export file (BibTeX or RIS format)
    """
    
    # Verify document belongs to current mahasiswa
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_mahasiswa.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check file extension
    filename = file.filename.lower()
    if not (filename.endswith('.bib') or filename.endswith('.ris')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload .bib or .ris file from Mendeley"
        )
    
    try:
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        parsed_refs = []
        
        if filename.endswith('.bib'):
            # Parse BibTeX
            parser = BibTexParser(common_strings=True)
            parser.customization = convert_to_unicode
            bib_database = bibtexparser.loads(content_str, parser=parser)
            
            for entry in bib_database.entries:
                parsed_refs.append(parse_bibtex_entry(entry))
        
        elif filename.endswith('.ris'):
            # Parse RIS
            parsed_refs = parse_ris_file(content_str)
        
        if not parsed_refs:
            raise HTTPException(
                status_code=400,
                detail="No valid references found in the file"
            )
        
        # Delete existing references for this document
        db.query(Referensi).filter(Referensi.dokumen_id == dokumen_id).delete()
        
        # Insert new references
        imported_count = 0
        for idx, ref_data in enumerate(parsed_refs, start=1):
            if ref_data['teks_referensi']:  # Only import if we have content
                new_ref = Referensi(
                    dokumen_id=dokumen_id,
                    teks_referensi=ref_data['teks_referensi'],
                    penulis=ref_data['penulis'],
                    tahun=ref_data['tahun'],
                    judul_publikasi=ref_data['judul_publikasi'],
                    nomor=idx,
                    status_validasi='pending'
                )
                db.add(new_ref)
                imported_count += 1
        
        db.commit()
        
        return {
            "message": f"Successfully imported {imported_count} references from Mendeley",
            "total_imported": imported_count,
            "file_type": "BibTeX" if filename.endswith('.bib') else "RIS"
        }
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Unable to read file. Please ensure it's a valid text file"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )


@router.get("/export-guide")
async def get_mendeley_export_guide():
    """
    Get instructions on how to export references from Mendeley
    """
    return {
        "title": "How to Export References from Mendeley",
        "steps": [
            {
                "step": 1,
                "title": "Open Mendeley Desktop",
                "description": "Launch your Mendeley Desktop application"
            },
            {
                "step": 2,
                "title": "Select References",
                "description": "Select the references you want to export (or select all with Ctrl+A)"
            },
            {
                "step": 3,
                "title": "Export",
                "description": "Go to File → Export... or right-click and select 'Export'"
            },
            {
                "step": 4,
                "title": "Choose Format",
                "description": "Select 'BibTeX (*.bib)' or 'RIS (*.ris)' as the export format"
            },
            {
                "step": 5,
                "title": "Save File",
                "description": "Save the file to your computer"
            },
            {
                "step": 6,
                "title": "Upload Here",
                "description": "Upload the exported file to import your references"
            }
        ],
        "supported_formats": ["BibTeX (.bib)", "RIS (.ris)"],
        "note": "All existing references for this document will be replaced with the imported ones"
    }


# OAuth Endpoints

@router.get("/oauth/authorize")
async def mendeley_oauth_authorize(
    dokumen_id: Optional[int] = Query(None, description="Optional: Document ID to sync references to"),
    current_user: Mahasiswa = Depends(get_current_mahasiswa)
):
    """
    Start Mendeley OAuth authorization flow
    Redirects user to Mendeley login page
    
    If dokumen_id is provided: sync references to specific document
    If dokumen_id is None: import all papers from Mendeley as new documents
    """
    # Store user_id and optional dokumen_id in state
    state = f"{current_user.id}:{dokumen_id or 'all'}:{datetime.utcnow().timestamp()}"
    
    authorization_url, _ = mendeley_service.get_authorization_url(state=state)
    
    return JSONResponse({
        "authorization_url": authorization_url,
        "message": "Please visit this URL to authorize access to your Mendeley library"
    })


@router.get("/oauth/callback")
async def mendeley_oauth_callback(
    code: str = Query(..., description="Authorization code from Mendeley"),
    state: str = Query(..., description="State parameter for verification"),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Mendeley
    Exchange code for access token and sync library
    """
    try:
        # Parse state to get user_id and dokumen_id
        parts = state.split(':')
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        user_id = int(parts[0])
        dokumen_id_str = parts[1]
        
        # Get access token
        token_data = mendeley_service.get_access_token(code)
        
        # Get frontend URL from environment or use default
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        
        if dokumen_id_str == 'all':
            # Store token for future use
            # Check if token exists
            existing_token = db.query(MendeleyToken).filter(
                MendeleyToken.mahasiswa_id == user_id
            ).first()
            
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)  # Mendeley tokens typically expire in 1 hour
            
            if existing_token:
                # Update existing token
                existing_token.access_token = token_data['access_token']
                existing_token.refresh_token = token_data.get('refresh_token')
                existing_token.expires_at = expires_at
                existing_token.updated_at = datetime.now(timezone.utc)
            else:
                # Create new token
                new_token = MendeleyToken(
                    mahasiswa_id=user_id,
                    access_token=token_data['access_token'],
                    refresh_token=token_data.get('refresh_token'),
                    expires_at=expires_at
                )
                db.add(new_token)
            
            db.commit()
            
            # Import all papers from Mendeley as new documents
            result = mendeley_service.import_all_papers(
                token_data['access_token'],
                user_id,
                db
            )
            
            # Redirect to dashboard with success message
            return RedirectResponse(
                url=f"{frontend_url}/mahasiswa/dashboard?mendeley_sync=success&imported={result['imported_count']}"
            )
        else:
            # Sync to specific document
            dokumen_id = int(dokumen_id_str)
            
            # Verify document belongs to user
            dokumen = db.query(Dokumen).filter(
                Dokumen.id == dokumen_id,
                Dokumen.mahasiswa_id == user_id
            ).first()
            
            if not dokumen:
                raise HTTPException(status_code=404, detail="Document not found or access denied")
            
            # Sync library
            result = mendeley_service.sync_library(
                token_data['access_token'],
                dokumen_id,
                db
            )
            
            # Redirect to document page with success message
            return RedirectResponse(
                url=f"{frontend_url}/mahasiswa/documents/{dokumen_id}?mendeley_sync=success&imported={result['imported_count']}"
            )
        
    except Exception as e:
        # Get frontend URL from environment or use default
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"{frontend_url}/mahasiswa/dashboard?mendeley_sync=error&message={str(e)}"
        )


@router.post("/sync/{dokumen_id}")
async def sync_mendeley_library(
    dokumen_id: int,
    access_token: str = Query(..., description="Mendeley OAuth access token"),
    current_user: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """
    Manually sync Mendeley library with existing access token
    """
    # Verify document belongs to user
    dokumen = db.query(Dokumen).filter(
        Dokumen.id == dokumen_id,
        Dokumen.mahasiswa_id == current_user.id
    ).first()
    
    if not dokumen:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        result = mendeley_service.sync_library(access_token, dokumen_id, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sync failed: {str(e)}")


@router.get("/test-connection")
async def test_mendeley_connection(
    access_token: str = Query(..., description="Mendeley OAuth access token")
):
    """
    Test Mendeley API connection and get user profile
    """
    try:
        profile = mendeley_service.get_user_profile(access_token)
        return {
            "status": "connected",
            "user": {
                "id": profile.get('id'),
                "first_name": profile.get('first_name'),
                "last_name": profile.get('last_name'),
                "email": profile.get('email'),
                "display_name": profile.get('display_name')
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")


@router.get("/status")
async def get_mendeley_status(
    current_user: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """
    Check if user has connected Mendeley account
    """
    token = db.query(MendeleyToken).filter(
        MendeleyToken.mahasiswa_id == current_user.id
    ).first()
    
    if not token:
        return {
            "connected": False,
            "message": "Mendeley not connected"
        }
    
    # Check if token is expired
    is_expired = token.expires_at and token.expires_at < datetime.now(timezone.utc)
    
    return {
        "connected": True,
        "expired": is_expired,
        "connected_at": token.created_at.isoformat() if token.created_at else None,
        "last_sync": token.updated_at.isoformat() if token.updated_at else None
    }


@router.post("/refresh")
async def refresh_mendeley_sync(
    current_user: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """
    Manually refresh/sync papers from Mendeley
    """
    # Get stored token
    token = db.query(MendeleyToken).filter(
        MendeleyToken.mahasiswa_id == current_user.id
    ).first()
    
    if not token:
        raise HTTPException(status_code=400, detail="Mendeley not connected. Please connect first.")
    
    # Check if token is expired
    if token.expires_at and token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired. Please reconnect to Mendeley.")
    
    try:
        # Import papers
        result = mendeley_service.import_all_papers(
            token.access_token,
            current_user.id,
            db
        )
        
        # Update last sync time
        token.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        return {
            "status": "success",
            "imported": result['imported_count'],
            "total": result['total_documents'],
            "message": result['message']
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sync failed: {str(e)}")


@router.post("/disconnect")
async def disconnect_mendeley(
    current_user: Mahasiswa = Depends(get_current_mahasiswa),
    db: Session = Depends(get_db)
):
    """
    Disconnect Mendeley account
    """
    token = db.query(MendeleyToken).filter(
        MendeleyToken.mahasiswa_id == current_user.id
    ).first()
    
    if token:
        db.delete(token)
        db.commit()
    
    return {
        "status": "success",
        "message": "Mendeley disconnected"
    }


@router.get("/check-config")
async def check_mendeley_config():
    """
    Check if Mendeley OAuth is configured correctly
    Public endpoint - no auth required
    """
    import os
    
    client_id = os.getenv('MENDELEY_CLIENT_ID', '')
    client_secret = os.getenv('MENDELEY_CLIENT_SECRET', '')
    redirect_uri = os.getenv('MENDELEY_REDIRECT_URI', '')
    
    is_configured = (
        client_id and 
        client_id != 'your_client_id_here' and
        client_secret and 
        client_secret != 'your_client_secret_here'
    )
    
    return {
        "configured": is_configured,
        "client_id_set": bool(client_id and client_id != 'your_client_id_here'),
        "client_secret_set": bool(client_secret and client_secret != 'your_client_secret_here'),
        "redirect_uri": redirect_uri,
        "redirect_uri_correct": redirect_uri == 'http://localhost:8000/api/mendeley/oauth/callback',
        "message": "✅ Mendeley OAuth configured correctly" if is_configured else "❌ Please configure Mendeley credentials in .env",
        "help": "See MENDELEY_FIX_AUTH_ERROR.md for setup instructions" if not is_configured else None
    }
