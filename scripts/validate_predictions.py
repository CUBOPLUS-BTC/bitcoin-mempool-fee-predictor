import pandas as pd
from datetime import datetime, timezone
import argparse
from pathlib import Path
from loguru import logger
import sys

# Append parent dir
sys.path.append(str(Path(__file__).parent.parent))

from src.ingestion import MempoolDataIngestion

LOG_FILE = "predictions/ensemble_predictions.csv"

def validate_pending_predictions(log_df: pd.DataFrame, ingestion: MempoolDataIngestion) -> pd.DataFrame:
    """Validate pending predictions against mined blocks"""
    if log_df.empty:
        return log_df

    pending = log_df[log_df['status'] == 'PENDING'].copy()
    if pending.empty:
        logger.info("No pending predictions to validate")
        return log_df

    logger.info(f"Validating {len(pending)} pending predictions...")

    # Fetch current block data
    blocks = ingestion.fetch_recent_blocks(count=15)
    if not blocks:
        logger.warning("Could not fetch blocks for validation")
        return log_df

    validated_count = 0
    
    # Cast column to object to avoid TypeError when assigning booleans to a float64 dtype column
    log_df['would_confirm'] = log_df['would_confirm'].astype(object)

    for idx, row in pending.iterrows():
        # Handle string timestamps parsing dynamically
        pred_time = pd.to_datetime(row['timestamp_pred'], format='mixed')
        horizon = int(row['horizon_blocks'])

        # Handle both tz-aware and tz-naive timestamps from CSV
        if pred_time.tzinfo is None:
            pred_time = pred_time.tz_localize('UTC')
        else:
            pred_time = pred_time.tz_convert('UTC')
        
        time_since = (datetime.now(timezone.utc) - pred_time).total_seconds()
        estimated_blocks_mined = time_since / 600  # ~10 min per block

        # Only validate if enough blocks have passed
        if estimated_blocks_mined >= horizon + 1:
            relevant_fees = []
            for block in blocks:
                extras = block.get('extras', {})
                median_fee = extras.get('medianFee', 0)
                min_fee = extras.get('feeRange', [0])[0] if extras.get('feeRange') else 0
                if median_fee > 0:
                    relevant_fees.append(min_fee if min_fee > 0 else median_fee)

            if relevant_fees:
                actual_fee = min(relevant_fees[:horizon]) if len(relevant_fees) >= horizon else min(relevant_fees)

                predicted = row['predicted_fee_sat_vb']
                would_confirm = predicted >= actual_fee
                overpay = max(0, predicted - actual_fee)

                log_df.loc[idx, 'actual_fee'] = actual_fee
                log_df.loc[idx, 'would_confirm'] = would_confirm
                log_df.loc[idx, 'overpay_sat_vb'] = overpay
                log_df.loc[idx, 'status'] = 'VALIDATED'

                validated_count += 1

    if validated_count > 0:
        logger.success(f"Validated {validated_count} predictions")

    return log_df

def run_validation():
    logger.info("=" * 80)
    logger.info(" ENSEMBLE VALIDATION RUNNER")
    logger.info("=" * 80)
    
    if not Path(LOG_FILE).exists():
        logger.error(f"Prediction log {LOG_FILE} not found.")
        return

    log_df = pd.read_csv(LOG_FILE)
    ingestion = MempoolDataIngestion()
    
    updated_df = validate_pending_predictions(log_df, ingestion)
    
    # Analyze validations
    validated = len(updated_df[updated_df['status'] == 'VALIDATED'])
    if validated > 0:
        val_df = updated_df[updated_df['status'] == 'VALIDATED']
        inclusion_rate = val_df['would_confirm'].mean()
        avg_overpay = val_df['overpay_sat_vb'].mean()
        logger.info(f"\nBlock Inclusion Accuracy: {inclusion_rate:.2%}")
        logger.info(f"Average Overpay: {avg_overpay:.2f} sat/vB")

        for horizon_label in val_df['horizon_label'].unique():
            h_data = val_df[val_df['horizon_label'] == horizon_label]
            h_inclusion = h_data['would_confirm'].mean()
            h_overpay = h_data['overpay_sat_vb'].mean()
            logger.info(f"  {horizon_label:10s}: {len(h_data):3d} validated | Inclusion: {h_inclusion:.2%} | Overpay: {h_overpay:.1f}")

    updated_df.to_csv(LOG_FILE, index=False)
    logger.info(f"Saved validations to {LOG_FILE}")

if __name__ == "__main__":
    run_validation()
