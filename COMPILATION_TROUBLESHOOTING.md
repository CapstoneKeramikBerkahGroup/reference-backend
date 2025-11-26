# 🐛 Compilation Report - Troubleshooting Guide

## Common Issues & Solutions

### Issue 1: "Failed to generate compilation report"

**Symptoms:**
- Button click → Toast error message
- No PDF downloaded
- Generic error message

**Root Causes & Solutions:**

#### A. No Documents Available
```
Error: "No documents found. Please upload documents first."
Status: 404
```

**Solution:**
1. Upload at least one document first
2. Wait for document to finish processing
3. Try again

#### B. Authentication Error
```
Error: "Could not validate credentials"
Status: 401
```

**Solution:**
1. Logout and login again
2. Token may have expired
3. Check browser localStorage for valid token

#### C. Missing Relationships Data
```
Error: "AttributeError: 'Dokumen' object has no attribute 'kata_kunci'"
```

**Solution:**
Backend code sudah fixed dengan `hasattr()` checks. Update backend:
```bash
docker restart reference_backend
```

#### D. PDF Generation Error
```
Error: "Failed to generate PDF: ..."
```

**Possible Causes:**
1. **Special characters in document title**
   - Fixed with HTML escaping: `&`, `<`, `>`
   
2. **Empty/None fields**
   - Fixed with null checks: `doc.format or 'N/A'`
   
3. **Large summary text**
   - Fixed with truncation: `[:500]`

---

## Debug Steps

### Step 1: Check Browser Console

```javascript
// Open DevTools (F12) → Console tab
// Look for error messages when clicking button
```

**Expected Output:**
```
Generating compilation report... This may take a moment
GET http://localhost:8000/api/documents/download-compilation
Status: 200 OK
Compilation report downloaded successfully! 📚
```

**Error Example:**
```
Compilation error: Error: Request failed with status code 500
```

### Step 2: Check Backend Logs

```bash
# Real-time logs
docker logs -f reference_backend

# Last 100 lines
docker logs --tail=100 reference_backend
```

**Look for:**
```python
# Success
INFO: 172.18.0.1:12345 - "GET /api/documents/download-compilation HTTP/1.1" 200 OK

# Error
ERROR: Exception in ASGI application
Traceback (most recent call last):
  ...
```

### Step 3: Manual API Test

```bash
# PowerShell

# 1. Login
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
  -Method POST `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=your_email@email.com&password=your_password"

$token = $response.access_token
Write-Host "Token: $token"

# 2. Check documents exist
Invoke-RestMethod -Uri "http://localhost:8000/api/documents/" `
  -Headers @{ "Authorization" = "Bearer $token" }

# 3. Download compilation
Invoke-WebRequest -Uri "http://localhost:8000/api/documents/download-compilation" `
  -Headers @{ "Authorization" = "Bearer $token" } `
  -OutFile "test_compilation.pdf"

# 4. Verify PDF
start test_compilation.pdf
```

### Step 4: Check Database

```bash
# Connect to PostgreSQL
docker exec -it reference_db psql -U admin -d reference_system

# Check documents
SELECT id, judul, status_analisis, mahasiswa_id FROM dokumen LIMIT 5;

# Check keywords exist
SELECT d.id, d.judul, COUNT(kk.id) as keyword_count
FROM dokumen d
LEFT JOIN dokumen_kata dk ON d.id = dk.dokumen_id
LEFT JOIN kata_kunci kk ON kk.id = dk.kata_kunci_id
GROUP BY d.id, d.judul;

# Check references exist
SELECT d.id, d.judul, COUNT(r.id) as ref_count
FROM dokumen d
LEFT JOIN referensi r ON d.id = r.dokumen_id
GROUP BY d.id, d.judul;

# Exit
\q
```

---

## Error Messages Explained

### Frontend Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "No documents to compile" | `documents.length === 0` | Upload documents first |
| "Failed to generate compilation report" | Generic catch-all | Check backend logs |
| "Could not validate credentials" | Token expired/invalid | Login again |
| "Generating compilation report..." (stuck) | Backend timeout/crash | Check backend logs |

### Backend Errors

| HTTP Status | Error Detail | Cause | Solution |
|-------------|--------------|-------|----------|
| 404 | "No documents found" | Empty query result | Upload documents |
| 500 | "Failed to query documents" | Database error | Check DB connection |
| 500 | "Failed to generate PDF" | ReportLab error | Check logs for traceback |
| 401 | "Could not validate credentials" | Invalid JWT | Re-authenticate |

