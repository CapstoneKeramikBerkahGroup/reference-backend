# 🚀 Quick Start Guide - Reference Management System Backend

## Prerequisites Checklist

- [ ] Docker Desktop installed
- [ ] Docker Desktop running
- [ ] Port 8000, 5432, 6379 available

## Step-by-Step Setup

### 1️⃣ Navigate to Backend Directory
```powershell
cd "d:\Kuliah\Semester 7\Capstone\Kodingan\backend"
```

### 2️⃣ Verify Files Exist
```powershell
dir
```
You should see:
- `docker-compose.yml`
- `Dockerfile`
- `requirements.txt`
- `.env`
- `app/` folder

### 3️⃣ Build and Start Docker Containers
```powershell
docker-compose up -d --build
```

**Wait time**: ~5-10 minutes (first time - downloading dependencies)

### 4️⃣ Check Container Status
```powershell
docker-compose ps
```

Expected output:
```
NAME                  COMMAND                  SERVICE    STATUS
reference_backend     "uvicorn app.main:app"   backend    Up
reference_db          "docker-entrypoint.s…"   db         Up
reference_redis       "docker-entrypoint.s…"   redis      Up
```

### 5️⃣ View Logs
```powershell
# All containers
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Press Ctrl+C to exit logs
```

### 6️⃣ Access API Documentation
Open browser: **http://localhost:8000/docs**

You should see Swagger UI with all API endpoints!

## 🎯 Quick API Test

### Test 1: Health Check
Open browser: http://localhost:8000/health

Expected response:
```json
{"status": "healthy"}
```

### Test 2: Register & Login via Swagger

1. Go to http://localhost:8000/docs
2. Find `POST /api/auth/register/mahasiswa`
3. Click "Try it out"
4. Use this sample data:
```json
{
  "nim": "1202223217",
  "program_studi": "Sistem Informasi",
  "angkatan": 2022,
  "user": {
    "email": "dhimmas@student.telkomuniversity.ac.id",
    "nama": "Dhimmas Parikesit",
    "password": "password123",
    "role": "mahasiswa"
  }
}
```
5. Click "Execute"
6. Should get 201 Created response

### Test 3: Login

1. Find `POST /api/auth/login`
2. Click "Try it out"
3. Enter:
   - username: `dhimmas@student.telkomuniversity.ac.id`
   - password: `password123`
4. Click "Execute"
5. Copy the `access_token` from response

### Test 4: Authorize

1. Click the green "Authorize" button at top right
2. Paste your token
3. Click "Authorize"
4. Now you can test protected endpoints!

## 📊 Database Access

### Connect to PostgreSQL
```powershell
docker exec -it reference_db psql -U admin -d reference_system
```

### Useful SQL Queries
```sql
-- List all tables
\dt

-- Show users
SELECT * FROM users;

-- Show mahasiswa
SELECT * FROM mahasiswa;

-- Show documents
SELECT * FROM dokumen;

-- Exit
\q
```

## 🛠️ Common Commands

### Stop Containers
```powershell
docker-compose down
```

### Restart Backend Only
```powershell
docker-compose restart backend
```

### Rebuild After Code Changes
```powershell
docker-compose up -d --build backend
```

### Clear Everything (including data)
```powershell
docker-compose down -v
```

### Check Disk Usage
```powershell
docker system df
```

## 🐛 Troubleshooting

### Port Already in Use
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

### Database Connection Error
```powershell
# Check database is ready
docker-compose logs db

# Restart database
docker-compose restart db

# Wait 10 seconds, then restart backend
docker-compose restart backend
```

### Backend Not Starting
```powershell
# Check logs
docker-compose logs backend

# Common issues:
# 1. Missing .env file -> copy .env.example to .env
# 2. Database not ready -> wait and restart backend
# 3. Port conflict -> change port in docker-compose.yml
```

### NLP Models Not Loading
```powershell
# Download spaCy model manually
docker exec -it reference_backend python -m spacy download en_core_web_sm

# Restart backend
docker-compose restart backend
```

## 📱 Testing with Postman

### Import Collection
1. Open Postman
2. Click Import
3. Copy this URL:
   ```
   http://localhost:8000/openapi.json
   ```
4. All endpoints imported!

### Set Environment Variables
- Create new environment: "Backend Local"
- Add variable:
  - `base_url`: `http://localhost:8000`
  - `token`: (will be set after login)

## 🎉 Success Indicators

✅ **All Working When:**
- [ ] http://localhost:8000 shows API info
- [ ] http://localhost:8000/docs shows Swagger UI
- [ ] http://localhost:8000/health returns `{"status": "healthy"}`
- [ ] Can register new user
- [ ] Can login and get token
- [ ] Can upload document
- [ ] No error logs in `docker-compose logs backend`

## 📞 Need Help?

If containers won't start, share output of:
```powershell
docker-compose ps
docker-compose logs backend
```

## Next Steps

1. ✅ Backend running
2. 🔜 Test all endpoints via Swagger
3. 🔜 Build frontend (React)
4. 🔜 Connect frontend to backend
5. 🔜 Deploy to cloud

---

**Pro Tip**: Keep `docker-compose logs -f backend` running in a separate terminal to monitor API requests in real-time!
