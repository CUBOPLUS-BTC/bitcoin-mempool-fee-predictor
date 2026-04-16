# Bitcoin Mempool Fee Prediction Framework

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![XGBoost](https://img.shields.io/badge/XGBoost-1.7-orange)
![LightGBM](https://img.shields.io/badge/LightGBM-4.0-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![Security](https://img.shields.io/badge/Security-8.5%2F10-success)

##  Overview

**ML-powered Bitcoin mempool fee prediction system** that predicts the optimal fee rate (sats/vByte) needed to get your transaction confirmed in the next **1, 3, or 6 blocks**.

This framework replaces traditional static fee estimation with machine learning models (XGBoost + LightGBM ensemble) trained on real-time mempool congestion data, block timing patterns, and network state metrics.

**Core Capabilities:**
-  **Block Inclusion Prediction**: Fee rates for next 1, 3, or 6 blocks
-  **Mempool Congestion Analysis**: Real-time queue depth and pressure metrics
-  **Dual Model Ensemble**: XGBoost + LightGBM with conservative bias
-  **Cost Optimization**: Save vs always paying the highest fee
-  **Auto-Retraining**: Hourly model updates with validation
-  **Live API**: FastAPI on port 8000 (with security hardening)
-  **Security Hardened**: API key auth, rate limiting, CSP, model integrity checks

##  Tech Stack

- **Core:** Python 3.9+
- **ML/AI:** XGBoost, LightGBM, Scikit-learn
- **Data Processing:** Pandas, NumPy, PyArrow
- **API:** FastAPI + Uvicorn + SlowAPI (rate limiting)
- **Security:** API key auth, CORS, CSP, security headers, model integrity
- **Frontend:** React + TypeScript + Vite (with security patches)
- **Data Sources:** Mempool.space API + Bitcoin Core RPC

##  Architecture

```
Mempool.space API ─┐
                    ├─► Collector Daemon ─► Feature Engineering ─► Model Training ─► Inference ─► FastAPI
Bitcoin Core RPC ──┘      (every 2 min)     (congestion metrics)   (XGBoost+LGB)   (ensemble)   (port 1234)
```

### Key Components

| Component | File | Description |
|---|---|---|
| **Data Ingestion** | `src/ingestion.py` | Fetches mempool state from mempool.space API |
| **Feature Engineering** | `src/features.py` | Creates congestion, fee, block timing features |
| **XGBoost Training** | `src/train.py` | Trains multi-horizon XGBoost models |
| **LightGBM Training** | `src/train_lightgbm.py` | Trains LightGBM for ensemble |
| **Inference** | `src/inference.py` | Loads models with SHA-256 integrity verification |
| **Ensemble** | `src/ensemble.py` | Combines XGBoost + LightGBM predictions |
| **Backtesting** | `src/backtest.py` | Tests predictions against confirmed blocks |
| **API Server** | `api/main.py` | FastAPI with auth, rate limiting, security headers |
| **Security Module** | `api/security.py` | API key authentication |
| **Model Integrity** | `src/model_integrity.py` | SHA-256 hash verification for ML models |
| **Collector Daemon** | `scripts/collector_daemon.py` | 24/7 mempool data collection |
| **Auto Retrain** | `scripts/auto_retrain.py` | Hourly model retraining pipeline |

##  Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Bitcoin Core RPC credentials (optional)
```

### 3. Start Collecting Data

The collector daemon must run continuously to build your training dataset:

```bash
# Test collection (5 snapshots)
python scripts/collector_daemon.py --test-run

# Run continuously (every 2 minutes)
python scripts/collector_daemon.py
```

>  **Important:** You need ~30 days of data (~21,600 snapshots) for robust model training. Minimum viable: 7 days (~5,040 snapshots).

### 4. Feature Engineering

```bash
python scripts/phase1_feature_engineering.py
```

### 5. Train Models

```bash
# Train all horizons (1, 3, 6 blocks)
python -m src.train --all

# Train LightGBM (ensemble partner)
python -m src.train_lightgbm --all
```

### 6. Start the API

**Development (no API key required):**
```bash
cd api
ENV=development python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Production (API key required):**
```bash
# Set required environment variables
export API_KEY=$(openssl rand -hex 32)
export ENV=production
export ALLOWED_ORIGINS=https://yourdomain.com,http://localhost:5173

python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Access the API documentation at: `http://localhost:8000/docs` (development only)

### 7. Live Predictions

```bash
python scripts/live_predict.py --once
```

##  API Endpoints

**Authentication:** Most endpoints require `X-API-Key` header (except `/health` and `/`).

| Method | Endpoint | Auth | Rate Limit | Description |
|---|---|---|---|---|
| `GET` | `/fees/predict` | Required | 30/min | ML fee predictions for all horizons |
| `GET` | `/fees/current` | Optional | - | Raw current fees from mempool.space |
| `GET` | `/fees/history` | Required | 10/min | Prediction history (max 100 records) |
| `GET` | `/mempool/blocks` | Optional | - | Projected mempool blocks |
| `GET` | `/health` | None | - | Service health check |
| `GET` | `/models` | Required | 20/min | Loaded model information |

**Example with API Key:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/fees/predict
```

### Example: Fee Prediction Response

```json
{
  "timestamp": "2026-04-13T21:35:00Z",
  "mempool_snapshot": {
    "tx_count": 45230,
    "vsize_mb": 150.5,
    "blocks_last_hour": 7
  },
  "fee_predictions": {
    "1_block": {
      "predicted_fee_sat_vb": 42,
      "confidence_interval": [35, 52],
      "confidence_score": 0.87,
      "priority": "high"
    },
    "3_blocks": {
      "predicted_fee_sat_vb": 28,
      "confidence_interval": [22, 36],
      "priority": "medium"
    },
    "6_blocks": {
      "predicted_fee_sat_vb": 15,
      "confidence_interval": [10, 22],
      "priority": "low"
    }
  },
  "recommendation": "NORMAL"
}
```

##  Model Evaluation Metrics

Models are evaluated with fee-prediction-specific metrics:

| Metric | Description | Target |
|---|---|---|
| **Block Inclusion Accuracy** | % of predictions that would confirm the tx | >90% |
| **MAE (sats/vB)** | Average absolute fee error | <5 sat/vB |
| **Overpay Rate** | How much extra the user would pay | <10 sat/vB |
| **Stuck Rate** | % of predictions that would fail to confirm | <10% |
| **Savings vs Naive** | Cost savings vs always paying fastest fee | >15% |

##  Automation

### Collector Daemon (24/7)
```bash
# Run as systemd service or screen/tmux
python scripts/collector_daemon.py
```

### Auto-Retrain (every 1 hour)
```bash
# Add to crontab:
# 0 * * * * cd /path/to/project && python scripts/auto_retrain.py
python scripts/auto_retrain.py
```

##  Security

This project has undergone comprehensive security hardening following OWASP Top 10 guidelines. **Security Score: 8.5/10**

### Implemented Security Features

| Feature | Implementation | Status |
|---|---|---|
| **API Authentication** | API Key (`X-API-Key` header) | ✅ Active |
| **Rate Limiting** | 30/10/20 req/min per endpoint | ✅ Active |
| **CORS** | Whitelist-based origin validation | ✅ Active |
| **Security Headers** | 7 headers including CSP, HSTS | ✅ Active |
| **Model Integrity** | SHA-256 hash verification | ✅ Active |
| **Error Sanitization** | No internal details exposed | ✅ Active |
| **Dependency Audit** | pip-audit + npm audit | ✅ Active |

### Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required for production
API_KEY=$(openssl rand -hex 32)
ENV=production
ALLOWED_ORIGINS=https://yourdomain.com,http://localhost:5173

# Optional: Strict model integrity
STRICT_MODEL_INTEGRITY=true
MODEL_HASHES_FILE=models/hashes.json
```

### Verification Scripts

```bash
# Verify API security patches
python scripts/verify_security_patches.py

# Check frontend dependencies
python scripts/check_frontend_security.py

# Generate model hashes
python scripts/generate_model_hashes.py
```

### Pentest Reports

- [Initial Pentest Report](PENTEST_TECNICO_bitcoin-mempool-fee-predictor.md)
- [Post-Patch Verification](PENTEST_VERIFICACION_POST_PATCH.md)
- [Security Patch Notes](SECURITY_PATCH_NOTES.md)

##  Data Sources

### Primary: Mempool.space API
- **Recommended fees**: `GET /api/v1/fees/recommended`
- **Mempool state**: `GET /api/mempool`
- **Projected blocks**: `GET /api/v1/fees/mempool-blocks`
- **Recent blocks**: `GET /api/v1/blocks`
- **Difficulty**: `GET /api/v1/difficulty-adjustment`

### Complementary: Bitcoin Core RPC
- **getmempoolinfo**: Mempool size, usage, min fee
- **estimatesmartfee**: Node's fee estimation for comparison
- **getblockchaininfo**: Chain state

##  Author

**Marcelo Guerra**
CUBO+ Developer & ESEN Student
El Salvador Bitcoin Community

##  License

This project is open-source and intended for educational and research purposes within the Bitcoin ecosystem.

---

**Note:** This framework predicts network fees based on current congestion data. Always verify predictions and add appropriate safety margins for critical transactions.
