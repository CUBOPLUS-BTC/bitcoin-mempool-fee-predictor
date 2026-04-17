# 🔐 Security Guide

Comprehensive guide to the security features of the Bitcoin Mempool Fee Predictor.

**Security Score: 8.5/10**

---

## 🛡️ Security Features Overview

| Feature | Status | Implementation |
|---------|--------|----------------|
| API Authentication | ✅ Active | API Key (`X-API-Key` header) |
| Rate Limiting | ✅ Active | 30/10/20 req/min per endpoint |
| CORS | ✅ Active | Whitelist-based origin validation |
| Security Headers | ✅ Active | 7 headers including CSP, HSTS |
| Model Integrity | ✅ Active | SHA-256 hash verification |
| Error Sanitization | ✅ Active | No internal details exposed |
| Dependency Audit | ✅ Active | pip-audit + npm audit |
| Frontend CSP | ✅ Active | Content Security Policy |

---

## 🔑 API Authentication

### How It Works

The API uses API key authentication via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8000/fees/predict
```

### Configuration

**Development Mode:**
```bash
export ENV=development
# No API key required
```

**Production Mode:**
```bash
export ENV=production
export API_KEY=$(openssl rand -hex 32)
# API key required for all protected endpoints
```

### Generating a Secure API Key

```bash
# Option 1: Using openssl
openssl rand -hex 32

# Option 2: Using Python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🌐 CORS Configuration

Cross-Origin Resource Sharing (CORS) is configured to allow only specific origins.

### Default Allowed Origins

```bash
http://localhost:5173   # React dev server
http://localhost:3000   # Alternative dev port
http://127.0.0.1:5173   # Localhost IP variant
```

### Custom Origins

```bash
export ALLOWED_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
```

### Security Note

- Wildcard (`*`) is **not** allowed with credentials enabled
- Only `GET` method is permitted
- Preflight requests are cached for 600 seconds

---

## ⏱️ Rate Limiting

Rate limiting prevents abuse and ensures fair resource usage.

### Endpoint Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/fees/predict` | 30 requests | 1 minute |
| `/fees/history` | 10 requests | 1 minute |
| `/models` | 20 requests | 1 minute |
| `/health`, `/` | Unlimited | - |

### Rate Limit Response

When exceeded:
```json
{
  "detail": "Rate limit exceeded"
}
```

HTTP Status: `429 Too Many Requests`

---

## 🔒 Security Headers

All API responses include these security headers:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS filter enabled |
| `Strict-Transport-Security` | `max-age=63072000` | HSTS (2 years) |
| `Content-Security-Policy` | `default-src 'self'` | CSP protection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer control |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Feature restrictions |

### Verification

```bash
curl -I http://localhost:8000/ | grep -E "X-|Strict-|Content-Security"
```

---

## 🧬 Model Integrity

SHA-256 hash verification prevents model tampering.

### How It Works

1. Generate hashes for production models
2. Store in `models/hashes.json`
3. Verify on every model load

### Setup

```bash
# Generate hashes
python scripts/generate_model_hashes.py

# Enable strict mode
export STRICT_MODEL_INTEGRITY=true
```

### Verification Output

```json
{
  "xgb_fee_1block_latest.json": "a1b2c3d4e5f6...",
  "lgbm_fee_1block_latest.txt": "f6e5d4c3b2a1..."
}
```

### Failure Behavior

- **Strict mode ON**: Model loading fails, error logged
- **Strict mode OFF**: Warning logged, model loads anyway

---

## 🚫 Error Sanitization

Error messages are sanitized in production to prevent information leakage.

### Production Mode

```json
{
  "error": "Internal server error",
  "timestamp": "2026-04-17T17:30:00Z"
}
```

### Development Mode

```json
{
  "error": "Internal server error",
  "detail": "Full traceback here...",
  "timestamp": "2026-04-17T17:30:00Z"
}
```

### Sensitive Patterns Filtered

- File paths (`/home/user/...`)
- Database connection strings
- Internal IP addresses
- Stack traces (in production)

---

## 🎨 Frontend Security

### Content Security Policy (CSP)

```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; 
               script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; 
               style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
               connect-src 'self' http://localhost:8000;
               frame-ancestors 'none';
               base-uri 'self';">
```

### XSS Prevention

- Input validation on all user inputs
- Output sanitization before DOM insertion
- API key stored securely (not in localStorage)

### Dependency Security

```bash
cd frontend-react
npm audit  # Check for vulnerabilities
npm run audit-fix  # Auto-fix where possible
```

---

## 🔧 Environment Variables

### Required Variables

| Variable | Production | Development | Description |
|----------|------------|-------------|-------------|
| `API_KEY` | ✅ Required | ❌ Optional | API authentication key |
| `ENV` | ✅ Required | ✅ Required | `production` or `development` |
| `ALLOWED_ORIGINS` | ✅ Required | ❌ Optional | Comma-separated CORS origins |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STRICT_MODEL_INTEGRITY` | `false` | Enforce strict model hash verification |
| `MODEL_HASHES_FILE` | `models/hashes.json` | Path to model hashes file |
| `LOG_LEVEL` | `info` | Logging level (debug, info, warning, error) |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |

### Example .env File

```bash
# Required
API_KEY=$(openssl rand -hex 32)
ENV=production
ALLOWED_ORIGINS=https://btc-fees.example.com,http://localhost:5173

# Optional but recommended
STRICT_MODEL_INTEGRITY=true
MODEL_HASHES_FILE=models/hashes.json
LOG_LEVEL=warning

# API settings
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 🧪 Security Verification

### Automated Verification

```bash
# Run security patch verification
python scripts/verify_security_patches.py

# Check frontend dependencies
python scripts/check_frontend_security.py

# Verify model integrity
python scripts/generate_model_hashes.py
```

### Manual Testing

```bash
# Test 1: API key required in production
curl http://localhost:8000/fees/predict
# Expected: {"detail":"API Key required"}

# Test 2: Valid API key works
curl -H "X-API-Key: your-key" http://localhost:8000/fees/predict
# Expected: 200 OK with predictions

# Test 3: Security headers present
curl -I http://localhost:8000/ | grep -E "X-|Strict-Transport"
# Expected: Multiple security headers

# Test 4: Rate limiting active
for i in {1..35}; do curl -s -H "X-API-Key: your-key" http://localhost:8000/health; done
# Expected: Some 429 responses after 30 requests
```

---

## 📊 Security Reports

- [Initial Pentest Report](../PENTEST_TECNICO_bitcoin-mempool-fee-predictor.md)
- [Post-Patch Verification](../PENTEST_VERIFICACION_POST_PATCH.md)
- [Patch Notes](../SECURITY_PATCH_NOTES.md)

---

## 🚨 Incident Response

### If You Suspect a Security Issue

1. **Immediately** rotate the API key:
   ```bash
   export API_KEY=$(openssl rand -hex 32)
   ```

2. Check logs for suspicious activity:
   ```bash
   tail -f logs/api.log | grep -E "401|403|429"
   ```

3. Verify model integrity:
   ```bash
   python scripts/generate_model_hashes.py --verify
   ```

4. Review GitHub Actions logs for unauthorized access

---

## 🔗 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
