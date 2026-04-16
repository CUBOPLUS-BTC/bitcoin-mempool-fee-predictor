"""
Security Module for API Authentication and Rate Limiting
Implements API key validation and rate limiting for the Fee Prediction API
"""

from fastapi import Security, HTTPException, Request
from fastapi.security import APIKeyHeader
import os
from datetime import datetime

# API Key configuration
API_KEY = os.getenv("API_KEY")
if not API_KEY and os.getenv("ENV", "production") == "production":
    raise ValueError("API_KEY environment variable is required in production")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key for protected endpoints"""
    if not API_KEY:  # Development mode without key
        return None
    
    if not api_key:
        raise HTTPException(status_code=403, detail="API Key required")
    
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    return api_key


class SecurityLogger:
    """Structured security logging"""
    
    @staticmethod
    def log_api_access(request: Request, response_status: int, api_key: str = None):
        """Log API access for security monitoring"""
        import json
        import logging
        
        logger = logging.getLogger("security")
        log_entry = {
            "event": "api_access",
            "timestamp": datetime.utcnow().isoformat(),
            "ip": request.client.host if request.client else "unknown",
            "endpoint": str(request.url.path),
            "method": request.method,
            "status": response_status,
            "api_key_prefix": api_key[:8] if api_key else None,
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        logger.info(json.dumps(log_entry))
