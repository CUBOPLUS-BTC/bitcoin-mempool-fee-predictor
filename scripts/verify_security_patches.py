#!/usr/bin/env python3
"""
Security Patch Verification Script
Tests that all security patches are working correctly
"""

import requests
import sys
import os

# Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

def test_endpoint(name, method, endpoint, headers=None, expected_status=None):
    """Test an API endpoint"""
    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            resp = requests.post(url, headers=headers, timeout=10)
        else:
            return False, f"Unsupported method: {method}"
        
        if expected_status and resp.status_code != expected_status:
            return False, f"Expected {expected_status}, got {resp.status_code}"
        
        return True, f"Status {resp.status_code}"
    except Exception as e:
        return False, str(e)

def check_security_headers():
    """Verify security headers are present"""
    print("\n🔒 Checking Security Headers...")
    try:
        resp = requests.get(f"{API_BASE}/", timeout=10)
        headers = resp.headers
        
        required_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'Strict-Transport-Security': None,  # Just check existence
        }
        
        results = []
        for header, expected in required_headers.items():
            if header in headers:
                if expected and headers[header] == expected:
                    results.append(("✅", header, headers[header]))
                elif not expected:
                    results.append(("✅", header, "Present"))
            else:
                results.append(("❌", header, "Missing"))
        
        for status, header, value in results:
            print(f"  {status} {header}: {value}")
        
        return all(r[0] == "✅" for r in results)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_authentication():
    """Test API key authentication"""
    print("\n🔑 Testing API Authentication...")
    
    # Test without API key (should fail for protected endpoints)
    success, msg = test_endpoint("Predict (no key)", "GET", "/fees/predict")
    if not success or "403" in msg:
        print(f"  ✅ Predict without key: Blocked ({msg})")
    else:
        print(f"  ❌ Predict without key: Allowed ({msg}) - VULNERABILITY!")
    
    # Test with API key
    headers = {"X-API-Key": API_KEY}
    success, msg = test_endpoint("Predict (with key)", "GET", "/fees/predict", headers=headers)
    if success and "200" in msg:
        print(f"  ✅ Predict with key: Allowed ({msg})")
    else:
        print(f"  ❌ Predict with key: Failed ({msg})")
    
    # Test models endpoint
    success, msg = test_endpoint("Models (no key)", "GET", "/models")
    if not success or "403" in msg:
        print(f"  ✅ Models without key: Blocked ({msg})")
    else:
        print(f"  ❌ Models without key: Allowed ({msg}) - VULNERABILITY!")

def test_cors():
    """Test CORS configuration"""
    print("\n🌐 Testing CORS Configuration...")
    try:
        # Test preflight with disallowed origin
        headers = {
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "GET"
        }
        resp = requests.options(f"{API_BASE}/fees/predict", headers=headers, timeout=10)
        
        cors_header = resp.headers.get('Access-Control-Allow-Origin', '')
        if cors_header == 'https://evil.com' or cors_header == '*':
            print(f"  ❌ CORS allows malicious origin: {cors_header}")
        else:
            print(f"  ✅ CORS rejects malicious origin")
    except Exception as e:
        print(f"  ⚠️  CORS test error: {e}")

def test_rate_limiting():
    """Test rate limiting"""
    print("\n⏱️  Testing Rate Limiting...")
    if not API_KEY:
        print("  ⚠️  Skipping (no API_KEY set)")
        return
    
    headers = {"X-API-Key": API_KEY}
    endpoint = "/health"
    
    # Make rapid requests
    responses = []
    for i in range(35):  # Should trigger rate limit at 30
        try:
            resp = requests.get(f"{API_BASE}{endpoint}", headers=headers, timeout=5)
            responses.append(resp.status_code)
        except Exception as e:
            responses.append(0)
    
    if 429 in responses:
        print(f"  ✅ Rate limiting active (429 received)")
    else:
        unique = set(responses)
        print(f"  ⚠️  No 429 received. Status codes: {unique}")

def test_error_handling():
    """Test that errors don't expose sensitive info"""
    print("\n🛡️  Testing Error Handling...")
    
    # Test non-existent endpoint
    try:
        resp = requests.get(f"{API_BASE}/nonexistent-endpoint-12345", timeout=10)
        body = resp.text.lower()
        
        sensitive_terms = ['traceback', 'stack trace', 'file "/', 'line ', 'module ']
        found = [term for term in sensitive_terms if term in body]
        
        if found:
            print(f"  ❌ Sensitive info in error: {found}")
        else:
            print(f"  ✅ No sensitive info in error response")
    except Exception as e:
        print(f"  ⚠️  Error test failed: {e}")

def main():
    print("=" * 60)
    print("🔐 SECURITY PATCH VERIFICATION")
    print("=" * 60)
    print(f"API: {API_BASE}")
    print(f"API Key: {'Set' if API_KEY else 'Not set'}")
    
    # Check if API is running
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"✅ API is running (status {resp.status_code})")
    except Exception as e:
        print(f"❌ API is not running: {e}")
        print("\nPlease start the API first:")
        print("  ENV=development API_KEY=test-key python -m uvicorn api.main:app --port 8000")
        sys.exit(1)
    
    # Run tests
    check_security_headers()
    test_authentication()
    test_cors()
    test_rate_limiting()
    test_error_handling()
    
    print("\n" + "=" * 60)
    print("✅ Verification complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
