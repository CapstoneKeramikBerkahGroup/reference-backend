-- Migration: Ubah kolom is_valid menjadi status_validasi
-- Tanggal: 2025-12-01

-- 1. Tambah kolom status_validasi dengan nilai default 'pending'
ALTER TABLE referensi ADD COLUMN IF NOT EXISTS status_validasi VARCHAR(50) DEFAULT 'pending';

-- 2. Migrate data dari is_valid ke status_validasi
-- Jika is_valid = true -> 'validated'
-- Jika is_valid = false dan catatan_validasi ada -> 'rejected'
-- Jika is_valid = false dan catatan_validasi kosong -> 'pending'
UPDATE referensi
SET status_validasi = CASE
    WHEN is_valid = true THEN 'validated'
    WHEN is_valid = false AND catatan_validasi IS NOT NULL AND catatan_validasi != '' THEN 'rejected'
    ELSE 'pending'
END;

-- 3. Tambah kolom created_at dan updated_at jika belum ada
ALTER TABLE referensi ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE referensi ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;

-- 4. Hapus kolom is_valid (opsional - bisa dilakukan setelah yakin sistem berjalan dengan baik)
-- ALTER TABLE referensi DROP COLUMN IF EXISTS is_valid;

-- 5. Verifikasi hasil migrasi
SELECT 
    status_validasi, 
    COUNT(*) as jumlah 
FROM referensi 
GROUP BY status_validasi;
