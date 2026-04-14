"""
Backtesting Module for Mempool Fee Prediction
Simulates fee estimation and calculates block inclusion metrics.
Replaces the previous trade-simulation backtester.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import json
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class FeeBacktester:
    """
    Backtesting engine for mempool fee prediction models.
    Simulates: would the predicted fee have been sufficient for block inclusion?
    Calculates savings vs naive approaches (always paying fastest fee).
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.results_dir = Path("backtest_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_path: str) -> dict:
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def run_backtest(
        self,
        predictions_df: pd.DataFrame,
        actuals_df: pd.DataFrame = None,
        horizon: int = 1
    ) -> Dict:
        """
        Run backtest on fee predictions vs actual required fees.

        Args:
            predictions_df: DataFrame with columns:
                - timestamp: prediction timestamp
                - predicted_fee: predicted fee in sats/vB
                - actual_fee: actual required fee (ground truth)
                - fee_fastest: what mempool.space recommended at that time
            actuals_df: Optional separate DataFrame with actual fees
            horizon: Block horizon being tested

        Returns:
            Dictionary with backtest results and metrics
        """
        logger.info(f"Starting fee backtest for {horizon}-block horizon")

        df = predictions_df.copy()

        if actuals_df is not None:
            # Merge actuals
            df = df.merge(actuals_df, on='timestamp', how='inner', suffixes=('', '_actual'))

        if 'predicted_fee' not in df.columns or 'actual_fee' not in df.columns:
            raise ValueError("DataFrame must have 'predicted_fee' and 'actual_fee' columns")

        y_pred = df['predicted_fee'].values
        y_true = df['actual_fee'].values
        y_naive = df['fee_fastest'].values if 'fee_fastest' in df.columns else y_true * 1.5

        # === Core Metrics ===
        metrics = self._calculate_inclusion_metrics(y_pred, y_true, y_naive, horizon)

        # === Per-sample results ===
        df['would_confirm'] = y_pred >= y_true
        df['overpay_sat_vb'] = np.maximum(y_pred - y_true, 0)
        df['underpay_sat_vb'] = np.maximum(y_true - y_pred, 0)
        df['error_sat_vb'] = y_pred - y_true
        df['error_pct'] = np.where(y_true > 0, (y_pred - y_true) / y_true * 100, 0)

        # Savings vs naive
        if 'fee_fastest' in df.columns:
            df['savings_vs_naive'] = df['fee_fastest'] - df['predicted_fee']
            df['savings_pct'] = np.where(
                df['fee_fastest'] > 0,
                df['savings_vs_naive'] / df['fee_fastest'] * 100,
                0
            )

        # === Time-based analysis ===
        time_analysis = {}
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['timestamp'].dt.hour

            # Inclusion accuracy by hour
            hourly = df.groupby('hour').agg({
                'would_confirm': 'mean',
                'overpay_sat_vb': 'mean',
                'error_sat_vb': 'mean',
            }).round(3)

            time_analysis['hourly_inclusion_accuracy'] = hourly['would_confirm'].to_dict()
            time_analysis['worst_hour'] = int(hourly['would_confirm'].idxmin())
            time_analysis['best_hour'] = int(hourly['would_confirm'].idxmax())

        # === Congestion regime analysis ===
        regime_analysis = {}
        if 'actual_fee' in df.columns:
            df['fee_regime'] = pd.cut(
                df['actual_fee'],
                bins=[0, 5, 15, 50, 100, float('inf')],
                labels=['very_low', 'low', 'medium', 'high', 'extreme']
            )
            regime_stats = df.groupby('fee_regime', observed=True).agg({
                'would_confirm': ['mean', 'count'],
                'overpay_sat_vb': 'mean',
            })
            for regime in regime_stats.index:
                regime_analysis[str(regime)] = {
                    'inclusion_accuracy': float(regime_stats.loc[regime, ('would_confirm', 'mean')]),
                    'sample_count': int(regime_stats.loc[regime, ('would_confirm', 'count')]),
                    'avg_overpay': float(regime_stats.loc[regime, ('overpay_sat_vb', 'mean')]),
                }

        results = {
            'horizon_blocks': horizon,
            'metrics': metrics,
            'time_analysis': time_analysis,
            'regime_analysis': regime_analysis,
            'n_samples': len(df),
            'backtest_timestamp': datetime.now().isoformat(),
        }

        logger.info(f"Backtest complete: Inclusion={metrics['block_inclusion_accuracy']:.2%}, "
                     f"MAE={metrics['mae']:.2f}, Savings={metrics.get('avg_savings_pct', 0):.1f}%")

        return results

    def _calculate_inclusion_metrics(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
        y_naive: np.ndarray,
        horizon: int
    ) -> Dict[str, float]:
        """Calculate comprehensive fee prediction metrics"""

        safe_y = np.where(y_true > 0, y_true, 1)
        overpay = np.maximum(y_pred - y_true, 0)
        underpay = np.maximum(y_true - y_pred, 0)
        errors = y_pred - y_true
        abs_errors = np.abs(errors)
        relative_errors = abs_errors / safe_y

        metrics = {
            # Core accuracy
            'block_inclusion_accuracy': float(np.mean(y_pred >= y_true)),
            'mae': float(np.mean(abs_errors)),
            'rmse': float(np.sqrt(np.mean(errors ** 2))),
            'mape': float(np.mean(relative_errors) * 100),
            'median_abs_error': float(np.median(abs_errors)),

            # Directional
            'avg_overpay_sat_vb': float(np.mean(overpay)),
            'avg_underpay_sat_vb': float(np.mean(underpay)),
            'max_underpay_sat_vb': float(np.max(underpay)),
            'pct_overpaying': float(np.mean(y_pred > y_true)),
            'pct_underpaying': float(np.mean(y_pred < y_true)),
            'pct_exact': float(np.mean(y_pred == y_true)),

            # Tolerance bands
            'within_1_sat': float(np.mean(abs_errors <= 1)),
            'within_2_sat': float(np.mean(abs_errors <= 2)),
            'within_5_sat': float(np.mean(abs_errors <= 5)),
            'within_10pct': float(np.mean(relative_errors < 0.10)),
            'within_20pct': float(np.mean(relative_errors < 0.20)),
            'within_50pct': float(np.mean(relative_errors < 0.50)),

            # Stuck transactions (worst case for user)
            'stuck_rate': float(np.mean(y_pred < y_true)),
            'severely_stuck_rate': float(np.mean((y_true - y_pred) > 10)),  # >10 sat/vB short
        }

        # Savings vs naive (always paying fastest fee)
        naive_cost = np.sum(y_naive)
        model_cost = np.sum(y_pred)
        if naive_cost > 0:
            metrics['total_savings_vs_naive_pct'] = float((1 - model_cost / naive_cost) * 100)
            metrics['avg_savings_pct'] = float(np.mean(
                np.where(y_naive > 0, (y_naive - y_pred) / y_naive * 100, 0)
            ))
            # Only count savings when model still achieves inclusion
            included_mask = y_pred >= y_true
            if included_mask.any():
                metrics['savings_when_included_pct'] = float(np.mean(
                    np.where(y_naive[included_mask] > 0,
                             (y_naive[included_mask] - y_pred[included_mask]) / y_naive[included_mask] * 100,
                             0)
                ))

        return metrics

    def save_results(self, results: Dict, filename: Optional[str] = None) -> str:
        """Save backtest results"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            horizon = results.get('horizon_blocks', 0)
            filename = f"fee_backtest_{horizon}block_{timestamp}.json"

        filepath = self.results_dir / filename

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"✓ Backtest results saved to {filepath}")
        return str(filepath)

    def print_summary(self, results: Dict) -> None:
        """Print formatted backtest summary"""
        m = results['metrics']
        horizon = results.get('horizon_blocks', '?')

        print(f"\n{'=' * 80}")
        print(f" FEE PREDICTION BACKTEST — {horizon}-BLOCK HORIZON")
        print(f"{'=' * 80}")

        print(f"\n INCLUSION METRICS:")
        print(f"  Block Inclusion Accuracy: {m['block_inclusion_accuracy']:.2%}")
        print(f"  Stuck Rate: {m['stuck_rate']:.2%}")
        print(f"  Severely Stuck (>10 sat/vB short): {m['severely_stuck_rate']:.2%}")

        print(f"\n ERROR METRICS:")
        print(f"  MAE: {m['mae']:.2f} sats/vB")
        print(f"  RMSE: {m['rmse']:.2f} sats/vB")
        print(f"  MAPE: {m['mape']:.1f}%")
        print(f"  Median Abs Error: {m['median_abs_error']:.2f} sats/vB")

        print(f"\n COST ANALYSIS:")
        print(f"  Avg Overpay: {m['avg_overpay_sat_vb']:.2f} sats/vB")
        print(f"  Avg Underpay: {m['avg_underpay_sat_vb']:.2f} sats/vB")
        print(f"  Max Underpay: {m['max_underpay_sat_vb']:.2f} sats/vB")
        if 'avg_savings_pct' in m:
            print(f"  Savings vs Always-Fastest: {m['avg_savings_pct']:.1f}%")

        print(f"\n TOLERANCE BANDS:")
        print(f"  Within 1 sat/vB: {m['within_1_sat']:.2%}")
        print(f"  Within 5 sat/vB: {m['within_5_sat']:.2%}")
        print(f"  Within 20%: {m['within_20pct']:.2%}")

        # Regime analysis
        ra = results.get('regime_analysis', {})
        if ra:
            print(f"\n BY CONGESTION REGIME:")
            for regime, stats in ra.items():
                print(f"  {regime:10s}: Inclusion={stats['inclusion_accuracy']:.2%} "
                      f"({stats['sample_count']} samples, avg overpay={stats['avg_overpay']:.1f})")

        print(f"\n  Total samples: {results['n_samples']:,}")
        print(f"{'=' * 80}")


def main():
    """CLI entry point for backtesting"""
    import argparse

    parser = argparse.ArgumentParser(description="Backtest fee predictions")
    parser.add_argument('--predictions', type=str, required=True, help='Predictions CSV')
    parser.add_argument('--horizon', type=int, default=1, help='Block horizon')
    parser.add_argument('--config', type=str, default='config/config.yaml')

    args = parser.parse_args()

    logger.add("logs/backtest.log", rotation="1 day", retention="7 days")

    # Load predictions
    df = pd.read_csv(args.predictions)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Run backtest
    backtester = FeeBacktester(config_path=args.config)
    results = backtester.run_backtest(df, horizon=args.horizon)

    backtester.print_summary(results)
    backtester.save_results(results)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
