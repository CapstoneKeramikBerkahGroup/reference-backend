#!/usr/bin/env python3
"""
Script to validate Mendeley OAuth configuration
Run this to check if your credentials are set up correctly
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def check_env_file():
    """Check if .env file exists and has Mendeley config"""
    env_path = Path(__file__).parent / '.env'
    
    if not env_path.exists():
        print("❌ Error: .env file not found!")
        print(f"   Expected at: {env_path}")
        return False
    
    print(f"✅ .env file found at: {env_path}")
    
    # Read .env file
    with open(env_path, 'r') as f:
        content = f.read()
    
    # Check for Mendeley config
    if 'MENDELEY_CLIENT_ID' not in content:
        print("❌ Error: MENDELEY_CLIENT_ID not found in .env")
        return False
    
    if 'MENDELEY_CLIENT_SECRET' not in content:
        print("❌ Error: MENDELEY_CLIENT_SECRET not found in .env")
        return False
    
    print("✅ Mendeley config keys found in .env")
    return True

def check_credentials():
    """Check if credentials are actually set (not placeholder)"""
    from dotenv import load_dotenv
    
    # Load .env
    load_dotenv()
    
    client_id = os.getenv('MENDELEY_CLIENT_ID', '')
    client_secret = os.getenv('MENDELEY_CLIENT_SECRET', '')
    redirect_uri = os.getenv('MENDELEY_REDIRECT_URI', '')
    
    print("\n" + "="*60)
    print("Mendeley OAuth Configuration Check")
    print("="*60)
    
    # Check Client ID
    print("\n1. Client ID:")
    if not client_id or client_id == 'your_client_id_here':
        print("   ❌ NOT SET or still placeholder")
        print("   → Please register app at https://dev.mendeley.com/myapps.html")
        return False
    else:
        print(f"   ✅ Set: {client_id[:20]}... (length: {len(client_id)})")
    
    # Check Client Secret
    print("\n2. Client Secret:")
    if not client_secret or client_secret == 'your_client_secret_here':
        print("   ❌ NOT SET or still placeholder")
        print("   → Please register app at https://dev.mendeley.com/myapps.html")
        return False
    else:
        print(f"   ✅ Set: {client_secret[:10]}... (length: {len(client_secret)})")
    
    # Check Redirect URI
    print("\n3. Redirect URI:")
    expected = 'http://localhost:8000/api/mendeley/oauth/callback'
    if redirect_uri != expected:
        print(f"   ⚠️  Current: {redirect_uri}")
        print(f"   ⚠️  Expected: {expected}")
        print("   → Make sure it matches your Mendeley app settings!")
    else:
        print(f"   ✅ Correct: {redirect_uri}")
    
    print("\n" + "="*60)
    print("✅ All credentials are set!")
    print("="*60)
    print("\nNext steps:")
    print("1. Make sure Mendeley app redirect URI matches:")
    print(f"   {expected}")
    print("2. Restart Docker: docker-compose down && docker-compose up -d")
    print("3. Test OAuth flow in browser")
    
    return True

def test_oauth_flow():
    """Test OAuth authorization URL generation"""
    print("\n" + "="*60)
    print("Testing OAuth Flow")
    print("="*60)
    
    try:
        from app.services.mendeley_service import mendeley_service
        
        print("\n✅ Mendeley service loaded successfully")
        
        # Generate auth URL
        auth_url, state = mendeley_service.get_authorization_url()
        
        print(f"\n✅ Authorization URL generated:")
        print(f"   {auth_url[:100]}...")
        print(f"\n✅ State: {state}")
        
        print("\n" + "="*60)
        print("✅ OAuth flow test PASSED!")
        print("="*60)
        print("\nYou can now test in browser:")
        print("1. Login to app as mahasiswa")
        print("2. Open a document")
        print("3. Click 'Import dari Mendeley' → 'Connect ke Mendeley'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing OAuth flow: {e}")
        print("\nPossible issues:")
        print("- Credentials not set correctly")
        print("- OAuth libraries not installed")
        print("- Service import error")
        return False

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Mendeley OAuth Configuration Validator")
    print("="*60)
    
    # Step 1: Check .env file
    if not check_env_file():
        print("\n❌ Please create .env file with Mendeley credentials")
        print("See: MENDELEY_FIX_AUTH_ERROR.md for instructions")
        sys.exit(1)
    
    # Step 2: Check credentials
    if not check_credentials():
        print("\n❌ Credentials not properly configured")
        print("See: MENDELEY_FIX_AUTH_ERROR.md for instructions")
        sys.exit(1)
    
    # Step 3: Test OAuth flow (optional, might fail if not in Docker)
    print("\n" + "="*60)
    print("Attempting to test OAuth flow...")
    print("(This might fail if not running in Docker)")
    print("="*60)
    
    try:
        test_oauth_flow()
    except Exception as e:
        print(f"\n⚠️  Could not test OAuth flow: {e}")
        print("This is normal if running outside Docker")
        print("Credentials are set correctly, proceed to restart Docker")
    
    print("\n" + "="*60)
    print("✅ Validation Complete!")
    print("="*60)
