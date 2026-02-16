# API Guide

## Overview

The Bitcoin On-Chain Framework provides a RESTful API built with FastAPI for serving model predictions and accessing framework functionality.

## Quick Start

### Starting the API Server

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

For production:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Access Interactive Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## API Endpoints

### Health Check

**Endpoint:** `GET /`

**Description:** Check if the API is running

**Response:**
```json
{
  "status": "ok",
  "message": "Bitcoin On-Chain Predictive Framework API"
}
```

### Get Predictions

**Endpoint:** `GET /api/v1/predict`

**Description:** Get current Bitcoin price predictions for all horizons

**Response:**
```json
{
  "timestamp": "2024-02-15T18:00:00Z",
  "current_price": 52000.00,
  "predictions": {
    "30min": {
      "predicted_price": 52100.00,
      "change_percent": 0.19,
      "confidence": "medium"
    },
    "60min": {
      "predicted_price": 52300.00,
      "change_percent": 0.58,
      "confidence": "medium"
    },
    "180min": {
      "predicted_price": 52800.00,
      "change_percent": 1.54,
      "confidence": "low"
    }
  },
  "model_version": "20240215_120000"
}
```

### Historical Predictions

**Endpoint:** `GET /api/v1/history`

**Query Parameters:**
- `start_date` (optional): ISO format date
- `end_date` (optional): ISO format date
- `limit` (optional): Number of records (default: 100)

**Response:**
```json
{
  "data": [
    {
      "timestamp": "2024-02-15T17:00:00Z",
      "predictions": {...}
    }
  ],
  "count": 100
}
```

### Model Metrics

**Endpoint:** `GET /api/v1/metrics`

**Description:** Get current model performance metrics

**Response:**
```json
{
  "models": {
    "30min": {
      "rmse": 0.0234,
      "mae": 0.0189,
      "r2_score": 0.76,
      "directional_accuracy": 0.68
    },
    "60min": {...},
    "180min": {...}
  },
  "last_updated": "2024-02-15T12:00:00Z"
}
```

## Authentication

Currently, the API does not require authentication for read-only endpoints. For production deployment, consider implementing:
- API key authentication
- JWT tokens
- Rate limiting per client

## Error Handling

The API uses standard HTTP status codes:

- `200 OK` - Request successful
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

**Error Response Format:**
```json
{
  "error": "Error message",
  "detail": "Detailed error information"
}
```

## Rate Limiting

Current limits:
- 60 requests per minute per IP
- 1000 requests per hour per IP

## CORS Configuration

For development, CORS is enabled for all origins. For production, configure allowed origins in `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## Example Usage

### Python

```python
import requests

# Get predictions
response = requests.get("http://localhost:8000/api/v1/predict")
data = response.json()

print(f"Current Price: ${data['current_price']}")
print(f"30min Prediction: ${data['predictions']['30min']['predicted_price']}")
```

### cURL

```bash
curl http://localhost:8000/api/v1/predict
```

### JavaScript

```javascript
fetch('http://localhost:8000/api/v1/predict')
  .then(response => response.json())
  .then(data => console.log(data));
```

## Production Deployment

### Using Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

Set these in production:
```bash
export API_HOST=0.0.0.0
export API_PORT=8000
export API_WORKERS=4
export LOG_LEVEL=INFO
```

## Monitoring

The API provides a `/health` endpoint for monitoring:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "uptime": 3600,
  "models_loaded": true
}
```
