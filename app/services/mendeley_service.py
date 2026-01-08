"""
Mendeley OAuth and Library Sync Service
Handles authentication and synchronization with Mendeley API
"""
import os
import requests
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient

# Mendeley API Configuration
MENDELEY_CLIENT_ID = os.getenv('MENDELEY_CLIENT_ID', '')
MENDELEY_CLIENT_SECRET = os.getenv('MENDELEY_CLIENT_SECRET', '')
MENDELEY_REDIRECT_URI = os.getenv('MENDELEY_REDIRECT_URI', 'http://localhost:8000/api/mendeley/oauth/callback')

# Mendeley API Endpoints
MENDELEY_AUTH_URL = 'https://api.mendeley.com/oauth/authorize'
MENDELEY_TOKEN_URL = 'https://api.mendeley.com/oauth/token'
MENDELEY_API_BASE = 'https://api.mendeley.com'


class MendeleyService:
    """Service for Mendeley API integration"""
    
    def __init__(self):
        self.client_id = MENDELEY_CLIENT_ID
        self.client_secret = MENDELEY_CLIENT_SECRET
        self.redirect_uri = MENDELEY_REDIRECT_URI
    
    def get_authorization_url(self, state: str = None) -> tuple:
        """
        Generate Mendeley OAuth authorization URL
        Returns: (authorization_url, state)
        """
        oauth = OAuth2Session(
            self.client_id,
            redirect_uri=self.redirect_uri,
            scope=['all']
        )
        
        authorization_url, state = oauth.authorization_url(
            MENDELEY_AUTH_URL,
            state=state
        )
        
        return authorization_url, state
    
    def get_access_token(self, authorization_code: str) -> Dict:
        """
        Exchange authorization code for access token
        """
        # Mendeley requires Basic Auth for token exchange
        from requests.auth import HTTPBasicAuth
        
        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.redirect_uri
        }
        
        response = requests.post(
            MENDELEY_TOKEN_URL,
            data=data,
            auth=HTTPBasicAuth(self.client_id, self.client_secret)
        )
        
        response.raise_for_status()
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh expired access token
        """
        oauth = OAuth2Session(self.client_id)
        
        token = oauth.refresh_token(
            MENDELEY_TOKEN_URL,
            refresh_token=refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        return token
    
    def get_user_profile(self, access_token: str) -> Dict:
        """
        Get Mendeley user profile information
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.mendeley-document.1+json'
        }
        
        response = requests.get(
            f'{MENDELEY_API_BASE}/profiles/me',
            headers=headers
        )
        
        response.raise_for_status()
        return response.json()
    
    def get_documents(self, access_token: str, limit: int = 100, view: str = 'all') -> List[Dict]:
        """
        Get documents from Mendeley library
        
        Args:
            access_token: OAuth access token
            limit: Number of documents to retrieve (max 500)
            view: View type ('bib', 'client', 'all', 'core')
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.mendeley-document.1+json'
        }
        
        params = {
            'limit': min(limit, 500),
            'view': view
        }
        
        response = requests.get(
            f'{MENDELEY_API_BASE}/documents',
            headers=headers,
            params=params
        )
        
        response.raise_for_status()
        return response.json()
    
    def get_document_by_id(self, access_token: str, document_id: str) -> Dict:
        """
        Get specific document from Mendeley by ID
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.mendeley-document.1+json'
        }
        
        response = requests.get(
            f'{MENDELEY_API_BASE}/documents/{document_id}',
            headers=headers
        )
        
        response.raise_for_status()
        return response.json()
    
    def get_folders(self, access_token: str) -> List[Dict]:
        """
        Get folders from Mendeley library
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.mendeley-folder.1+json'
        }
        
        response = requests.get(
            f'{MENDELEY_API_BASE}/folders',
            headers=headers
        )
        
        response.raise_for_status()
        return response.json()
    
    def get_folder_documents(self, access_token: str, folder_id: str) -> List[Dict]:
        """
        Get documents from specific folder
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.mendeley-document.1+json'
        }
        
        response = requests.get(
            f'{MENDELEY_API_BASE}/folders/{folder_id}/documents',
            headers=headers
        )
        
        response.raise_for_status()
        return response.json()
    
    def get_document_files(self, access_token: str, document_id: str) -> List[Dict]:
        """
        Get files attached to a document
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.mendeley-file.1+json'
        }
        
        response = requests.get(
            f'{MENDELEY_API_BASE}/documents/{document_id}/files',
            headers=headers
        )
        
        if response.status_code == 404:
            return []  # No files attached
            
        response.raise_for_status()
        return response.json()
    
    def download_file(self, access_token: str, file_id: str, save_path: str) -> bool:
        """
        Download a file from Mendeley
        
        Args:
            access_token: OAuth access token
            file_id: Mendeley file ID
            save_path: Local path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            response = requests.get(
                f'{MENDELEY_API_BASE}/files/{file_id}',
                headers=headers,
                stream=True
            )
            
            response.raise_for_status()
            
            # Save file
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True
            
        except Exception as e:
            print(f"Error downloading file {file_id}: {str(e)}")
            return False
    
    def parse_mendeley_document(self, doc: Dict) -> Dict:
        """
        Parse Mendeley document format to our referensi format
        """
        # Extract authors
        authors = []
        if 'authors' in doc:
            for author in doc['authors']:
                name_parts = []
                if 'first_name' in author:
                    name_parts.append(author['first_name'])
                if 'last_name' in author:
                    name_parts.append(author['last_name'])
                if name_parts:
                    authors.append(' '.join(name_parts))
        
        penulis = ', '.join(authors) if authors else ''
        
        # Extract year
        tahun = ''
        if 'year' in doc:
            tahun = str(doc['year'])
        
        # Extract title
        judul_publikasi = doc.get('title', '')
        
        # Build full reference text
        parts = []
        
        if penulis:
            parts.append(penulis)
        
        if tahun:
            parts.append(f"({tahun})")
        
        if judul_publikasi:
            parts.append(judul_publikasi)
        
        # Add publication details
        if 'source' in doc:
            parts.append(f"In: {doc['source']}")
        
        if 'volume' in doc:
            parts.append(f"Vol. {doc['volume']}")
        
        if 'issue' in doc:
            parts.append(f"Issue {doc['issue']}")
        
        if 'pages' in doc:
            parts.append(f"pp. {doc['pages']}")
        
        if 'publisher' in doc:
            parts.append(doc['publisher'])
        
        if 'doi' in doc:
            parts.append(f"DOI: {doc['doi']}")
        
        if 'pmid' in doc:
            parts.append(f"PMID: {doc['pmid']}")
        
        teks_referensi = '. '.join(parts)
        
        return {
            'teks_referensi': teks_referensi,
            'penulis': penulis,
            'tahun': tahun,
            'judul_publikasi': judul_publikasi,
            'mendeley_id': doc.get('id', ''),
            'mendeley_type': doc.get('type', ''),
            'mendeley_link': doc.get('link', '')
        }
    
    def sync_library(self, access_token: str, dokumen_id: int, db_session) -> Dict:
        """
        Sync entire Mendeley library to document references
        """
        from app.models import Referensi
        
        # Get all documents from Mendeley
        mendeley_docs = self.get_documents(access_token, limit=500)
        
        if not mendeley_docs:
            return {
                'status': 'error',
                'message': 'No documents found in Mendeley library'
            }
        
        # Delete existing references
        db_session.query(Referensi).filter(
            Referensi.dokumen_id == dokumen_id
        ).delete()
        
        # Parse and insert new references
        imported_count = 0
        for idx, mendeley_doc in enumerate(mendeley_docs, start=1):
            try:
                ref_data = self.parse_mendeley_document(mendeley_doc)
                
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
                    db_session.add(new_ref)
                    imported_count += 1
            except Exception as e:
                print(f"Error parsing document {mendeley_doc.get('id', 'unknown')}: {str(e)}")
                continue
        
        db_session.commit()
        
        return {
            'status': 'success',
            'total_documents': len(mendeley_docs),
            'imported_count': imported_count,
            'message': f'Successfully synced {imported_count} references from Mendeley'
        }
    
    def import_all_papers(self, access_token: str, mahasiswa_id: int, db_session) -> Dict:
        """
        Import all papers from Mendeley as new documents
        Each paper becomes a separate document in the system
        """
        from app.models import Dokumen, Referensi
        
        print(f"[Mendeley Import] Starting import for mahasiswa_id: {mahasiswa_id}")
        
        # Get all documents from Mendeley
        mendeley_docs = self.get_documents(access_token, limit=500)
        
        print(f"[Mendeley Import] Retrieved {len(mendeley_docs) if mendeley_docs else 0} documents from Mendeley API")
        
        if not mendeley_docs:
            return {
                'status': 'error',
                'message': 'No documents found in Mendeley library',
                'imported_count': 0
            }
        
        imported_count = 0
        skipped_count = 0
        
        for mendeley_doc in mendeley_docs:
            try:
                mendeley_id = mendeley_doc.get('id', 'unknown')
                judul_mendeley = mendeley_doc.get('title', 'Untitled Document')
                
                # Check if document already exists (by filename pattern or judul)
                existing_doc = db_session.query(Dokumen).filter(
                    Dokumen.mahasiswa_id == mahasiswa_id,
                    (Dokumen.nama_file.like(f'mendeley_{mendeley_id}%')) | 
                    (Dokumen.judul == judul_mendeley)
                ).first()
                
                if existing_doc:
                    print(f"[Mendeley Import] Document already exists: {judul_mendeley}, skipping...")
                    skipped_count += 1
                    continue
                
                # Parse document data
                ref_data = self.parse_mendeley_document(mendeley_doc)
                
                # Skip if no meaningful content
                if not ref_data['teks_referensi']:
                    continue
                
                # Create new document in system
                judul = judul_mendeley
                if not judul or judul.strip() == '':
                    judul = ref_data['judul_publikasi'] or 'Untitled Document'
                
                # Try to get PDF file from Mendeley
                import tempfile
                import shutil
                
                upload_dir = f"uploads/mahasiswa_{mahasiswa_id}"
                os.makedirs(upload_dir, exist_ok=True)
                
                mendeley_id = mendeley_doc.get('id', 'unknown')
                file_format = 'txt'
                filename = f"mendeley_{mendeley_id}.txt"
                file_path = None
                
                # Try to download PDF from Mendeley
                try:
                    print(f"[Mendeley Import] Checking for files attached to document: {mendeley_id}")
                    files = self.get_document_files(access_token, mendeley_id)
                    
                    if files and len(files) > 0:
                        # Get first file (usually PDF)
                        file_info = files[0]
                        file_id = file_info.get('id')
                        file_name = file_info.get('file_name', f'paper_{mendeley_id}.pdf')
                        
                        print(f"[Mendeley Import] Found file: {file_name}, downloading...")
                        
                        # Download PDF
                        pdf_path = os.path.join(upload_dir, file_name)
                        if self.download_file(access_token, file_id, pdf_path):
                            file_path = pdf_path
                            filename = file_name
                            file_format = 'pdf' if file_name.lower().endswith('.pdf') else 'docx'
                            print(f"[Mendeley Import] Successfully downloaded PDF: {file_name}")
                        else:
                            print(f"[Mendeley Import] Failed to download file, will use metadata")
                    else:
                        print(f"[Mendeley Import] No files attached, will use metadata only")
                        
                except Exception as e:
                    print(f"[Mendeley Import] Error getting files: {str(e)}")
                
                # If no PDF downloaded, create text file with metadata
                if not file_path:
                    temp_dir = tempfile.mkdtemp()
                    temp_file = os.path.join(temp_dir, 'mendeley_import.txt')
                    
                    # Build comprehensive text content for NLP analysis
                    content_parts = [
                        f"Title: {judul}",
                        "",
                        f"Authors: {ref_data['penulis'] or 'Unknown'}",
                        f"Year: {ref_data['tahun'] or 'Unknown'}",
                        f"Publication: {ref_data['judul_publikasi'] or 'Unknown'}",
                        "",
                    ]
                    
                    # Add abstract if available
                    if mendeley_doc.get('abstract'):
                        content_parts.extend([
                            "Abstract:",
                            mendeley_doc.get('abstract'),
                            ""
                        ])
                    
                    # Add full reference text
                    content_parts.extend([
                        "Reference:",
                        ref_data['teks_referensi'],
                        "",
                        "---",
                        "This document was imported from Mendeley.",
                        "No PDF file was available for download."
                    ])
                    
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(content_parts))
                    
                    file_path = os.path.join(upload_dir, filename)
                    shutil.copy(temp_file, file_path)
                    shutil.rmtree(temp_dir)
                
                # Get file size
                file_size = os.path.getsize(file_path) // 1024  # KB
                
                new_dokumen = Dokumen(
                    mahasiswa_id=mahasiswa_id,
                    judul=judul[:500],  # Limit to 500 chars (model allows 500)
                    nama_file=filename,
                    path_file=file_path,
                    format=file_format,
                    ukuran_kb=file_size,
                    ringkasan=mendeley_doc.get('abstract', '')[:500] if mendeley_doc.get('abstract') else None,
                    status_analisis='pending'
                )
                db_session.add(new_dokumen)
                db_session.flush()  # Get the dokumen_id
                
                # Add the paper itself as a reference
                new_ref = Referensi(
                    dokumen_id=new_dokumen.id,
                    teks_referensi=ref_data['teks_referensi'],
                    penulis=ref_data['penulis'],
                    tahun=ref_data['tahun'],
                    judul_publikasi=ref_data['judul_publikasi'],
                    nomor=1,
                    status_validasi='pending'
                )
                db_session.add(new_ref)
                
                imported_count += 1
                print(f"[Mendeley Import] Successfully imported: {judul[:50]}...")
                
            except Exception as e:
                print(f"[Mendeley Import] Error importing paper {mendeley_doc.get('id', 'unknown')}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        db_session.commit()
        
        print(f"[Mendeley Import] Completed. Imported {imported_count} new papers, skipped {skipped_count} existing papers out of {len(mendeley_docs)} total")
        
        message = f'Successfully imported {imported_count} new papers from Mendeley'
        if skipped_count > 0:
            message += f' ({skipped_count} already existed)'
        
        return {
            'status': 'success',
            'total_documents': len(mendeley_docs),
            'imported_count': imported_count,
            'skipped_count': skipped_count,
            'message': message
        }


# Global instance
mendeley_service = MendeleyService()
