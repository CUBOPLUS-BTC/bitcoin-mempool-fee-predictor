"""
Live Fee Prediction Script
Runs every 10 minutes, fetching mempool state and predicting fees.
Logs predictions for validation against confirmed blocks.

Usage:
    python scripts/live_predict.py
    python scripts/live_predict.py --once   # Single prediction
"""

import sys
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion import MempoolDataIngestion
from src.inference import FeeModelInference

# Configuration
LOG_FILE = 'predictions/ensemble_predictions.csv'
HORIZONS = {1: '1block', 3: '3blocks', 6: '6blocks'}


def load_or_create_bitacora():
    """Load existing bitacora or create new one"""
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'], format='mixed')
        print(f" Loaded {len(df)} existing predictions")
        return df
    else:
        df = pd.DataFrame(columns=[
            'timestamp_pred',
            'horizon_blocks',
            'horizon_label',
            'mempool_tx_count',
            'mempool_vsize_mb',
            'current_fastest_fee',
            'current_halfhour_fee',
            'current_hour_fee',
            'predicted_fee_sat_vb',
            'predicted_fee_exact',
            'confidence_score',
            'models_used',
            'actual_fee',
            'would_confirm',
            'overpay_sat_vb',
            'status'
        ])
        print(" Created new fee prediction bitacora")
        return df

def run_live_prediction(single_run: bool = False):
    """Main prediction function"""
    print("=" * 80)
    print(" LIVE FEE PREDICTION — MEMPOOL MONITOR")
    print(f" Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # Ensure predictions dir exists
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    # Load/create bitacora
    log_df = load_or_create_bitacora()

    # Initialize services
    ingestion = MempoolDataIngestion()
    inference = FeeModelInference()

    # Check if models exist at all
    loaded = inference.load_all_models()
    info = inference.get_loaded_models_info()
    if info['total_models'] == 0:
        print("  No trained models found. Run auto_retrain workflow first.")
        print("   Exiting gracefully.")
        return

    # Fetch live mempool data
    print("\n Fetching mempool state...")
    snapshot = ingestion.fetch_full_snapshot()
    if snapshot is None:
        print(" Error: Could not fetch mempool data")
        return

    # Load historical snapshots for feature engineering
    snapshots_df = ingestion.load_snapshots()

    if snapshots_df is None or len(snapshots_df) < 5:
        print("  Not enough historical data — collecting quick snapshots...")
        import time
        rows = []
        for i in range(5):
            s = ingestion.fetch_full_snapshot()
            if s:
                rows.append(s)
            if i < 4:
                time.sleep(2)
        snapshots_df = pd.DataFrame(rows)
        print(f"   Collected {len(snapshots_df)} snapshots")
    else:
        # Append current snapshot
        snapshots_df = pd.concat([snapshots_df, pd.DataFrame([snapshot])], ignore_index=True)

    print(f" Mempool: {snapshot.get('mempool_tx_count', 0):,} txs, "
          f"{snapshot.get('mempool_vsize', 0) / 1e6:.1f} MvB")
    print(f"   Current fees: fastest={snapshot.get('fee_fastest', '?')}, "
          f"halfhour={snapshot.get('fee_half_hour', '?')}, "
          f"hour={snapshot.get('fee_hour', '?')} sat/vB")

    # Make predictions
    print("\n Making fee predictions...")
    try:
        response = inference.predict_from_snapshot(snapshots_df)
    except Exception as e:
        print(f" Prediction error: {e}")
        import traceback
        traceback.print_exc()
        return

    timestamp_pred = datetime.now(timezone.utc)
    new_predictions = []

    for label, pred in response.get('fee_predictions', {}).items():
        horizon = pred['horizon_blocks']
        prediction = {
            'timestamp_pred': timestamp_pred.isoformat(),
            'horizon_blocks': horizon,
            'horizon_label': label,
            'mempool_tx_count': snapshot.get('mempool_tx_count', 0),
            'mempool_vsize_mb': round(snapshot.get('mempool_vsize', 0) / 1e6, 1),
            'current_fastest_fee': snapshot.get('fee_fastest', 0),
            'current_halfhour_fee': snapshot.get('fee_half_hour', 0),
            'current_hour_fee': snapshot.get('fee_hour', 0),
            'predicted_fee_sat_vb': pred['predicted_fee_sat_vb'],
            'predicted_fee_exact': pred['predicted_fee_exact'],
            'confidence_score': pred['confidence_score'],
            'models_used': ','.join(pred.get('models_used', [])),
            'actual_fee': np.nan,
            'would_confirm': np.nan,
            'overpay_sat_vb': np.nan,
            'status': 'PENDING'
        }
        new_predictions.append(prediction)

        ci = pred['confidence_interval']
        print(f"   {label:10s}: {pred['predicted_fee_sat_vb']:3d} sat/vB "
              f"[{ci[0]}-{ci[1]}] ({pred['priority']}) "
              f"conf={pred['confidence_score']:.2f}")

    # Recommendation
    print(f"\n Recommendation: {response.get('recommendation', 'N/A')}")

    # Append new predictions
    if new_predictions:
        new_df = pd.DataFrame(new_predictions)
        log_df = pd.concat([log_df, new_df], ignore_index=True)
        print(f"\n Added {len(new_predictions)} new predictions")

    # Save bitacora
    log_df.to_csv(LOG_FILE, index=False)
    print(f" Saved to: {LOG_FILE}")

    # Show statistics
    print("\n" + "=" * 80)
    print(" STATISTICS")
    print("=" * 80)

    total = len(log_df)
    pending = len(log_df[log_df['status'] == 'PENDING'])

    print(f"Total predictions: {total}")
    print(f"  - Pending: {pending}")


    # Save current snapshot for collector
    ingestion.save_snapshot(snapshot)

    print("\n Prediction cycle completed!")
    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    args = parser.parse_args()

    if args.once:
        run_live_prediction(single_run=True)
    else:
        run_live_prediction(single_run=True)
