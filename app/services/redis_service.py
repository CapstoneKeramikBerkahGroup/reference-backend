import redis
import json
from datetime import timedelta
from app.core.config import settings
from typing import Optional


class RedisService:
    """Service for Redis operations (CAPTCHA, verification codes, sessions)"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    # ============= CAPTCHA Methods =============
    
    def store_captcha(self, session_id: str, captcha_text: str, expire_minutes: int = 5):
        """Store CAPTCHA text in Redis with expiration"""
        key = f"captcha:{session_id}"
        self.redis_client.setex(key, timedelta(minutes=expire_minutes), captcha_text)
    
    def get_captcha(self, session_id: str) -> Optional[str]:
        """Get CAPTCHA text from Redis"""
        key = f"captcha:{session_id}"
        return self.redis_client.get(key)
    
    def delete_captcha(self, session_id: str):
        """Delete CAPTCHA from Redis after validation"""
        key = f"captcha:{session_id}"
        self.redis_client.delete(key)
    
    # ============= Verification Code Methods =============
    
    def store_verification_code(self, email: str, code: str, expire_minutes: int = 15):
        """Store verification code for password reset"""
        key = f"verify:password:{email}"
        data = {"code": code, "attempts": 0}
        self.redis_client.setex(
            key, 
            timedelta(minutes=expire_minutes), 
            json.dumps(data)
        )
    
    def get_verification_code(self, email: str) -> Optional[dict]:
        """Get verification code data"""
        key = f"verify:password:{email}"
        data = self.redis_client.get(key)
        return json.loads(data) if data else None
    
    def increment_verification_attempts(self, email: str) -> int:
        """Increment failed verification attempts"""
        key = f"verify:password:{email}"
        data = self.get_verification_code(email)
        
        if not data:
            return 0
        
        data["attempts"] += 1
        
        # Get remaining TTL
        ttl = self.redis_client.ttl(key)
        if ttl > 0:
            self.redis_client.setex(key, ttl, json.dumps(data))
        
        return data["attempts"]
    
    def delete_verification_code(self, email: str):
        """Delete verification code after successful reset"""
        key = f"verify:password:{email}"
        self.redis_client.delete(key)
    
    # ============= Rate Limiting =============
    
    def check_rate_limit(self, key: str, max_attempts: int, window_minutes: int) -> bool:
        """
        Check if rate limit is exceeded
        Returns True if allowed, False if rate limit exceeded
        """
        attempts = self.redis_client.get(key)
        
        if attempts is None:
            self.redis_client.setex(key, timedelta(minutes=window_minutes), 1)
            return True
        
        attempts = int(attempts)
        if attempts >= max_attempts:
            return False
        
        self.redis_client.incr(key)
        return True
    
    def get_rate_limit_ttl(self, key: str) -> int:
        """Get remaining TTL for rate limit key (in seconds)"""
        return self.redis_client.ttl(key)


# Singleton instance
redis_service = RedisService()
