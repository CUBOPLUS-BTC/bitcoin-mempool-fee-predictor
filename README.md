# Bitcoin Mempool Fee Prediction Framework

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![XGBoost](https://img.shields.io/badge/XGBoost-1.7-orange)
![LightGBM](https://img.shields.io/badge/LightGBM-4.0-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

##  Overview

**ML-powered Bitcoin mempool fee prediction system** that predicts the optimal fee rate (sats/vByte) needed to get your transaction confirmed in the next **1, 3, or 6 blocks**.

This framework replaces traditional static fee estimation with machine learning models (XGBoost + LightGBM ensemble) trained on real-time mempool congestion data, block timing patterns, and network state metrics.

**Core Capabilities:**
-  **Block Inclusion Prediction**: Fee rates for next 1, 3, or 6 blocks
-  **Mempool Congestion Analysis**: Real-time queue depth and pressure metrics
-  **Dual Model Ensemble**: XGBoost + LightGBM with conservative bias
-  **Cost Optimization**: Save vs always paying the highest fee
-  **Auto-Retraining**: Hourly model updates with validation
-  **Live API**: FastAPI on port 1234

##  Tech Stack

- **Core:** Python 3.9+
- **ML/AI:** XGBoost, LightGBM, Scikit-learn
- **Data Processing:** Pandas, NumPy, PyArrow
- **API:** FastAPI (model serving on port 1234)
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
| **Inference** | `src/inference.py` | Loads models, makes fee predictions |
| **Ensemble** | `src/ensemble.py` | Combines XGBoost + LightGBM predictions |
| **Backtesting** | `src/backtest.py` | Tests predictions against confirmed blocks |
| **API Server** | `api/main.py` | FastAPI server for real-time predictions |
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

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 1234 --reload
```

Access the API documentation at: `http://localhost:1234/docs`

### 7. Live Predictions

```bash
python scripts/live_predict.py --once
```

##  API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/fees/predict` | ML fee predictions for all horizons |
| `GET` | `/fees/current` | Raw current fees from mempool.space |
| `GET` | `/fees/history` | Prediction history with validation stats |
| `GET` | `/mempool/blocks` | Projected mempool blocks |
| `GET` | `/health` | Service health check |
| `GET` | `/models` | Loaded model information |

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
