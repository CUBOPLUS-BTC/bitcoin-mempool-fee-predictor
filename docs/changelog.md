# 📝 Changelog

All notable changes to the Bitcoin Mempool Fee Predictor.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] - 2026-04-16

### 🔒 Security (Major Update)

**Security Score: 5.8/10 → 8.5/10**

#### Added
- **API Key Authentication** (`api/security.py`)
  - `X-API-Key` header authentication for all endpoints
  - Required in production, optional in development
  - Secure key generation utilities

- **Rate Limiting** (`slowapi`)
  - 30 req/min for `/fees/predict`
  - 10 req/min for `/fees/history`
  - 20 req/min for `/models`
  - IP-based rate limiting

- **Security Headers Middleware** (`api/middleware/security_headers.py`)
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 1; mode=block
  - Strict-Transport-Security (HSTS)
  - Content-Security-Policy
  - Referrer-Policy
  - Permissions-Policy

- **Model Integrity Verification** (`src/model_integrity.py`)
  - SHA-256 hash generation for models
  - Integrity check before loading
  - Strict mode option for production
  - Script to generate hashes

- **CORS Security**
  - Whitelist-based origin validation
  - Removed wildcard with credentials
  - Configurable via `ALLOWED_ORIGINS`

- **Error Sanitization**
  - Generic error messages in production
  - Internal details hidden
  - Sensitive patterns filtered

- **Frontend Security**
  - Content Security Policy (CSP) meta tags
  - XSS prevention in React components
  - Input validation and sanitization
  - API key secure handling

#### Fixed
- **Uvicorn Reload**: Disabled in production (`ENV=production`)
- **GitHub Actions**: Pinned to specific SHA versions
  - `actions/checkout@v4.2.2` → SHA pinned
  - `actions/setup-python@v5.0.0` → SHA pinned
  - `git-auto-commit-action@v5.0.1` → replaced with manual git commands
- **Frontend Dependencies**: Updated vulnerable npm packages
  - `vite`: ^5.0.8 → ^6.0.7
  - `react`: ^18.2.0 → ^18.3.1
  - `lucide-react`: fixed version
  - `esbuild`: override to ^0.24.2
  - 8 vulnerabilities resolved

### 📚 Documentation

#### Added
- Complete documentation folder (`docs/`)
  - Installation guide
  - API reference
  - Security guide
  - Architecture documentation
  - Contributing guide
  - FAQ
  - Changelog (this file)
- Security patch notes (`SECURITY_PATCH_NOTES.md`)
- Post-patch verification report (`PENTEST_VERIFICACION_POST_PATCH.md`)

### 🔧 Scripts

#### Added
- `scripts/verify_security_patches.py` - Automated security verification
- `scripts/check_frontend_security.py` - Frontend dependency checker
- `scripts/generate_model_hashes.py` - Model integrity hash generator

### 🛠️ Changed

- **API Endpoints**: Added authentication and rate limiting columns
- **README**: Updated with security features and badges
- **Environment Variables**: Added security-related variables
- **Package.json**: Updated all dependencies to secure versions

---

## [1.5.0] - 2026-04-10

### Added
- LightGBM ensemble models
- Ensemble confidence intervals
- Model metadata tracking
- GitHub Actions workflows for auto-retraining

### Changed
- Improved feature engineering with time-based features
- Enhanced backtesting with walk-forward validation
- Updated config format

---

## [1.4.0] - 2026-04-05

### Added
- React frontend with TypeScript
- Real-time mempool visualization
- Model performance dashboard

### Changed
- API port standardized to 8000
- Improved error handling

---

## [1.3.0] - 2026-03-28

### Added
- Multi-horizon predictions (1, 3, 6 blocks)
- Historical prediction tracking
- Validation metrics storage

### Fixed
- Memory leak in collector daemon
- Race condition in model loading

---

## [1.2.0] - 2026-03-20

### Added
- Bitcoin Core RPC integration
- Fee recommendation engine
- Priority level classification

### Changed
- Refactored inference pipeline
- Improved caching strategy

---

## [1.1.0] - 2026-03-15

### Added
- XGBoost model training pipeline
- Feature importance tracking
- Model evaluation metrics

### Fixed
- API timeout issues
- Snapshot data corruption

---

## [1.0.0] - 2026-03-10

### Added
- Initial release
- FastAPI backend
- Mempool.space integration
- Basic fee prediction
- Collector daemon
- Docker support

---

## 🏷️ Versioning Notes

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes requiring user intervention
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

---

## 📊 Security Score History

| Version | Score | Notes |
|---------|-------|-------|
| 1.0.0 - 1.5.0 | 5.8/10 | Basic functionality, minimal security |
| 2.0.0 | 8.5/10 | Comprehensive security hardening |

---

## 🔮 Planned for Future Versions

### [2.1.0] - Planned
- Redis for distributed rate limiting
- PostgreSQL for prediction history
- WebSocket support for real-time updates
- Advanced analytics dashboard

### [2.2.0] - Planned
- Kubernetes deployment guides
- Horizontal scaling support
- Model A/B testing framework
- Custom model upload API

### [3.0.0] - Planned
- REST API v2 with breaking improvements
- gRPC support
- Multi-chain support (Liquid, Lightning)
- Advanced ML models (Neural Networks)

---

## 🙏 Contributors

Thank you to all contributors who have helped improve this project!

### Version 2.0.0 Security Patch
- Security audit and pentest
- Vulnerability patching
- Documentation updates

---

*For more details on specific changes, see the commit history on GitHub.*
