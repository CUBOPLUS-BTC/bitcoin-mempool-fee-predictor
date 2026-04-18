#!/usr/bin/env python3
"""
Load historical prediction data from CSV for initial chart state.
This gives the frontend historical context even with empty snapshot directory.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_ensemble_predictions_to_json(
    csv_path: str = "predictions/ensemble_predictions.csv",
    output_path: str = "frontend-react/public/historical_data.json",
    max_points: int = 50
) -> dict:
    """
    Load historical ensemble predictions from CSV and convert to JSON format
    compatible with frontend ChartDataPoint interface.
    
    Returns data in format:
    {
        "timestamp": string,
        "predicted_1block": number,
        "predicted_3blocks": number,
        "predicted_6blocks": number,
        "mempool_fastest": number,
        "mempool_halfhour": number,
        "mempool_hour": number
    }
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        logger.warning(f"CSV file not found: {csv_path}")
        return {"data": [], "count": 0}
    
    logger.info(f"Loading historical data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Pivot to get one row per timestamp with all horizons
    pivoted = df.pivot_table(
        index='timestamp_pred',
        columns='horizon_label',
        values=['predicted_fee_sat_vb', 'current_fastest_fee', 'current_halfhour_fee', 'current_hour_fee'],
        aggfunc='first'
    ).reset_index()
    
    # Flatten column names
    pivoted.columns = [' '.join(col).strip() if col[1] else col[0] for col in pivoted.columns.values]
    
    # Rename columns for clarity
    column_mapping = {
        'timestamp_pred': 'timestamp',
        ('predicted_fee_sat_vb', '1_block') if ('predicted_fee_sat_vb', '1_block') in pivoted.columns else 'predicted_fee_sat_vb 1_block': 'predicted_1block',
        ('predicted_fee_sat_vb', '3_blocks') if ('predicted_fee_sat_vb', '3_blocks') in pivoted.columns else 'predicted_fee_sat_vb 3_blocks': 'predicted_3blocks',
        ('predicted_fee_sat_vb', '6_blocks') if ('predicted_fee_sat_vb', '6_blocks') in pivoted.columns else 'predicted_fee_sat_vb 6_blocks': 'predicted_6blocks',
        ('current_fastest_fee', '1_block') if ('current_fastest_fee', '1_block') in pivoted.columns else 'current_fastest_fee 1_block': 'mempool_fastest',
        ('current_halfhour_fee', '1_block') if ('current_halfhour_fee', '1_block') in pivoted.columns else 'current_halfhour_fee 1_block': 'mempool_halfhour',
        ('current_hour_fee', '1_block') if ('current_hour_fee', '1_block') in pivoted.columns else 'current_hour_fee 1_block': 'mempool_hour',
    }
    
    # Handle alternative column name formats
    result_data = []
    
    for _, row in df.iterrows():
        try:
            entry = {
                "timestamp": row['timestamp_pred'],
                f"predicted_{row['horizon_label'].replace('_', '')}": float(row['predicted_fee_sat_vb']),
                "mempool_fastest": float(row['current_fastest_fee']),
                "mempool_halfhour": float(row['current_halfhour_fee']),
                "mempool_hour": float(row['current_hour_fee']),
            }
            result_data.append(entry)
        except Exception as e:
            logger.warning(f"Error processing row: {e}")
            continue
    
    # Group by timestamp
    grouped = {}
    for entry in result_data:
        ts = entry['timestamp']
        if ts not in grouped:
            grouped[ts] = {
                'timestamp': ts,
                'predicted_1block': entry.get('predicted_1block', entry.get('predicted_1_block', 0)),
                'predicted_3blocks': entry.get('predicted_3blocks', entry.get('predicted_3_blocks', 0)),
                'predicted_6blocks': entry.get('predicted_6blocks', entry.get('predicted_6_blocks', 0)),
                'mempool_fastest': entry['mempool_fastest'],
                'mempool_halfhour': entry['mempool_halfhour'],
                'mempool_hour': entry['mempool_hour'],
            }
        else:
            # Update with non-zero values
            for key in ['predicted_1block', 'predicted_3blocks', 'predicted_6blocks']:
                if entry.get(key) and entry.get(key) > 0:
                    grouped[ts][key] = entry[key]
    
    # Convert to list and sort by timestamp
    chart_data = sorted(grouped.values(), key=lambda x: x['timestamp'])
    
    # Take last max_points
    chart_data = chart_data[-max_points:]
    
    # Ensure all numeric values are proper types
    for entry in chart_data:
        for key in ['predicted_1block', 'predicted_3blocks', 'predicted_6blocks', 
                    'mempool_fastest', 'mempool_halfhour', 'mempool_hour']:
            entry[key] = float(entry.get(key, 0)) if entry.get(key) else 0.0
    
    output = {
        "data": chart_data,
        "count": len(chart_data),
        "loaded_at": datetime.now().isoformat(),
        "source": str(csv_path)
    }
    
    # Save to JSON
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"✓ Loaded {len(chart_data)} historical data points to {output_path}")
    
    # Print sample
    if chart_data:
        logger.info(f"Sample entry: {chart_data[0]}")
    
    return output


def verify_models_loaded():
    """Verify that the best models are being used"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from src.inference import FeeModelInference
    
    logger.info("\nVerifying model configuration...")
    
    inference = FeeModelInference()
    inference.load_all_models()
    
    info = inference.get_loaded_models_info()
    logger.info(f"Models loaded: {info}")
    
    # Check model timestamps
    for model_type in ['xgb_models', 'lgb_models']:
        for horizon in info.get(model_type, []):
            ts_key = f"{model_type.replace('_models', '')}_{horizon}"
            ts = info.get('load_timestamps', {}).get(ts_key, 'unknown')
            logger.info(f"  {model_type} horizon {horizon}: loaded at {ts}")
    
    return info


def print_model_metrics():
    """Print metrics from training summaries"""
    import json
    
    logger.info("\nModel Training Metrics:")
    logger.info("=" * 50)
    
    models_dir = Path("models")
    summary_files = list(models_dir.glob("training_summary_*.json"))
    
    if not summary_files:
        logger.warning("No training summary files found")
        return
    
    # Get most recent
    latest = sorted(summary_files)[-1]
    
    with open(latest) as f:
        data = json.load(f)
    
    logger.info(f"Latest training: {data.get('timestamp', 'unknown')}")
    
    for horizon, metrics in data.get('horizons', {}).items():
        logger.info(f"\n{horizon}:")
        logger.info(f"  MAE: {metrics.get('mae', 'N/A'):.2f} sat/vB")
        logger.info(f"  RMSE: {metrics.get('rmse', 'N/A'):.2f} sat/vB")
        logger.info(f"  R²: {metrics.get('r2', 'N/A'):.4f}")
        logger.info(f"  Block Inclusion Accuracy: {metrics.get('block_inclusion_accuracy', 'N/A'):.1%}")


if __name__ == "__main__":
    # Load historical data
    result = load_ensemble_predictions_to_json()
    
    # Verify models
    verify_models_loaded()
    
    # Print metrics
    print_model_metrics()
    
    logger.info("\n✓ Historical data loader complete")
    logger.info(f"Frontend can now load: /historical_data.json")
