#!/bin/bash
export NODE_ENV=development
export VITE_API_URL=http://localhost:8000
export VITE_API_KEY=dev-test-key

cd /home/chelo/antigravity/btc/bitcoin-onchain-framework/frontend-react

# Check if already running
if pgrep -f "vite" > /dev/null; then
    echo "Frontend already running!"
    exit 0
fi

echo "Starting frontend on http://localhost:5173 ..."
npm run dev -- --host 0.0.0.0 --port 5173 2>&1 &
sleep 5

echo "Frontend should be available at http://localhost:5173"
curl -s http://localhost:5173 2>&1 | head -3 || echo "Frontend still loading..."
