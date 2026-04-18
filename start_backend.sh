#!/bin/bash
export ENV=development
export API_KEY=dev-test-key
export PYTHONUNBUFFERED=1

cd /home/chelo/antigravity/btc/bitcoin-onchain-framework

# Check if already running
if pgrep -f "uvicorn.*api.main:app" > /dev/null; then
    echo "Backend already running!"
    exit 0
fi

echo "Starting backend on http://localhost:8000 ..."
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 &
BPID=$!
sleep 5

echo "Testing health endpoint..."
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Health check failed"

echo "Backend PID: $BPID"
