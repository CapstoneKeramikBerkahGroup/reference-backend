import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
print(f"🔑 Memeriksa API Key: {api_key[:5]}...{api_key[-3:]}")

try:
    genai.configure(api_key=api_key)
    print("\n📋 Daftar Model yang Tersedia untuk Akun Ini:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f" - {m.name}")
except Exception as e:
    print(f"\n❌ Error: {e}")