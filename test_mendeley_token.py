"""
Test Mendeley Token Exchange
"""
import requests
from requests.auth import HTTPBasicAuth
import base64

# Your credentials
CLIENT_ID = "21567"
CLIENT_SECRET = "BakRaMQUPbcjGQtu"
REDIRECT_URI = "http://localhost:8000/api/mendeley/oauth/callback"

# Test authorization code (you'll need to get this from a real OAuth flow)
# For now, let's just test the authentication format

def test_basic_auth():
    """Test if Basic Auth header is correctly formed"""
    auth = HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    
    # Create a test request (this will fail without valid code, but shows the auth header)
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()}'
    }
    
    print("Testing Mendeley Token Exchange...")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Client Secret: {CLIENT_SECRET[:10]}... (hidden)")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"\nBasic Auth Header: {headers['Authorization'][:30]}...")
    
    # Test with invalid code to see error response
    data = {
        'grant_type': 'authorization_code',
        'code': 'test_invalid_code',
        'redirect_uri': REDIRECT_URI
    }
    
    print("\nSending token request with invalid code (to test auth)...")
    response = requests.post(
        'https://api.mendeley.com/oauth/token',
        data=data,
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {response.text}")
    
    if response.status_code == 401:
        print("\n❌ 401 Unauthorized - Your credentials are incorrect!")
        print("Please check:")
        print("1. Client ID should be the Application ID from Mendeley Developer Portal")
        print("2. Client Secret should match exactly (no extra spaces)")
        print("3. Your Mendeley app must be 'Published' status")
    elif response.status_code == 400:
        print("\n✅ Authentication is OK (400 is expected with invalid code)")
        print("The credentials are accepted by Mendeley API")
    else:
        print(f"\n⚠️ Unexpected response: {response.status_code}")

if __name__ == "__main__":
    test_basic_auth()
