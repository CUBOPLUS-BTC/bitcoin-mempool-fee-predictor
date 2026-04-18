"""
Multi-tenant API Key Authentication with Redis caching.
Supports multiple API keys with per-client rate limiting and revocation.
"""

import os
import redis
import hashlib
import secrets
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from fastapi import HTTPException, Security, Request
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Security: Use Redis for caching API keys with TTL
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
API_KEY_CACHE_TTL = int(os.getenv("API_KEY_CACHE_TTL", "3600"))  # 1 hour

class APIKeyInfo(BaseModel):
    """API Key metadata"""
    key_id: str
    client_name: str
    permissions: List[str]
    rate_limit: int  # requests per minute
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool = True
    last_used: Optional[str] = None

class MultiKeyAuthManager:
    """
    Multi-tenant API Key Manager with Redis caching.
    
    Features:
    - Multiple API keys per client
    - Automatic key revocation
    - Per-client rate limiting
    - Redis caching for performance
    """
    
    def __init__(self, redis_url: str = REDIS_URL):
        self.api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
        self._local_cache: Dict[str, APIKeyInfo] = {}
        
        # Initialize Redis connection
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("✓ Redis connection established for API key caching")
        except (redis.ConnectionError, redis.ResponseError) as e:
            logger.warning(f"Redis unavailable ({e}), using local cache only")
            self.redis_client = None
    
    def _hash_key(self, api_key: str) -> str:
        """Hash API key for secure storage/lookup"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def _get_cache_key(self, hashed_key: str) -> str:
        """Generate Redis cache key"""
        return f"api_key:{hashed_key}"
    
    def _get_rate_limit_key(self, key_id: str) -> str:
        """Generate rate limit counter key"""
        minute_bucket = datetime.now().strftime("%Y%m%d%H%M")
        return f"rate_limit:{key_id}:{minute_bucket}"
    
    def validate_api_key(self, api_key: str) -> Optional[APIKeyInfo]:
        """
        Validate API key against cache or persistent storage.
        
        Args:
            api_key: The raw API key to validate
            
        Returns:
            APIKeyInfo if valid, None otherwise
        """
        if not api_key:
            return None
        
        hashed = self._hash_key(api_key)
        
        # Check local cache first (fastest)
        if hashed in self._local_cache:
            info = self._local_cache[hashed]
            if info.is_active and (not info.expires_at or datetime.now() < datetime.fromisoformat(info.expires_at)):
                return info
            else:
                del self._local_cache[hashed]
        
        # Check Redis cache
        if self.redis_client:
            cache_key = self._get_cache_key(hashed)
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                import json
                info = APIKeyInfo.parse_raw(cached_data)
                if info.is_active:
                    self._local_cache[hashed] = info
                    return info
        
        # Check environment variable (legacy single-key support)
        master_key = os.getenv("API_KEY")
        if master_key and secrets.compare_digest(api_key, master_key):
            info = APIKeyInfo(
                key_id="master",
                client_name="admin",
                permissions=["read", "write", "admin"],
                rate_limit=100,
                created_at=datetime.now().isoformat(),
            )
            self._local_cache[hashed] = info
            return info
        
        return None
    
    def check_rate_limit(self, key_info: APIKeyInfo, request: Request) -> bool:
        """
        Check if request is within rate limit for this API key.
        
        Args:
            key_info: API key metadata
            request: FastAPI request object
            
        Returns:
            True if within limit, False if exceeded
        """
        if not self.redis_client:
            # Without Redis, allow all (with basic logging)
            return True
        
        rate_key = self._get_rate_limit_key(key_info.key_id)
        current = self.redis_client.incr(rate_key)
        
        # Set expiry on first request
        if current == 1:
            self.redis_client.expire(rate_key, 60)  # 1 minute window
        
        if current > key_info.rate_limit:
            logger.warning(
                f"Rate limit exceeded for client {key_info.client_name} "
                f"({key_info.key_id}): {current}/{key_info.rate_limit}"
            )
            return False
        
        return True
    
    async def verify_api_key(
        self,
        request: Request,
        api_key: str = Security(APIKeyHeader(name="X-API-Key", auto_error=False))
    ) -> APIKeyInfo:
        """
        FastAPI dependency for API key verification.
        
        Usage:
            @app.get("/protected")
            async def endpoint(api_key_info: APIKeyInfo = Depends(auth_manager.verify_api_key)):
                ...
        """
        # Security: Development bypass
        env = os.getenv("ENV", "production")
        if env == "development" and not api_key:
            return APIKeyInfo(
                key_id="dev",
                client_name="development",
                permissions=["read", "write"],
                rate_limit=1000,
                created_at=datetime.now().isoformat()
            )
        
        if not api_key:
            raise HTTPException(status_code=401, detail="API Key required")
        
        # Validate key
        key_info = self.validate_api_key(api_key)
        if not key_info:
            logger.warning(f"Invalid API key attempt from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        if not key_info.is_active:
            logger.warning(f"Revoked API key used: {key_info.key_id}")
            raise HTTPException(status_code=403, detail="API key revoked")
        
        # Check rate limit
        if not self.check_rate_limit(key_info, request):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Update last used timestamp (async fire-and-forget)
        if self.redis_client:
            key_info.last_used = datetime.now().isoformat()
            self.redis_client.setex(
                self._get_cache_key(self._hash_key(api_key)),
                API_KEY_CACHE_TTL,
                key_info.json()
            )
        
        return key_info
    
    def create_api_key(
        self,
        client_name: str,
        permissions: List[str] = None,
        rate_limit: int = 30,
        expires_days: Optional[int] = None
    ) -> tuple[str, APIKeyInfo]:
        """
        Create a new API key for a client.
        
        Args:
            client_name: Identifier for the client
            permissions: List of permissions (read, write, admin)
            rate_limit: Requests per minute limit
            expires_days: Optional expiration in days
            
        Returns:
            Tuple of (raw_api_key, key_info)
        """
        # Generate secure random key
        raw_key = f"btc_{secrets.token_urlsafe(32)}"
        hashed = self._hash_key(raw_key)
        
        key_id = f"key_{secrets.token_hex(8)}"
        
        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        
        info = APIKeyInfo(
            key_id=key_id,
            client_name=client_name,
            permissions=permissions or ["read"],
            rate_limit=rate_limit,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at,
            is_active=True
        )
        
        # Store in Redis
        if self.redis_client:
            self.redis_client.setex(
                self._get_cache_key(hashed),
                API_KEY_CACHE_TTL if not expires_days else int(timedelta(days=expires_days).total_seconds()),
                info.json()
            )
        
        # Store in local cache
        self._local_cache[hashed] = info
        
        logger.info(f"Created API key {key_id} for client {client_name}")
        return raw_key, info
    
    def revoke_api_key(self, key_id: str) -> bool:
        """
        Revoke an API key by ID.
        
        Args:
            key_id: The key ID to revoke
            
        Returns:
            True if revoked, False if not found
        """
        # Find in local cache
        for hashed, info in list(self._local_cache.items()):
            if info.key_id == key_id:
                info.is_active = False
                
                # Update Redis
                if self.redis_client:
                    self.redis_client.setex(
                        self._get_cache_key(hashed),
                        API_KEY_CACHE_TTL,
                        info.json()
                    )
                
                logger.info(f"Revoked API key {key_id}")
                return True
        
        return False
    
    def list_active_keys(self) -> List[APIKeyInfo]:
        """List all active API keys"""
        return [info for info in self._local_cache.values() if info.is_active]


# Global instance (singleton)
auth_manager = MultiKeyAuthManager()

# Legacy compatibility
def verify_api_key(request: Request, api_key: str = Security(APIKeyHeader(name="X-API-Key", auto_error=False))):
    """Legacy wrapper for single-key verification"""
    return auth_manager.verify_api_key(request, api_key)
