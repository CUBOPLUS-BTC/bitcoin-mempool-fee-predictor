# 📦 Installation Guide

Complete guide for setting up the Bitcoin Mempool Fee Predictor.

## Prerequisites

- **Python**: 3.9 or higher
- **Node.js**: 18.x or higher (for frontend)
- **Git**: For cloning the repository
- **Bitcoin Core**: Optional, for RPC data source

## 🐍 Backend Installation

### 1. Clone Repository

```bash
git clone https://github.com/CUBOPLUS-BTC/bitcoin-mempool-fee-predictor.git
cd bitcoin-mempool-fee-predictor
```

### 2. Create Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n fee-predictor python=3.11
conda activate fee-predictor
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required for production:**
```bash
# Generate secure API key
export API_KEY=$(openssl rand -hex 32)
export ENV=production
export ALLOWED_ORIGINS=https://yourdomain.com,http://localhost:5173
```

**Development:**
```bash
export ENV=development  # No API key required
```

### 5. Verify Installation

```bash
python -c "import src.inference; print('✅ Backend OK')"
```

## ⚛️ Frontend Installation

### 1. Navigate to Frontend

```bash
cd frontend-react
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API key and URL
```

Example `.env`:
```env
VITE_API_URL=http://localhost:8000
VITE_API_KEY=your-api-key-here
```

### 4. Start Development Server

```bash
npm run dev
```

Frontend will be available at `http://localhost:5173`

## 🐳 Docker Installation (Alternative)

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f api
```

### Manual Docker

```bash
# Build image
docker build -t fee-predictor .

# Run container
docker run -p 8000:8000 \
  -e API_KEY=your-key \
  -e ENV=production \
  fee-predictor
```

## 🔧 Model Setup

### Download Pre-trained Models

Models are automatically downloaded on first run, or you can:

```bash
# Place models in the models/production/ directory
ls models/production/
# Should contain: xgb_fee_*block_latest.json, lgbm_fee_*block_latest.txt
```

### Generate Model Hashes (Optional but Recommended)

```bash
python scripts/generate_model_hashes.py
```

This creates `models/hashes.json` for integrity verification.

## ✅ Verification

### Backend Verification

```bash
# Start API
ENV=development python -m uvicorn api.main:app --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

### Frontend Verification

```bash
cd frontend-react
npm run audit  # Should show 0 vulnerabilities
npm run dev
```

### Full System Test

```bash
python scripts/verify_security_patches.py
```

## 🚀 Next Steps

1. **[API Reference](./api-reference.md)** - Learn how to use the API
2. **[Security Guide](./security.md)** - Configure security settings
3. **[Architecture](./architecture.md)** - Understand the system design

## 🐛 Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'src'`
**Solution**: Run from project root or install in editable mode:
```bash
pip install -e .
```

**Issue**: `API_KEY required in production`
**Solution**: Set environment variable:
```bash
export API_KEY=$(openssl rand -hex 32)
```

**Issue**: Frontend shows 403 Forbidden
**Solution**: Configure API key in frontend `.env`:
```bash
VITE_API_KEY=your-api-key
```

See [FAQ](./faq.md) for more troubleshooting tips.
