# 📡 API Reference

Complete reference for the Bitcoin Mempool Fee Predictor API.

**Base URL**: `http://localhost:8000` (default)

## 🔐 Authentication

Most endpoints require authentication via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/fees/predict
```

**Public endpoints** (no auth required):
- `GET /`
- `GET /health`

## 📝 Endpoints

### Health Check

Check if the API is running.

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-17T17:30:00Z"
}
```

---

### Fee Prediction

Get ML-based fee predictions for all horizons.

```http
GET /fees/predict
```

**Headers:**
- `X-API-Key: your-api-key` (required)

**Rate Limit:** 30 requests per minute

**Response:**
```json
{
  "timestamp": "2026-04-17T17:30:00Z",
  "mempool_snapshot": {
    "tx_count": 45230,
    "vsize_mb": 150.5,
    "blocks_last_hour": 7,
    "avg_fee_1h": 12.3
  },
  "current_fees": {
    "minimumFee": 1.0,
    "economyFee": 3.5,
    "hourFee": 8.2,
    "halfHourFee": 12.1,
    "fastestFee": 18.5
  },
  "fee_predictions": {
    "1_block": {
      "predicted_fee_sat_vb": 20.5,
      "confidence_interval": [18.2, 22.8],
      "confidence_score": 0.85,
      "priority": "high",
      "models_used": ["xgb", "lgbm"],
      "individual_predictions": {
        "xgb": 21.2,
        "lgbm": 19.8
      }
    },
    "3_block": { ... },
    "6_block": { ... }
  },
  "recommendation": {
    "urgent": 20.5,
    "normal": 12.1,
    "economic": 8.2,
    "best_value": "3_block"
  }
}
```

**Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 timestamp of prediction |
| `predicted_fee_sat_vb` | float | Recommended fee rate in satoshis/vByte |
| `confidence_interval` | array | [low, high] confidence bounds |
| `confidence_score` | float | 0-1 confidence in prediction |
| `priority` | string | high/medium/low based on mempool pressure |
| `models_used` | array | Which ML models contributed |
| `recommendation` | object | Curated fee suggestions for different urgency |

---

### Current Fees

Get raw current fees from mempool.space (no ML prediction).

```http
GET /fees/current
```

**Rate Limit:** None

**Response:**
```json
{
  "minimumFee": 1.0,
  "economyFee": 3.5,
  "hourFee": 8.2,
  "halfHourFee": 12.1,
  "fastestFee": 18.5,
  "timestamp": "2026-04-17T17:30:00Z"
}
```

---

### Prediction History

Get historical predictions with validation.

```http
GET /fees/history?limit=50
```

**Parameters:**
- `limit` (optional): Max records to return (default: 100, max: 1000)

**Headers:**
- `X-API-Key: your-api-key` (required)

**Rate Limit:** 10 requests per minute

**Response:**
```json
{
  "count": 50,
  "predictions": [
    {
      "timestamp": "2026-04-17T16:00:00Z",
      "actual_fee": 15.2,
      "predicted_fee": 14.8,
      "error": 0.4,
      "accuracy": 0.97
    }
  ]
}
```

---

### Mempool Blocks

Get projected mempool blocks.

```http
GET /mempool/blocks
```

**Rate Limit:** None

**Response:**
```json
{
  "blocks": [
    {
      "blockVSize": 1000000,
      "transactionCount": 2850,
      "minFee": 12.0,
      "medianFee": 18.5,
      "maxFee": 45.2
    }
  ],
  "timestamp": "2026-04-17T17:30:00Z"
}
```

---

### Model Information

Get information about loaded ML models.

```http
GET /models
```

**Headers:**
- `X-API-Key: your-api-key` (required)

**Rate Limit:** 20 requests per minute

**Response:**
```json
{
  "loaded_models": [
    {
      "name": "xgb_fee_1block",
      "type": "xgboost",
      "version": "2.1.0",
      "features": ["vsize_mb", "tx_count", "blocks_last_hour", ...],
      "last_trained": "2026-04-17T12:00:00Z",
      "hash_verified": true
    }
  ],
  "integrity_status": "verified",
  "timestamp": "2026-04-17T17:30:00Z"
}
```

---

## ⚠️ Error Responses

### 401 Unauthorized

Missing or invalid API key.

```json
{
  "detail": "API Key required"
}
```

### 403 Forbidden

API key valid but not authorized for this resource.

```json
{
  "detail": "Invalid API Key"
}
```

### 429 Too Many Requests

Rate limit exceeded.

```json
{
  "detail": "Rate limit exceeded"
}
```

### 500 Internal Server Error

Server error (details sanitized in production).

```json
{
  "error": "Internal server error",
  "timestamp": "2026-04-17T17:30:00Z"
}
```

## 🔒 Security Headers

All responses include:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=63072000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

## 📊 Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/fees/predict` | 30 | 1 minute |
| `/fees/history` | 10 | 1 minute |
| `/models` | 20 | 1 minute |
| `/health`, `/`, `/fees/current` | No limit | - |

## 🧪 Testing

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Predict fees (with API key)
curl -H "X-API-Key: dev-key-123" http://localhost:8000/fees/predict

# Get current fees (no auth)
curl http://localhost:8000/fees/current

# Get model info
curl -H "X-API-Key: dev-key-123" http://localhost:8000/models
```

### Python Example

```python
import requests

API_URL = "http://localhost:8000"
API_KEY = "your-api-key"

headers = {"X-API-Key": API_KEY}

# Get predictions
response = requests.get(f"{API_URL}/fees/predict", headers=headers)
predictions = response.json()

print(f"1-block fee: {predictions['fee_predictions']['1_block']['predicted_fee_sat_vb']} sat/vB")
```

### JavaScript Example

```javascript
const API_URL = 'http://localhost:8000';
const API_KEY = 'your-api-key';

async function getPredictions() {
  const response = await fetch(`${API_URL}/fees/predict`, {
    headers: { 'X-API-Key': API_KEY }
  });
  const data = await response.json();
  console.log('Recommended fee:', data.fee_predictions['1_block'].predicted_fee_sat_vb);
}
```

## 📚 See Also

- [Installation Guide](./installation.md)
- [Security Guide](./security.md)
- [Architecture](./architecture.md)
