from jose import jwt, JWTError
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token

# Create token
token = create_access_token({"sub": 1, "email": "test@test.com", "role": "mahasiswa"})
print(f"Token created: {token[:50]}...")

# Try decoding with jose directly
try:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    print(f"Direct decode SUCCESS: {payload}")
except JWTError as e:
    print(f"Direct decode FAILED: {e}")

# Try with our function
decoded = decode_access_token(token)
print(f"Function decode result: {decoded}")
