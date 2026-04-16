"""
Security Headers Middleware
Adds security headers to all API responses
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # XSS protection for legacy browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict transport security (HTTPS only)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        
        # Content Security Policy for API
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Hide server version
        response.headers["Server"] = "API-Server"
        
        return response
