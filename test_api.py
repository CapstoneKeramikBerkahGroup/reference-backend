import requests
import json

# Base URL
BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test health endpoint"""
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_register_mahasiswa():
    """Test mahasiswa registration"""
    print("\n=== Testing Mahasiswa Registration ===")
    
    data = {
        "nim": "1202223217",
        "program_studi": "Sistem Informasi",
        "angkatan": 2022,
        "user": {
            "email": "dhimmas.test@student.telkomuniversity.ac.id",
            "nama": "Dhimmas Parikesit",
            "password": "password123",
            "role": "mahasiswa"
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/register/mahasiswa", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 201

def test_login():
    """Test login"""
    print("\n=== Testing Login ===")
    
    data = {
        "username": "dhimmas.test@student.telkomuniversity.ac.id",
        "password": "password123"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/login", data=data)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Token: {result['access_token'][:50]}...")
        return result['access_token']
    else:
        print(f"Error: {response.json()}")
        return None

def test_get_me(token):
    """Test get current user"""
    print("\n=== Testing Get Current User ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_upload_document(token):
    """Test document upload"""
    print("\n=== Testing Document Upload ===")
    
    # Create a dummy PDF file for testing
    import io
    from reportlab.pdfgen import canvas
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, "Test Document")
    p.drawString(100, 700, "This is a test research paper about Machine Learning.")
    p.save()
    buffer.seek(0)
    
    files = {"file": ("test_paper.pdf", buffer, "application/pdf")}
    data = {"judul": "Machine Learning Research"}
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.post(f"{BASE_URL}/api/documents/upload", files=files, data=data, headers=headers)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 201:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        return result['id']
    else:
        print(f"Error: {response.json()}")
        return None

def test_get_documents(token):
    """Test get all documents"""
    print("\n=== Testing Get Documents ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/documents/", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Documents count: {len(response.json())}")
    return response.status_code == 200

def run_tests():
    """Run all tests"""
    print("=" * 60)
    print("BACKEND API TESTING")
    print("=" * 60)
    
    try:
        # Test 1: Health check
        if not test_health_check():
            print("❌ Health check failed!")
            return
        print("✅ Health check passed!")
        
        # Test 2: Register
        if not test_register_mahasiswa():
            print("⚠️  Registration failed (might already exist)")
        else:
            print("✅ Registration passed!")
        
        # Test 3: Login
        token = test_login()
        if not token:
            print("❌ Login failed!")
            return
        print("✅ Login passed!")
        
        # Test 4: Get current user
        if not test_get_me(token):
            print("❌ Get current user failed!")
            return
        print("✅ Get current user passed!")
        
        # Test 5: Upload document
        doc_id = test_upload_document(token)
        if not doc_id:
            print("❌ Document upload failed!")
            return
        print("✅ Document upload passed!")
        
        # Test 6: Get documents
        if not test_get_documents(token):
            print("❌ Get documents failed!")
            return
        print("✅ Get documents passed!")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to backend. Make sure Docker containers are running:")
        print("   docker-compose up -d")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == "__main__":
    run_tests()
