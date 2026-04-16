import { useState, useEffect, useCallback } from 'react';
import type { PredictResponse, CurrentFeesResponse, HealthResponse, LogEntry, LogType } from '../types/api';

// Security: Dynamic API base URL
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Security: API key from environment (NEVER hardcode)
const API_KEY = import.meta.env.VITE_API_KEY || localStorage.getItem('api_key') || '';

// Security: Validate numeric inputs
function validateNumber(value: number, min: number, max: number): number | null {
  const num = parseFloat(String(value));
  return !isNaN(num) && num >= min && num <= max ? num : null;
}

// Security: Sanitize string to prevent XSS
function sanitize(str: string): string {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

export function useApi() {
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [currentFees, setCurrentFees] = useState<CurrentFeesResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addLog = useCallback((msg: string, type: LogType = 'info') => {
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
    setLogs(prev => [{ time: timestamp, msg, type }, ...prev].slice(0, 20));
  }, []);

  const fetchPrediction = useCallback(async () => {
    try {
      setLoading(true);
      addLog('Running ensemble prediction...', 'info');
      
      // Security: Include API key in headers
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (API_KEY) {
        headers['X-API-Key'] = API_KEY;
      }
      
      const res = await fetch(`${API_BASE}/fees/predict?use_ensemble=true`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
      const data: PredictResponse = await res.json();
      
      // Security: Validate prediction values
      const p1 = data.fee_predictions['1_block'];
      const p3 = data.fee_predictions['3_blocks'];
      const p6 = data.fee_predictions['6_blocks'];
      
      if (!validateNumber(p1.predicted_fee_sat_vb, 1, 10000) ||
          !validateNumber(p3.predicted_fee_sat_vb, 1, 10000) ||
          !validateNumber(p6.predicted_fee_sat_vb, 1, 10000)) {
        addLog('Invalid prediction values received', 'error');
        throw new Error('Invalid prediction values');
      }
      
      setPrediction(data);
      
      addLog(
        `Ensemble: 1blk=${p1.predicted_fee_sat_vb}, XGB=${p1.individual_predictions.xgb.toFixed(2)}, LGB=${p1.individual_predictions.lgb.toFixed(2)}`,
        'success'
      );
      addLog(`Confidence: ${(p1.confidence_score * 100).toFixed(1)}%`, 'info');
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      setError(msg);
      addLog(`Prediction Error: ${msg}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [addLog]);

  const fetchCurrentFees = useCallback(async () => {
    try {
      addLog('Fetching mempool data...', 'info');
      
      // Security: Include API key in headers
      const headers: Record<string, string> = {};
      if (API_KEY) {
        headers['X-API-Key'] = API_KEY;
      }
      
      const res = await fetch(`${API_BASE}/fees/current`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
      const data: CurrentFeesResponse = await res.json();
      setCurrentFees(data);
      
      addLog(
        `Mempool: ${data.mempool.tx_count.toLocaleString()} txs, ${data.mempool.vsize_mb} MB`,
        'success'
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      addLog(`API Error: ${msg}`, 'error');
    }
  }, [addLog]);

  const fetchHealth = useCallback(async () => {
    try {
      // Security: Include API key in headers
      const headers: Record<string, string> = {};
      if (API_KEY) {
        headers['X-API-Key'] = API_KEY;
      }
      
      const res = await fetch(`${API_BASE}/health`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
      const data: HealthResponse = await res.json();
      setHealth(data);
    } catch (e) {
      addLog('Health check failed', 'error');
    }
  }, [addLog]);

  // Initial load
  useEffect(() => {
    addLog('System initialized', 'success');
    addLog('Connecting to API...', 'info');
    
    fetchHealth();
    fetchCurrentFees();
    fetchPrediction();
    
    // Auto refresh intervals
    const feesInterval = setInterval(fetchCurrentFees, 30000);
    const predInterval = setInterval(fetchPrediction, 60000);
    const healthInterval = setInterval(fetchHealth, 60000);
    
    return () => {
      clearInterval(feesInterval);
      clearInterval(predInterval);
      clearInterval(healthInterval);
    };
  }, [fetchCurrentFees, fetchPrediction, fetchHealth, addLog]);

  return {
    prediction,
    currentFees,
    health,
    logs,
    loading,
    error,
    fetchPrediction,
    fetchCurrentFees,
    addLog,
  };
}
