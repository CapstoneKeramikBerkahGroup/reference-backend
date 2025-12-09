from pyzotero import zotero
from sqlalchemy.orm import Session
from app.models import UserZotero, ExternalReference
import logging
from datetime import datetime
import os
import requests
from app.models import Dokumen, ExternalReference, UserZotero, Mahasiswa
from uuid import uuid4

logger = logging.getLogger(__name__)

class ZoteroService:
    def sync_library(self, user_id: int, db: Session):
        """
        Menarik metadata dari Zotero Library user.
        """
        # 1. Ambil kredensial user dari DB
        creds = db.query(UserZotero).filter(UserZotero.user_id == user_id).first()
        if not creds:
            raise Exception("Zotero account not connected. Please connect in settings.")

        try:
            # 2. Koneksi ke Zotero API
            zot = zotero.Zotero(creds.zotero_user_id, creds.library_type, creds.api_key)
            
            # 3. Ambil 50 item teratas (bisa dinaikkan nanti)
            logger.info(f"Fetching items for Zotero User {creds.zotero_user_id}...")
            items = zot.top(limit=50)
            
            synced_count = 0
            for item in items:
                data = item['data']
                key = data['key']
                
                # Cek apakah item sudah ada di DB kita (biar gak duplikat)
                exists = db.query(ExternalReference).filter(
                    ExternalReference.source_id == key, 
                    ExternalReference.user_id == user_id
                ).first()
                
                if exists:
                    continue # Skip jika sudah ada

                # Parsing Nama Penulis
                creators = data.get('creators', [])
                author_names = []
                for c in creators:
                    if 'firstName' in c and 'lastName' in c:
                        author_names.append(f"{c['firstName']} {c['lastName']}")
                    elif 'name' in c:
                        author_names.append(c['name'])
                
                authors_str = ", ".join(author_names)
                
                # Parsing Tahun
                date_str = data.get('date', '')
                year = date_str[:4] if len(date_str) >= 4 else "N/A"

                # Simpan ke DB
                new_ref = ExternalReference(
                    user_id=user_id,
                    source="zotero",
                    source_id=key,
                    title=data.get('title', 'Untitled'),
                    authors=authors_str,
                    year=year,
                    abstract=data.get('abstractNote', ''),
                    url=data.get('url', ''),
                    has_pdf=False # Logic deteksi PDF bisa ditambahkan nanti
                )
                db.add(new_ref)
                synced_count += 1
            
            # Update waktu sync terakhir
            creds.last_sync = datetime.utcnow()
            db.commit()
            
            logger.info(f"✅ Synced {synced_count} new items from Zotero.")
            return {"status": "success", "synced_count": synced_count}

        except Exception as e:
            logger.error(f"❌ Zotero Sync Error: {e}")
            raise e
    
    def process_zotero_document(self, ext_ref_id: int, db: Session, user_id: int):
        """
        Download PDF dari Zotero, simpan sebagai Dokumen lokal, dan trigger analisis.
        """
        # 1. Ambil data External Reference
        ext_ref = db.query(ExternalReference).filter(ExternalReference.id == ext_ref_id).first()
        if not ext_ref:
            raise Exception("Reference not found")
        
        # Cek apakah sudah pernah diproses? (Biar gak download ulang)
        if ext_ref.local_document_id:
            return {"document_id": ext_ref.local_document_id, "status": "exists"}

        # 2. Ambil Kredensial Zotero User
        creds = db.query(UserZotero).filter(UserZotero.user_id == user_id).first()
        if not creds:
            raise Exception("Zotero credentials not found")

        # 3. Cari Attachment PDF di Zotero
        zot = zotero.Zotero(creds.zotero_user_id, creds.library_type, creds.api_key)
        # Cari item 'child' yang tipe-nya attachment PDF
        children = zot.children(ext_ref.source_id)
        pdf_item = next((c for c in children if c['data'].get('contentType') == 'application/pdf'), None)

        if not pdf_item:
            raise Exception("No PDF attachment found for this item in Zotero")

        # 4. Download File
        file_key = pdf_item['key']
        file_name = pdf_item['data'].get('filename', f"{ext_ref.source_id}.pdf")
        
        # Buat path lokal
        upload_dir = "/app/uploads"
        unique_filename = f"zotero_{uuid4().hex}_{file_name}"
        file_path = os.path.join(upload_dir, unique_filename)

        # Stream download dari Zotero API (butuh header auth)
        # Library pyzotero punya method 'dump' tapi untuk binary file lebih aman pakai requests manual ke signed URL
        # Atau gunakan method .file(key) dari pyzotero jika support (versi baru support)
        
        try:
            # Cara Pyzotero untuk download file binary
            zot.dump(file_key, file_name, upload_dir) 
            # Rename agar unik (karena dump pakai nama asli)
            os.rename(os.path.join(upload_dir, file_name), file_path)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise Exception("Failed to download PDF from Zotero")

        # 5. Buat Entry di Tabel Dokumen
        # Kita butuh ID Mahasiswa dari User ID
        mahasiswa = db.query(Mahasiswa).filter(Mahasiswa.user_id == user_id).first()
        if not mahasiswa:
             raise Exception("User profile not found")

        new_doc = Dokumen(
            mahasiswa_id=mahasiswa.id,
            judul=ext_ref.title,
            nama_file=file_name,
            path_file=file_path,
            format="pdf",
            ukuran_kb=os.path.getsize(file_path) // 1024,
            status_analisis="pending" # Nanti diproses oleh worker
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # 6. Link Balik dan Update Status
        ext_ref.local_document_id = new_doc.id
        ext_ref.is_analyzed = True
        db.commit()

        return {"document_id": new_doc.id, "status": "created"}

zotero_service = ZoteroService()