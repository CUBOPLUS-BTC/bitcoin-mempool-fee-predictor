import { useState, useEffect, useCallback } from 'react';
import type { PredictResponse, CurrentFeesResponse, HealthResponse, LogEntry, LogType, MempoolSpaceResponse } from '../types/api';

// Security: Dynamic API base URL
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Security: API key from environment (NEVER hardcode)
const API_KEY = import.meta.env.VITE_API_KEY || localStorage.getItem('api_key') || '';

// Security: Validate numeric inputs
function validateNumber(value: number, min: number, max: number): number | null {
  const num = parseFloat(String(value));
  return !isNaN(num) && num >= min && num <= max ? num : null;
}



export interface ChartDataPoint {
  timestamp: string;
  predicted_1block: number;
  predicted_3blocks: number;
  predicted_6blocks: number;
  mempool_fastest: number;
  mempool_halfhour: number;
  mempool_hour: number;
}

export function useApi() {
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [currentFees, setCurrentFees] = useState<CurrentFeesResponse | null>(null);
  const [mempoolSpaceData, setMempoolSpaceData] = useState<MempoolSpaceResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);

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
      
      // Log feature weights if available
      if (p1.feature_weights) {
        const topFeature = Object.entries(p1.feature_weights)[0];
        if (topFeature) {
          addLog(`Top feature: ${topFeature[0]} (${(topFeature[1] * 100).toFixed(1)}%)`, 'info');
        }
      }
      
      // Log decision reasoning if available
      if (p1.decision_reasoning) {
        addLog(`Reasoning: ${p1.decision_reasoning.substring(0, 60)}...`, 'info');
      }
      
      setPrediction(data);
      
      // Add to chart data for shadow deployment comparison
      const mempoolData = mempoolSpaceData || await fetchMempoolSpaceData();
      if (mempoolData) {
        const newDataPoint: ChartDataPoint = {
          timestamp: new Date().toISOString(),
          predicted_1block: p1.predicted_fee_sat_vb,
          predicted_3blocks: p3.predicted_fee_sat_vb,
          predicted_6blocks: p6.predicted_fee_sat_vb,
          mempool_fastest: mempoolData.fastestFee,
          mempool_halfhour: mempoolData.halfHourFee,
          mempool_hour: mempoolData.hourFee,
        };
        
        setChartData(prev => {
          const updated = [...prev, newDataPoint].slice(-50); // Keep last 50 points
          return updated;
        });
      }
      
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

  const fetchMempoolSpaceData = useCallback(async () => {
    try {
      addLog('Fetching mempool.space data (shadow source)...', 'info');
      
      // Fetch from mempool.space API (no API key needed)
      const res = await fetch('https://mempool.space/api/v1/fees/recommended');
      if (!res.ok) throw new Error(`Mempool.space HTTP ${res.status}`);
      
      const data: MempoolSpaceResponse = await res.json();
      data.timestamp = new Date().toISOString();
      
      setMempoolSpaceData(data);
      addLog(
        `Mempool.space: fastest=${data.fastestFee}, halfHour=${data.halfHourFee}`,
        'success'
      );
      return data;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      addLog(`Mempool.space Error: ${msg}`, 'warning');
      return null;
    }
  }, [addLog]);

  const fetchCurrentFees = useCallback(async () => {
    try {
      addLog('Fetching local mempool data...', 'info');
      
      // Security: Include API key in headers
      const headers: Record<string, string> = {};
      if (API_KEY) {
        headers['X-API-Key'] = API_KEY;
      }
      
      // Parallel fetch from both APIs
      const [localRes, _mempoolSpaceData] = await Promise.all([
        fetch(`${API_BASE}/fees/current`, { headers }),
        fetchMempoolSpaceData()
      ]);
      
      if (!localRes.ok) throw new Error(`HTTP ${localRes.status}`);
      
      const data: CurrentFeesResponse = await localRes.json();
      setCurrentFees(data);
      
      addLog(
        `Local API: ${data.mempool.tx_count.toLocaleString()} txs, ${data.mempool.vsize_mb} MB`,
        'success'
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      addLog(`API Error: ${msg}`, 'error');
    }
  }, [addLog, fetchMempoolSpaceData]);

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

  const loadHistoricalData = useCallback(async () => {
    try {
      addLog('Loading historical chart data...', 'info');
      const response = await fetch('/historical_data.json');
      if (response.ok) {
        const historical = await response.json();
        if (historical.data && historical.data.length > 0) {
          setChartData(historical.data);
          addLog(`Loaded ${historical.data.length} historical data points`, 'success');
        }
      }
    } catch (e) {
      addLog('No historical data available', 'warning');
    }
  }, [addLog]);

  useEffect(() => {
    loadHistoricalData(); // Load historical data first
    fetchCurrentFees();
    fetchPrediction();
    fetchHealth();

    const feesInterval = setInterval(fetchCurrentFees, 60000); // 1 min
    const predInterval = setInterval(fetchPrediction, 60000); // 1 min
    const healthInterval = setInterval(fetchHealth, 30000); // 30 sec

    return () => {
      clearInterval(feesInterval);
      clearInterval(predInterval);
      clearInterval(healthInterval);
    };
  }, [fetchCurrentFees, fetchPrediction, fetchHealth, loadHistoricalData, addLog]);

  return {
    prediction,
    currentFees,
    mempoolSpaceData,
    health,
    logs,
    loading,
    error,
    chartData,
    fetchPrediction,
    fetchCurrentFees,
    fetchMempoolSpaceData,
    addLog,
  };
}
