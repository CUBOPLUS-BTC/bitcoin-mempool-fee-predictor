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
        df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
        print(f"✅ Loaded {len(df)} existing predictions")
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
        print("✅ Created new fee prediction bitacora")
        return df


def validate_pending_predictions(df, ingestion):
    """
    Validate pending predictions by checking confirmed blocks.
    If enough blocks have been mined since the prediction,
    compare predicted fee vs what was actually required.
    """
    if df.empty:
        return df

    pending = df[df['status'] == 'PENDING'].copy()
    if pending.empty:
        print("ℹ️  No pending predictions to validate")
        return df

    print(f"\n🔍 Validating {len(pending)} pending predictions...")

    # Fetch current block data
    blocks = ingestion.fetch_recent_blocks(count=15)
    if not blocks:
        print("⚠️  Could not fetch blocks for validation")
        return df

    current_height = blocks[0].get('height', 0) if blocks else 0
    validated_count = 0
    
    # Cast column to object to avoid TypeError when assigning booleans to a float64 dtype column
    df['would_confirm'] = df['would_confirm'].astype(object)

    for idx, row in pending.iterrows():
        pred_time = pd.to_datetime(row['timestamp_pred'], format='mixed')
        horizon = int(row['horizon_blocks'])

        # Find the block height at prediction time (approximate)
        # Use the time since prediction to estimate blocks mined
        # Handle both tz-aware and tz-naive timestamps from CSV
        if pred_time.tzinfo is None:
            pred_time = pred_time.tz_localize('UTC')
        else:
            pred_time = pred_time.tz_convert('UTC')
        time_since = (datetime.now(timezone.utc) - pred_time).total_seconds()
        estimated_blocks_mined = time_since / 600  # ~10 min per block

        # Only validate if enough blocks have passed
        if estimated_blocks_mined >= horizon + 1:
            # Find the min fee of blocks that were mined in the horizon window
            # Use the median fee from recent blocks as ground truth
            relevant_fees = []
            for block in blocks:
                extras = block.get('extras', {})
                median_fee = extras.get('medianFee', 0)
                min_fee = extras.get('feeRange', [0])[0] if extras.get('feeRange') else 0
                if median_fee > 0:
                    relevant_fees.append(min_fee if min_fee > 0 else median_fee)

            if relevant_fees:
                # Use the minimum fee across the relevant blocks
                actual_fee = min(relevant_fees[:horizon]) if len(relevant_fees) >= horizon else min(relevant_fees)

                predicted = row['predicted_fee_sat_vb']
                would_confirm = predicted >= actual_fee
                overpay = max(0, predicted - actual_fee)

                df.loc[idx, 'actual_fee'] = actual_fee
                df.loc[idx, 'would_confirm'] = would_confirm
                df.loc[idx, 'overpay_sat_vb'] = overpay
                df.loc[idx, 'status'] = 'VALIDATED'

                validated_count += 1

    if validated_count > 0:
        print(f"✅ Validated {validated_count} predictions")

    return df


def run_live_prediction(single_run: bool = False):
    """Main prediction function"""
    print("=" * 80)
    print("⚡ LIVE FEE PREDICTION — MEMPOOL MONITOR")
    print(f"⏰ Timestamp: {datetime.now(timezone.utc).isoformat()}")
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
        print("⚠️  No trained models found. Run auto_retrain workflow first.")
        print("   Exiting gracefully.")
        return

    # Validate pending predictions
    log_df = validate_pending_predictions(log_df, ingestion)

    # Fetch live mempool data
    print("\n📥 Fetching mempool state...")
    snapshot = ingestion.fetch_full_snapshot()
    if snapshot is None:
        print("❌ Error: Could not fetch mempool data")
        return

    # Load historical snapshots for feature engineering
    snapshots_df = ingestion.load_snapshots()

    if snapshots_df is None or len(snapshots_df) < 5:
        print("⚠️  Not enough historical data — collecting quick snapshots...")
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

    print(f"✅ Mempool: {snapshot.get('mempool_tx_count', 0):,} txs, "
          f"{snapshot.get('mempool_vsize', 0) / 1e6:.1f} MvB")
    print(f"   Current fees: fastest={snapshot.get('fee_fastest', '?')}, "
          f"halfhour={snapshot.get('fee_half_hour', '?')}, "
          f"hour={snapshot.get('fee_hour', '?')} sat/vB")

    # Make predictions
    print("\n🤖 Making fee predictions...")
    try:
        response = inference.predict_from_snapshot(snapshots_df)
    except Exception as e:
        print(f"❌ Prediction error: {e}")
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
        print(f"  ✅ {label:10s}: {pred['predicted_fee_sat_vb']:3d} sat/vB "
              f"[{ci[0]}-{ci[1]}] ({pred['priority']}) "
              f"conf={pred['confidence_score']:.2f}")

    # Recommendation
    print(f"\n📋 Recommendation: {response.get('recommendation', 'N/A')}")

    # Append new predictions
    if new_predictions:
        new_df = pd.DataFrame(new_predictions)
        log_df = pd.concat([log_df, new_df], ignore_index=True)
        print(f"\n✅ Added {len(new_predictions)} new predictions")

    # Save bitacora
    log_df.to_csv(LOG_FILE, index=False)
    print(f"💾 Saved to: {LOG_FILE}")

    # Show statistics
    print("\n" + "=" * 80)
    print("📊 STATISTICS")
    print("=" * 80)

    total = len(log_df)
    pending = len(log_df[log_df['status'] == 'PENDING'])
    validated = len(log_df[log_df['status'] == 'VALIDATED'])

    print(f"Total predictions: {total}")
    print(f"  - Pending: {pending}")
    print(f"  - Validated: {validated}")

    if validated > 0:
        val_df = log_df[log_df['status'] == 'VALIDATED']
        inclusion_rate = val_df['would_confirm'].mean()
        avg_overpay = val_df['overpay_sat_vb'].mean()
        print(f"\nBlock Inclusion Accuracy: {inclusion_rate:.2%}")
        print(f"Average Overpay: {avg_overpay:.2f} sat/vB")

        for horizon_label in val_df['horizon_label'].unique():
            h_data = val_df[val_df['horizon_label'] == horizon_label]
            h_inclusion = h_data['would_confirm'].mean()
            h_overpay = h_data['overpay_sat_vb'].mean()
            print(f"  {horizon_label:10s}: {len(h_data):3d} validated | "
                  f"Inclusion: {h_inclusion:.2%} | Overpay: {h_overpay:.1f} sat/vB")

    # Save current snapshot for collector
    ingestion.save_snapshot(snapshot)

    print("\n✅ Prediction cycle completed!")
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
