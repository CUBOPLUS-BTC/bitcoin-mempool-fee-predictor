#!/bin/bash
# Diagnose and fix prediction fetch errors

echo "=========================================="
echo "🔍 DIAGNÓSTICO DE CONEXIÓN BACKEND/FRONTEND"
echo "=========================================="
echo ""

# Check if backend is running
echo "1. Verificando si backend está corriendo..."
if pgrep -f "uvicorn.*api.main:app" > /dev/null; then
    echo "   ✅ Backend está corriendo"
else
    echo "   ❌ Backend NO está corriendo - Este es el problema!"
fi
echo ""

# Check if frontend is running
echo "2. Verificando si frontend está corriendo..."
if pgrep -f "vite" > /dev/null; then
    echo "   ✅ Frontend está corriendo"
else
    echo "   ❌ Frontend NO está corriendo"
fi
echo ""

# Test backend health
echo "3. Probando endpoint /health..."
HEALTH=$(curl -s http://localhost:8000/health 2>&1)
if [ -n "$HEALTH" ]; then
    echo "   ✅ Backend responde:"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    echo "   ❌ Backend no responde en http://localhost:8000"
fi
echo ""

# Test backend predict
echo "4. Probando endpoint /fees/predict..."
PREDICT=$(curl -s -H "X-API-Key: dev-test-key" http://localhost:8000/fees/predict 2>&1 | head -c 200)
if [ -n "$PREDICT" ] && [[ "$PREDICT" != *"error"* ]]; then
    echo "   ✅ Predict funciona:"
    echo "$PREDICT"
else
    echo "   ❌ Predict no funciona o retorna error"
    echo "$PREDICT"
fi
echo ""

# Test CORS
echo "5. Verificando CORS..."
curl -s -I -H "Origin: http://localhost:5173" http://localhost:8000/health 2>&1 | grep -i "access-control" || echo "   ⚠️  Headers CORS no visibles en preflight"
echo ""

echo "=========================================="
echo "🔧 SOLUCIÓN RÁPIDA"
echo "=========================================="
echo ""

# Activate venv
cd /home/chelo/antigravity/btc/bitcoin-onchain-framework
source venv/bin/activate

# Install missing dependencies
echo "Instalando dependencias faltantes (slowapi, redis, cryptography)..."
pip install slowapi redis cryptography -q 2>/dev/null

# Kill existing processes
echo "Deteniendo procesos existentes..."
pkill -f "uvicorn.*api.main:app" 2>/dev/null
pkill -f "vite" 2>/dev/null
sleep 2

# Start backend
echo ""
echo "🚀 Iniciando backend..."
export ENV=development
export API_KEY=dev-test-key
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 2>&1 > /tmp/backend.log &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend
echo "Esperando backend (6 segundos)..."
sleep 6

# Test backend
echo ""
echo "Probando backend..."
curl -s http://localhost:8000/health 2>&1 | python3 -m json.tool 2>/dev/null && echo "✅ Backend OK" || echo "❌ Backend error - revisa /tmp/backend.log"

# Start frontend
echo ""
echo "🚀 Iniciando frontend..."
cd frontend-react
export VITE_API_URL=http://localhost:8000
export VITE_API_KEY=dev-test-key
npm run dev -- --host 0.0.0.0 --port 5173 2>&1 > /tmp/frontend.log &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

sleep 4

echo ""
echo "=========================================="
echo "✅ SERVICIOS INICIADOS"
echo "=========================================="
echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Logs backend:  tail -f /tmp/backend.log"
echo "Logs frontend: tail -f /tmp/frontend.log"
echo ""
echo "Para detener: pkill -f uvicorn; pkill -f vite"
