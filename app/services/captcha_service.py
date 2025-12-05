"""Captcha generation service with graceful fallback.

Tries to use the `captcha` package (from captcha.image import ImageCaptcha).
If it's not available at runtime, falls back to a Pillow-based simple captcha
renderer so the backend doesn't crash. A warning is printed in DEBUG logs.
"""

from io import BytesIO
import random
import string
import base64
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont  # Pillow is in requirements

# Try to import the third-party captcha library; fallback if missing
try:
    from captcha.image import ImageCaptcha  # type: ignore
    _HAS_CAPTCHA_LIB = True
except Exception:  # ModuleNotFoundError or other runtime import issues
    ImageCaptcha = None  # type: ignore
    _HAS_CAPTCHA_LIB = False


class CaptchaService:
    """Service for generating and validating CAPTCHA"""

    def __init__(self):
        self.width = 200
        self.height = 80
        self._use_fallback = not _HAS_CAPTCHA_LIB
        if not self._use_fallback:
            # Initialize third-party captcha generator
            self.image_captcha = ImageCaptcha(width=self.width, height=self.height)  # type: ignore
        else:
            # Fallback: no external captcha lib; we'll render with Pillow
            # Note: This is simpler and less obfuscated than ImageCaptcha.
            # Consider installing `captcha` package in your runtime for production use.
            print("[CAPTCHA] Warning: 'captcha' package not found. Using Pillow fallback renderer.")
    
    def generate_captcha_text(self, length: int = 6) -> str:
        """Generate random CAPTCHA text"""
        # Use uppercase letters and numbers for better readability
        characters = string.ascii_uppercase + string.digits
        # Exclude confusing characters: O, 0, I, 1, l
        characters = characters.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
        return ''.join(random.choices(characters, k=length))
    
    def generate_captcha_image(self, text: str) -> Tuple[str, bytes]:
        """
        Generate CAPTCHA image
        Returns: (base64_string, raw_bytes)
        """
        if not self._use_fallback:
            # Generate image using captcha library
            data = self.image_captcha.generate(text)  # type: ignore
            image_bytes = data.getvalue()
        else:
            # Simple Pillow-based rendering as a fallback
            img = Image.new("RGB", (self.width, self.height), color=(245, 245, 245))
            draw = ImageDraw.Draw(img)

            # Try a basic font; fall back to default if truetype unavailable
            try:
                # DejaVuSans is commonly available in manylinux images via Pillow
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
            except Exception:
                font = ImageFont.load_default()

            # Draw centered text
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            x = (self.width - text_w) // 2
            y = (self.height - text_h) // 2
            draw.text((x, y), text, fill=(30, 30, 30), font=font)

            # Save to bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            image_bytes = buffer.getvalue()

        # Convert to base64 for frontend
        base64_string = base64.b64encode(image_bytes).decode('utf-8')

        return base64_string, image_bytes
    
    def create_captcha(self) -> dict:
        """
        Create complete CAPTCHA
        Returns dict with text and base64 image
        """
        text = self.generate_captcha_text()
        base64_image, _ = self.generate_captcha_image(text)
        
        return {
            "text": text,
            "image": f"data:image/png;base64,{base64_image}"
        }
    
    @staticmethod
    def validate_captcha(user_input: str, expected: str) -> bool:
        """
        Validate CAPTCHA input (case-insensitive)
        """
        return user_input.upper().strip() == expected.upper().strip()


# Singleton instance
captcha_service = CaptchaService()
