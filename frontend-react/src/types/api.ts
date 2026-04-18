export interface FeePrediction {
  horizon_blocks: number;
  predicted_fee_sat_vb: number;
  predicted_fee_exact: number;
  confidence_interval: [number, number];
  confidence_score: number;
  priority: 'high' | 'medium' | 'low';
  models_used: string[];
  individual_predictions: {
    xgb: number;
    lgb: number;
  };
  feature_weights?: Record<string, number>;
  decision_reasoning?: string;
  timestamp: string;
}

export interface PredictResponse {
  timestamp: string;
  mempool_snapshot: {
    tx_count: number;
    vsize_mb: number;
    total_fee_btc: number;
    blocks_last_hour: number;
    time_since_last_block_sec: number;
  };
  current_fees: {
    fastest: number;
    half_hour: number;
    hour: number;
    economy: number;
    minimum: number;
  };
  fee_predictions: {
    '1_block': FeePrediction;
    '3_blocks': FeePrediction;
    '6_blocks': FeePrediction;
  };
  recommendation: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface CurrentFeesResponse {
  timestamp: string;
  fees: {
    fastest: number;
    half_hour: number;
    hour: number;
    economy: number;
    minimum: number;
  };
  mempool: {
    tx_count: number;
    vsize_mb: number;
    total_fee_btc: number;
  };
  source: string;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  models_loaded: number;
  xgb_horizons: number[];
  lgb_horizons: number[];
}

export type LogType = 'info' | 'warning' | 'error' | 'success';

export interface LogEntry {
  time: string;
  msg: string;
  type: LogType;
}

// Mempool.space API response
export interface MempoolSpaceResponse {
  fastestFee: number;
  halfHourFee: number;
  hourFee: number;
  economyFee: number;
  minimumFee: number;
  timestamp: string;
}