---

## Quick Fixes

### Fix 1: Restart Backend
```bash
docker restart reference_backend
```

### Fix 2: Clear Browser Cache
```javascript
// Browser Console
localStorage.clear();
// Then refresh and login again
```

### Fix 3: Rebuild Backend
```bash
docker-compose down
docker-compose build --no-cache backend
docker-compose up -d
```

### Fix 4: Check ReportLab Installation
```bash
docker exec reference_backend pip show reportlab
# Should show: Version: 4.0.9
```

### Fix 5: Manual ReportLab Install
```bash
docker exec reference_backend pip install reportlab==4.0.9
docker restart reference_backend
```

---

## Known Limitations

### Current Limitations

1. **Max Documents:** Report best for 1-50 documents
   - More than 50 may be slow
   - Consider pagination in future

2. **PDF Size:** Can be large for many docs
   - Each document summary adds ~1-2 pages
   - Similarity table can be long

3. **Processing Time:** 
   - 10 docs ≈ 2-3 seconds
   - 50 docs ≈ 10-15 seconds
   - Shows loading toast

4. **Special Characters:**
   - Fixed: `&`, `<`, `>` escaped
   - Emoji in titles: Converted to text

5. **Empty Data:**
   - Documents without NLP processing: No keywords/summary
   - Documents without similarity: Empty network table

### Workarounds

**For Large Collections:**
```javascript
// Use filters to reduce document count
await documentsAPI.downloadCompilation({
  status_filter: 'completed'  // Only processed docs
});
```

**For Faster Generation:**
```python
# Backend: Reduce data in query
documents = query.limit(20).all()  # Top 20 only
```

---

## Testing Checklist

### Pre-Test Setup
- [ ] Backend running: `docker ps | grep reference_backend`
- [ ] Database healthy: `docker exec reference_db pg_isready`
- [ ] ReportLab installed: `docker exec reference_backend pip show reportlab`
- [ ] User logged in with valid token
- [ ] At least 1 document uploaded

### Test Cases

#### Test 1: Single Document
1. Upload 1 document
2. Wait for processing (status = completed)
3. Click "Download Compilation"
4. **Expected:** PDF with 1 document, minimal stats

#### Test 2: Multiple Documents
1. Upload 5+ documents
2. Process all documents
3. Click "Download Compilation"
4. **Expected:** PDF with all documents, keyword aggregation

#### Test 3: With Filters
1. Tag some documents
2. Use filter: `tag_filter=machine-learning`
3. **Expected:** Only tagged documents in PDF

#### Test 4: Empty Collection
1. Delete all documents
2. Click button
3. **Expected:** Warning toast "No documents to compile"

#### Test 5: Unprocessed Documents
1. Upload document (status = pending)
2. Don't wait for processing
3. Click button
4. **Expected:** PDF generated but "No summary available"

---

## Performance Optimization

### Backend Optimization

```python
# Eager load relationships to reduce queries
from sqlalchemy.orm import joinedload

documents = query.options(
    joinedload(Dokumen.kata_kunci),
    joinedload(Dokumen.referensi),
    joinedload(Dokumen.tags)
).all()
```

### Frontend Optimization

```javascript
// Show progress indicator
const handleDownloadCompilation = async () => {
  const toastId = toast.loading('Generating report...');
  
  try {
    const response = await documentsAPI.downloadCompilation();
    toast.success('Downloaded!', { id: toastId });
  } catch (err) {
    toast.error('Failed!', { id: toastId });
  }
};
```

---

## Contact & Support

**Issue Tracking:**
- Check backend logs first
- Check browser console
- Search this troubleshooting guide
- Create GitHub issue with:
  - Error message
  - Backend logs (last 50 lines)
  - Browser console output
  - Steps to reproduce

**Quick Help:**
```bash
# Collect debug info
echo "=== Backend Status ===" > debug.txt
docker ps | grep reference >> debug.txt
echo "\n=== Backend Logs ===" >> debug.txt
docker logs --tail=50 reference_backend >> debug.txt
echo "\n=== ReportLab ===" >> debug.txt
docker exec reference_backend pip show reportlab >> debug.txt

# Share debug.txt for support
```

---

**Last Updated:** November 26, 2025
**Version:** 1.0.0
