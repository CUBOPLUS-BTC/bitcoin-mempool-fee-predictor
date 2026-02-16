# Deployment Guide

## Overview

This guide covers deployment options for the Bitcoin On-Chain Predictive Framework in various environments.

## Local Development

### Setup

1. Clone and install:
```bash
git clone https://github.com/marchelo23/bitcoin-onchain-framework.git
cd bitcoin-onchain-framework
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run the API:
```bash
uvicorn api.main:app --reload
```

## Production Deployment

### Option 1: Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/raw data/processed models/production logs

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Build and run:**
```bash
docker build -t bitcoin-onchain-framework .
docker run -p 8000:8000 --env-file .env bitcoin-onchain-framework
```

**Using Docker Compose:**
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
    restart: unless-stopped
```

Run:
```bash
docker-compose up -d
```

### Option 2: Cloud Deployment (AWS)

**Using EC2:**

1. Launch EC2 instance (t3.medium or larger)
2. SSH into instance
3. Install dependencies:
```bash
sudo apt update
sudo apt install python3.9 python3-pip
```

4. Clone and setup:
```bash
git clone https://github.com/marchelo23/bitcoin-onchain-framework.git
cd bitcoin-onchain-framework
pip install -r requirements.txt
```

5. Setup systemd service:
```bash
sudo nano /etc/systemd/system/btc-api.service
```

```ini
[Unit]
Description=Bitcoin On-Chain API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/bitcoin-onchain-framework
Environment="PATH=/home/ubuntu/.local/bin"
ExecStart=/usr/bin/python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

[Install]
WantedBy=multi-user.target
```

6. Start service:
```bash
sudo systemctl start btc-api
sudo systemctl enable btc-api
```

### Option 3: Heroku Deployment

1. Create `Procfile`:
```
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

2. Create `runtime.txt`:
```
python-3.9.16
```

3. Deploy:
```bash
heroku create bitcoin-onchain-api
git push heroku main
```

## Automated Training & Monitoring

### Cron Jobs for Data Updates

Edit crontab:
```bash
crontab -e
```

Add:
```bash
# Update data every 3 hours
0 */3 * * * cd /path/to/bitcoin-onchain-framework && /path/to/venv/bin/python scripts/live_predict.py

# Retrain models weekly (Sunday at 2 AM)
0 2 * * 0 cd /path/to/bitcoin-onchain-framework && /path/to/venv/bin/python -m src.train --all

# Daily monitoring
0 9 * * * cd /path/to/bitcoin-onchain-framework && /path/to/venv/bin/python scripts/monitor_daily.py
```

### GitHub Actions CI/CD

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          # Add your deployment commands here
```

## Monitoring & Logging

### Log Management

Configure loguru in production:
```python
from loguru import logger

logger.add(
    "logs/api_{time}.log",
    rotation="500 MB",
    retention="10 days",
    compression="zip"
)
```

### Metrics Collection

Use Prometheus for metrics:
```bash
pip install prometheus-fastapi-instrumentator
```

Add to `api/main.py`:
```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

## Environment Variables

**Required:**
- `API_HOST` - API host (default: 0.0.0.0)
- `API_PORT` - API port (default: 8000)
- `EXCHANGE_API_KEY` - Exchange API key
- `EXCHANGE_SECRET` - Exchange API secret

**Optional:**
- `LOG_LEVEL` - Logging level (default: INFO)
- `MODEL_VERSION` - Model version to use
- `ENABLE_MONITORING` - Enable monitoring (default: false)

## Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` as template
2. **Use HTTPS** in production - Configure SSL certificates
3. **Implement rate limiting** - Prevent API abuse
4. **Regular updates** - Keep dependencies updated
5. **Backup models** - Regular model and data backups

## Troubleshooting

### API won't start
```bash
# Check if port is in use
lsof -i :8000

# Check logs
tail -f logs/api.log
```

### Models not loading
```bash
# Verify model files exist
ls -la models/

# Check permissions
chmod -R 755 models/
```

### Out of memory
- Reduce `API_WORKERS`
- Use smaller batch sizes
- Consider larger instance type

## Scaling

### Horizontal Scaling

Use load balancer (nginx):
```nginx
upstream api_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    location / {
        proxy_pass http://api_backend;
    }
}
```

### Vertical Scaling

Recommended instance sizes:
- **Development:** 2 CPU, 4GB RAM
- **Production:** 4 CPU, 8GB RAM
- **High Load:** 8+ CPU, 16GB+ RAM

## Support

For deployment issues, please open an issue on GitHub or contact the maintainer.
