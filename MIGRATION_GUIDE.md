# Migration Guide - Status Validasi Referensi

## Perubahan yang Dilakukan

Mengubah sistem validasi referensi dari:
- Field `is_valid` (Boolean: True/False)

Menjadi:
- Field `status_validasi` (String: 'pending', 'validated', 'rejected')

## Langkah Migrasi Database

### 1. Backup Database (WAJIB!)

```powershell
docker exec -it reference_db pg_dump -U admin reference_system > backup_before_migration.sql
```

### 2. Jalankan Migrasi

```powershell
# Copy file SQL ke dalam container
docker cp migration_status_validasi.sql reference_db:/tmp/

# Connect ke PostgreSQL dan jalankan migrasi
docker exec -it reference_db psql -U admin -d reference_system -f /tmp/migration_status_validasi.sql
```

### 3. Verifikasi Hasil Migrasi

```powershell
# Connect ke database
docker exec -it reference_db psql -U admin -d reference_system

# Cek struktur tabel
\d referensi

# Cek distribusi status
SELECT status_validasi, COUNT(*) as jumlah 
FROM referensi 
GROUP BY status_validasi;

# Cek sample data
SELECT id, teks_referensi, status_validasi, catatan_validasi 
FROM referensi 
LIMIT 10;

# Exit
\q
```

## Mapping Status

| Kondisi Lama | Status Baru |
|--------------|-------------|
| is_valid = true | validated |
| is_valid = false + catatan_validasi ada | rejected |
| is_valid = false + catatan_validasi kosong | pending |

## Perubahan Kode

### Backend (Sudah Diperbaiki)

1. **Model `Referensi`** (`app/models/models.py`)
   - Tambah kolom `status_validasi` 
   - Tambah kolom `created_at` dan `updated_at`

2. **API Endpoint** (`app/api/dosen.py`)
   - `/referensi/pending` - Filter by `status_validasi = 'pending'`
   - `/referensi/{id}/validate` - Update `status_validasi`
   - `/referensi/history` - Filter by `status_validasi IN ('validated', 'rejected')`

3. **Document API** (`app/api/documents.py`)
   - Return `status_validasi` di response

4. **NLP Service** (`app/api/nlp.py`)
   - Set default `status_validasi = 'pending'` saat extract references

### Frontend (Sudah Diperbaiki)

1. **DosenDokumenDetail.jsx**
   - Ganti `is_valid` -> `status_validasi`
   - Ganti boolean check -> string check
   - Badge color: 'pending' -> secondary, 'validated' -> default, 'rejected' -> destructive

2. **DosenPendingReferensi.jsx**
   - Request body: `{ status_validasi: 'validated'/'rejected', catatan_validasi: '...' }`
   - Badge mapping sudah benar

3. **API Service** (`services/api.js`)
   - Endpoint sudah benar

## Testing Checklist

### Backend

- [ ] ✅ Migrasi database berhasil
- [ ] ✅ Tabel referensi memiliki kolom `status_validasi`
- [ ] ✅ Data ter-migrate dengan benar
- [ ] ✅ GET `/dosen/referensi/pending` return data dengan `status_validasi='pending'`
- [ ] ✅ PUT `/dosen/referensi/{id}/validate` update status dengan benar
- [ ] ✅ GET `/dosen/referensi/history` return data validated/rejected
- [ ] ✅ GET `/documents/doc/{id}` return referensi dengan `status_validasi`

### Frontend

- [ ] ✅ Badge di DosenDokumenDetail menampilkan status yang benar
- [ ] ✅ Tombol Approve/Reject hanya muncul untuk status 'pending'
- [ ] ✅ Approve mengubah status ke 'validated'
- [ ] ✅ Reject mengubah status ke 'rejected'
- [ ] ✅ Halaman DosenPendingReferensi hanya menampilkan referensi pending
- [ ] ✅ Riwayat validasi menampilkan referensi validated/rejected

## Rollback (Jika Diperlukan)

```sql
-- Restore dari backup
docker exec -i reference_db psql -U admin -d reference_system < backup_before_migration.sql
```

## Notes

- Field `is_valid` TIDAK dihapus dalam migrasi ini untuk backward compatibility
- Setelah yakin sistem berjalan dengan baik, bisa jalankan: `ALTER TABLE referensi DROP COLUMN is_valid;`
- Pastikan restart backend setelah migrasi: `docker compose restart backend`
