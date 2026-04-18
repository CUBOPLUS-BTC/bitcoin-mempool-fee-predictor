#!/bin/bash
export ENV=development
export API_KEY=dev-test-key
export PYTHONUNBUFFERED=1

cd /home/chelo/antigravity/btc/bitcoin-onchain-framework

# Activate venv
source venv/bin/activate

# Install missing dependencies
echo "Installing dependencies..."
pip install slowapi redis cryptography -q

# Kill existing backend
pkill -f "uvicorn.*api.main:app" 2>/dev/null
sleep 2

echo "Starting backend on http://localhost:8000 ..."
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 &
BPID=$!
sleep 6

echo "Testing health endpoint..."
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Health check failed - check logs"
echo ""
echo "Backend PID: $BPID"
echo "Test predict endpoint:"
curl -s -H "X-API-Key: dev-test-key" http://localhost:8000/fees/predict 2>&1 | head -1 || echo "Predict endpoint not ready yet"
echo ""
echo "View logs: tail -f /tmp/uvicorn.log"
