# 🏗️ Architecture

System architecture and data flow documentation.

---

## 📊 High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Mempool.space  │     │  Bitcoin Core   │
│     API         │     │      RPC        │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Collector Daemon    │  ← Runs every 2 minutes
         │  (scripts/collector)  │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │  Data Ingestion Layer │
         │   (src/ingestion.py)  │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │ Feature Engineering   │
         │   (src/features.py)   │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │    ML Models          │
         │ ┌─────────┬─────────┐ │
         │ │ XGBoost │LightGBM│ │ ← Ensemble prediction
         │ └────┬────┴────┬────┘ │
         └──────┼─────────┼──────┘
                └────┬────┘
                     │
         ┌───────────▼───────────┐
         │  Ensemble & Inference │
         │   (src/ensemble.py)   │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   FastAPI Server    │  ← Port 8000
         │    (api/main.py)     │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Frontend (React)   │  ← Port 5173
         │  (frontend-react/)    │
         └───────────────────────┘
```

---

## 🔄 Data Flow

### 1. Data Collection

**Frequency**: Every 2 minutes

**Process**:
```
mempool.space API → JSON snapshots → data/snapshots/
                                    ↓
                         Consolidated parquet
                         (mempool_consolidated.parquet)
```

**Key Data Points**:
- Transaction count in mempool
- Virtual size (MB)
- Fee distribution histogram
- Block arrival rate
- Recommended fees (from API)

### 2. Feature Engineering

**Input**: Raw mempool snapshots

**Output**: Feature vectors for ML models

| Feature | Description | Source |
|---------|-------------|--------|
| `vsize_mb` | Mempool size in MB | mempool.space |
| `tx_count` | Number of pending transactions | mempool.space |
| `avg_fee_1h` | Average fee last hour | Calculated |
| `fee_percentile_10` | 10th percentile fee | mempool.space |
| `blocks_last_hour` | Blocks found in last hour | mempool.space |
| `congestion_ratio` | tx_count / (blocks * 4000) | Calculated |
| `time_of_day` | Hour of day (0-23) | Derived |
| `day_of_week` | Day of week (0-6) | Derived |

### 3. Model Training

**XGBoost Models**:
```
Input: Feature vector (8-12 features)
Output: Predicted fee for 1, 3, or 6 block horizon
Training: Every hour via GitHub Actions
Format: JSON (model + metadata)
```

**LightGBM Models**:
```
Input: Same feature vector
Output: Alternative prediction
Training: Every hour via GitHub Actions
Format: Text (LightGBM native)
```

### 4. Ensemble Prediction

**Weighting**:
- XGBoost: 60% (conservative)
- LightGBM: 40%

**Formula**:
```
predicted_fee = (xgb_pred * 0.6) + (lgbm_pred * 0.4)
```

**Confidence Calculation**:
```
confidence = 1 - (std_dev / predicted_fee)
confidence_interval = [pred - 1.96*std, pred + 1.96*std]
```

### 5. API Serving

**FastAPI Endpoints**:
- `/fees/predict` - ML predictions
- `/fees/current` - Raw mempool.space fees
- `/fees/history` - Historical predictions
- `/mempool/blocks` - Projected blocks
- `/models` - Model information
- `/health` - Health check

**Security Layers**:
1. CORS validation
2. API key authentication
3. Rate limiting
4. Input validation
5. Security headers

---

## 📁 Directory Structure

```
bitcoin-onchain-framework/
├── api/                          # FastAPI application
│   ├── main.py                   # API entry point
│   ├── security.py               # Authentication
│   └── middleware/               # Security middleware
│       └── security_headers.py
│
├── src/                          # Core ML & data code
│   ├── ingestion.py            # Data fetching
│   ├── features.py               # Feature engineering
│   ├── train.py                  # XGBoost training
│   ├── train_lightgbm.py         # LightGBM training
│   ├── inference.py              # Model loading & prediction
│   ├── ensemble.py               # Ensemble logic
│   ├── backtest.py               # Model validation
│   └── model_integrity.py        # Hash verification
│
├── scripts/                      # Automation scripts
│   ├── collector_daemon.py       # 24/7 data collection
│   ├── auto_retrain.py           # Hourly retraining
│   ├── retrain_fee_model.py      # Model training
│   ├── promote_best_models.py    # Model selection
│   ├── live_predict.py           # Live predictions
│   └── generate_model_hashes.py  # Integrity hashes
│
├── frontend-react/               # React frontend
│   ├── src/
│   │   ├── hooks/useApi.ts       # API client
│   │   ├── components/           # React components
│   │   └── types/api.ts          # TypeScript types
│   ├── package.json
│   └── vite.config.ts
│
├── models/                       # Trained models
│   ├── production/               # Current production models
│   ├── xgb_fee_*_latest.json     # XGBoost models
│   ├── lgbm_fee_*_latest.txt     # LightGBM models
│   └── hashes.json               # SHA-256 hashes
│
├── data/                         # Training data
│   └── snapshots/                # Raw mempool data
│
├── config/                       # Configuration
│   └── config.yaml               # Main config
│
├── tests/                        # Test suite
├── docs/                         # Documentation
└── .github/workflows/             # CI/CD automation
```

---

## 🔧 Component Details

### Collector Daemon

**File**: `scripts/collector_daemon.py`

**Purpose**: Continuously collect mempool data

**Schedule**: Every 2 minutes

**Output**:
- `data/snapshots/mempool_snapshot_*.json`
- `data/snapshots/mempool_consolidated.parquet`

**GitHub Actions**: Runs 24/7 via `live_fee_prediction.yml`

### Feature Engineering

**File**: `src/features.py`

**Purpose**: Transform raw data into ML features

**Key Functions**:
- `create_features()`: Main feature creation
- `add_time_features()`: Time-based features
- `calculate_congestion()`: Mempool pressure metrics

### XGBoost Training

**File**: `src/train.py`

**Purpose**: Train fee prediction models

**Hyperparameters**:
```python
{
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 200,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'objective': 'reg:squarederror'
}
```

**Training Frequency**: Hourly

**Validation**: Walk-forward validation

### Ensemble Logic

**File**: `src/ensemble.py`

**Purpose**: Combine XGBoost + LightGBM predictions

**Algorithm**:
1. Load both models
2. Verify integrity (SHA-256)
3. Make individual predictions
4. Weighted average (60/40)
5. Calculate confidence interval
6. Determine priority level

### FastAPI Server

**File**: `api/main.py`

**Key Features**:
- Async request handling
- Automatic OpenAPI documentation
- Middleware stack:
  - CORS validation
  - Security headers
  - Rate limiting
  - Error handling

**Security**:
- API key authentication
- Rate limiting (slowapi)
- CORS whitelist
- Sanitized error messages

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflows

#### 1. Auto-Retrain (`auto_retrain.yml`)

**Trigger**: Every hour

**Steps**:
1. Collect 80 mempool snapshots
2. Consolidate data
3. Train XGBoost + LightGBM models
4. Validate on recent data
5. Promote best models
6. Commit to repository

#### 2. Live Prediction (`live_fee_prediction.yml`)

**Trigger**: Every 10 minutes

**Steps**:
1. Verify models exist
2. Collect current snapshot
3. Run live prediction
4. Save to predictions/
5. Commit results

#### 3. Ensemble Validation (`ensemble_validation.yml`)

**Trigger**: Every hour

**Steps**:
1. Load latest predictions
2. Compare with actual fees
3. Calculate accuracy metrics
4. Generate validation report

#### 4. CI Tests (`ci_test.yml`)

**Trigger**: On push/PR

**Steps**:
1. Lint with flake8
2. Run unit tests
3. Test API connectivity
4. Security scan with bandit

---

## 📊 Data Storage

### Raw Snapshots

**Format**: JSON
**Location**: `data/snapshots/`
**Retention**: Last 30 days (configurable)

```json
{
  "timestamp": "2026-04-17T17:30:00Z",
  "mempool": {
    "vsize": 150500000,
    "count": 45230
  },
  "fees": {
    "fastestFee": 18.5,
    "halfHourFee": 12.1,
    "hourFee": 8.2
  }
}
```

### Consolidated Data

**Format**: Parquet
**Location**: `data/snapshots/mempool_consolidated.parquet`
**Purpose**: Efficient ML training

### Model Files

**XGBoost**: `models/xgb_fee_{horizon}block_latest.json`
- Model parameters
- Feature importance
- Training metadata

**LightGBM**: `models/lgbm_fee_{horizon}block_latest.txt`
- Native LightGBM format
- Optimized for inference

### Predictions

**Location**: `predictions/ensemble_predictions.csv`
**Format**: CSV with timestamp, predictions, actual fees

---

## 🚀 Scaling Considerations

### Current Limitations

- Single-node API (no horizontal scaling)
- File-based model storage
- In-memory rate limiting

### Future Improvements

1. **Redis** for distributed rate limiting
2. **S3/GCS** for model storage
3. **Kubernetes** for horizontal scaling
4. **PostgreSQL** for prediction history

---

## 📚 See Also

- [API Reference](./api-reference.md)
- [Installation Guide](./installation.md)
- [Security Guide](./security.md)
