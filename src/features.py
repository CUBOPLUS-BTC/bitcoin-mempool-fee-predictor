"""
Feature Engineering Module for Mempool Fee Prediction
Creates congestion-based features from mempool snapshots and Bitcoin Core RPC data.
Replaces the previous technical-indicator-based features for price prediction.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import yaml
from loguru import logger
from typing import List, Optional, Tuple


class FeatureEngineer:
    """
    Feature engineering for Bitcoin mempool fee prediction.
    Generates congestion metrics, fee landscape features, block timing analysis,
    and composite indicators from raw mempool snapshots.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize feature engineer

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.processed_dir = Path(self.config['data']['processed_dir'])
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def create_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create all mempool congestion features from raw snapshots.

        Args:
            df: DataFrame with raw mempool snapshot data

        Returns:
            DataFrame with added features
        """
        logger.info("Creating mempool features...")
        df = df.copy()

        # Ensure sorted by time
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)

        # 1. Mempool state features (raw + derived)
        df = self._add_mempool_state_features(df)

        # 2. Fee landscape features
        df = self._add_fee_landscape_features(df)

        # 3. Block timing and supply-side features
        df = self._add_block_features(df)

        # 4. Projected block features
        df = self._add_projected_block_features(df)

        # 5. Time-based cyclical features
        df = self._add_time_features(df)

        # 6. Rolling / lag features over snapshot windows
        df = self._add_rolling_features(df)

        # 7. Lag features of key variables
        df = self._add_lag_features(df)

        # 8. Composite / ratio features (defragment first to avoid pandas warning)
        df = df.copy()
        df = self._add_composite_features(df)

        # 9. Bitcoin Core RPC features (if available)
        df = self._add_rpc_features(df)

        # Remove NaN rows (from rolling windows)
        initial_rows = len(df)
        df = df.dropna()
        logger.info(f"Dropped {initial_rows - len(df)} rows with NaN values")

        logger.info(f"✓ Created {len(df.columns)} total columns ({len(self.get_feature_columns(df))} features)")

        return df

    # =========================================================================
    # Feature Groups
    # =========================================================================

    def _add_mempool_state_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add mempool state derived features"""

        # Normalize vsize to MvB for readability
        df['mempool_vsize_mb'] = df['mempool_vsize'] / 1e6

        # Average fee per transaction
        df['mempool_avg_fee_per_tx'] = np.where(
            df['mempool_tx_count'] > 0,
            df['mempool_total_fee'] / df['mempool_tx_count'],
            0
        )

        # Fee density: total fee / total vsize (satoshis per vByte across entire mempool)
        df['mempool_fee_density'] = np.where(
            df['mempool_vsize'] > 0,
            df['mempool_total_fee'] / df['mempool_vsize'],
            0
        )

        # Deltas: change vs previous snapshot
        df['mempool_tx_count_delta'] = df['mempool_tx_count'].diff()
        df['mempool_vsize_delta'] = df['mempool_vsize'].diff()
        df['mempool_total_fee_delta'] = df['mempool_total_fee'].diff()

        # Velocity (first derivative of vsize)
        df['mempool_vsize_velocity'] = df['mempool_vsize'].diff()

        # Acceleration (second derivative of vsize)
        df['mempool_vsize_acceleration'] = df['mempool_vsize_velocity'].diff()

        # Percent changes
        df['mempool_tx_count_pct_change'] = df['mempool_tx_count'].pct_change()
        df['mempool_vsize_pct_change'] = df['mempool_vsize'].pct_change()

        return df

    def _add_fee_landscape_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add fee distribution and spread features"""

        # Fee spread (range between fastest and economy)
        df['fee_spread'] = df['fee_fastest'] - df['fee_economy']

        # Fee spread ratio
        df['fee_spread_ratio'] = np.where(
            df['fee_economy'] > 0,
            df['fee_fastest'] / df['fee_economy'],
            1.0
        )

        # Fee tier differences
        df['fee_fast_vs_halfhour'] = df['fee_fastest'] - df['fee_half_hour']
        df['fee_halfhour_vs_hour'] = df['fee_half_hour'] - df['fee_hour']
        df['fee_hour_vs_economy'] = df['fee_hour'] - df['fee_economy']

        # Fee deltas vs previous snapshot
        for fee_col in ['fee_fastest', 'fee_half_hour', 'fee_hour', 'fee_economy']:
            df[f'{fee_col}_delta'] = df[fee_col].diff()
            df[f'{fee_col}_pct_change'] = df[fee_col].pct_change()

        # Fee premium: how much more is fastest vs last confirmed block median
        df['fee_premium_ratio'] = np.where(
            df['last_block_median_fee'] > 0,
            df['fee_fastest'] / df['last_block_median_fee'],
            1.0
        )

        return df

    def _add_block_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add block timing and supply-side features"""

        # Block time deviation from 10min (600s) expected
        df['block_time_deviation_3'] = df['avg_block_time_last3'] - 600.0
        df['block_time_deviation_6'] = df['avg_block_time_last6'] - 600.0

        # Block time ratio (>1 means slower than expected)
        df['block_time_ratio'] = df['avg_block_time_last6'] / 600.0

        # Last block fullness (weight / max_weight where max = 4,000,000 WU)
        df['last_block_fullness'] = np.where(
            df['last_block_weight'] > 0,
            df['last_block_weight'] / 4_000_000.0,
            0.0
        )

        # Time since last block (important for urgency)
        # Already in snapshot as 'time_since_last_block'
        df['time_since_last_block_normalized'] = df['time_since_last_block'] / 600.0

        # Block fee trend: recent block fees vs average
        df['block_fee_trend'] = np.where(
            df['avg_block_median_fee_last6'] > 0,
            df['last_block_median_fee'] / df['avg_block_median_fee_last6'],
            1.0
        )

        # Block fee range
        df['block_fee_range'] = df['max_block_median_fee_last6'] - df['min_block_median_fee_last6']

        return df

    def _add_projected_block_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add features from mempool projected blocks"""

        # Fee gradient across projected blocks
        for i in range(min(7, self._count_projected_blocks(df))):
            col = f'projected_block_{i}_median_fee'
            if col in df.columns:
                if i > 0:
                    prev_col = f'projected_block_{i-1}_median_fee'
                    if prev_col in df.columns:
                        df[f'projected_fee_gradient_{i}'] = df[prev_col] - df[col]

        # Total projected mempool weight
        total_vsize_cols = [f'projected_block_{i}_total_vsize'
                           for i in range(8) if f'projected_block_{i}_total_vsize' in df.columns]
        if total_vsize_cols:
            df['projected_total_vsize'] = df[total_vsize_cols].sum(axis=1)

        # Number of projected blocks (how deep is the queue)
        n_tx_cols = [f'projected_block_{i}_n_tx'
                     for i in range(8) if f'projected_block_{i}_n_tx' in df.columns]
        if n_tx_cols:
            df['projected_total_tx'] = df[n_tx_cols].sum(axis=1)
            df['projected_n_nonempty_blocks'] = (df[n_tx_cols] > 0).sum(axis=1)

        return df

    def _count_projected_blocks(self, df: pd.DataFrame) -> int:
        """Count how many projected block columns exist"""
        count = 0
        for i in range(8):
            if f'projected_block_{i}_median_fee' in df.columns:
                count += 1
        return count

    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based cyclical features"""
        if 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'])

            # Hour of day (cyclical encoding)
            hour = ts.dt.hour
            df['hour_sin'] = np.sin(2 * np.pi * hour / 24)
            df['hour_cos'] = np.cos(2 * np.pi * hour / 24)

            # Day of week (cyclical encoding)
            dow = ts.dt.dayofweek
            df['day_sin'] = np.sin(2 * np.pi * dow / 7)
            df['day_cos'] = np.cos(2 * np.pi * dow / 7)

            # Weekend indicator
            df['is_weekend'] = (dow >= 5).astype(int)

            # Approximate Bitcoin network activity periods
            # US business hours (14:00-22:00 UTC) tend to have more activity
            df['is_us_hours'] = ((hour >= 14) & (hour <= 22)).astype(int)

        return df

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add rolling window statistics for key metrics"""
        windows = self.config['features']['mempool_size_windows']

        # Mempool vsize rolling stats
        for w in windows:
            df[f'mempool_vsize_ma_{w}'] = df['mempool_vsize'].rolling(window=w).mean()
            df[f'mempool_vsize_std_{w}'] = df['mempool_vsize'].rolling(window=w).std()
            df[f'mempool_vsize_vs_ma_{w}'] = np.where(
                df[f'mempool_vsize_ma_{w}'] > 0,
                df['mempool_vsize'] / df[f'mempool_vsize_ma_{w}'],
                1.0
            )

        # Fee rolling stats
        for fee_col in ['fee_fastest', 'fee_half_hour', 'fee_hour']:
            for w in windows:
                df[f'{fee_col}_ma_{w}'] = df[fee_col].rolling(window=w).mean()
                df[f'{fee_col}_std_{w}'] = df[fee_col].rolling(window=w).std()

            # Z-score of current fee vs its rolling mean/std
            w_main = windows[-1]  # Use largest window for z-score
            ma_col = f'{fee_col}_ma_{w_main}'
            std_col = f'{fee_col}_std_{w_main}'
            df[f'{fee_col}_zscore'] = np.where(
                df[std_col] > 0,
                (df[fee_col] - df[ma_col]) / df[std_col],
                0.0
            )

        # Tx count rolling
        for w in windows:
            df[f'mempool_tx_count_ma_{w}'] = df['mempool_tx_count'].rolling(window=w).mean()

        return df

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lagged features of key variables"""
        n_lags = self.config['features'].get('n_lags', 5)

        key_features = [
            'fee_fastest', 'fee_half_hour', 'fee_hour',
            'mempool_vsize', 'mempool_tx_count',
            'mempool_fee_density', 'fee_spread'
        ]

        for feature in key_features:
            if feature in df.columns:
                for lag in range(1, n_lags + 1):
                    df[f'{feature}_lag_{lag}'] = df[feature].shift(lag)

        return df

    def _add_composite_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add composite and ratio features"""

        # Congestion index: mempool_vsize / (blocks_per_hour * ~4MB block capacity)
        df['congestion_index'] = np.where(
            df['blocks_last_hour'] > 0,
            df['mempool_vsize'] / (df['blocks_last_hour'] * 4_000_000),
            df['mempool_vsize'] / 4_000_000  # assume 1 block/hour if unknown
        )

        # Estimated drain rate: how many vBytes are cleared per block
        # Approximate from recent block sizes
        df['mempool_drain_rate'] = np.where(
            df['blocks_last_hour'] > 0,
            df['last_block_weight'] / 4.0,  # weight / 4 ≈ vsize
            1_000_000  # default ~1MB
        )

        # Estimated blocks to clear mempool
        df['estimated_clear_blocks'] = np.where(
            df['mempool_drain_rate'] > 0,
            df['mempool_vsize'] / df['mempool_drain_rate'],
            0
        )

        # Estimated time to clear (in minutes)
        df['estimated_clear_minutes'] = df['estimated_clear_blocks'] * (df['avg_block_time_last6'] / 60.0)

        # Fee pressure: ratio of projected block 0 fee range to last confirmed
        if 'projected_block_0_median_fee' in df.columns:
            df['fee_pressure'] = np.where(
                df['last_block_median_fee'] > 0,
                df['projected_block_0_median_fee'] / df['last_block_median_fee'],
                1.0
            )

        # Network urgency composite
        # Higher when: mempool growing + block times slow + fees rising
        df['urgency_score'] = (
            df.get('mempool_vsize_pct_change', 0).clip(-1, 1) * 0.3 +
            df.get('block_time_ratio', 1.0).clip(0.5, 2.0) * 0.3 +
            df.get('fee_fastest_pct_change', 0).clip(-1, 1) * 0.4
        )

        return df

    def _add_rpc_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add features from Bitcoin Core RPC if available.
        These columns are populated by the collector daemon when RPC is enabled.
        """
        rpc_columns = [
            'rpc_mempool_size',       # getmempoolinfo: size
            'rpc_mempool_bytes',      # getmempoolinfo: bytes
            'rpc_mempool_usage',      # getmempoolinfo: usage
            'rpc_mempool_maxmempool', # getmempoolinfo: maxmempool
            'rpc_mempool_minfee',     # getmempoolinfo: mempoolminfee
            'rpc_est_fee_1',          # estimatesmartfee 1: feerate in BTC/kB
            'rpc_est_fee_3',          # estimatesmartfee 3
            'rpc_est_fee_6',          # estimatesmartfee 6
            'rpc_est_fee_12',         # estimatesmartfee 12
            'rpc_est_fee_25',         # estimatesmartfee 25
        ]

        # Only process if RPC columns exist
        rpc_present = [col for col in rpc_columns if col in df.columns]
        if rpc_present:
            logger.info(f"Adding {len(rpc_present)} Bitcoin Core RPC features")

            # Convert BTC/kB fee estimates to sat/vB (if present)
            for col in ['rpc_est_fee_1', 'rpc_est_fee_3', 'rpc_est_fee_6',
                        'rpc_est_fee_12', 'rpc_est_fee_25']:
                if col in df.columns:
                    # BTC/kB → sat/vB: multiply by 100,000 (1e5) then divide by 4 (witness discount)
                    # More precisely: BTC/kB * 1e8 / 1000 = sat/B, then ÷ ~1 for vB ≈ sat/vB
                    df[f'{col}_sat_vb'] = df[col] * 1e8 / 1000.0

            # RPC mempool fullness ratio
            if 'rpc_mempool_usage' in df.columns and 'rpc_mempool_maxmempool' in df.columns:
                df['rpc_mempool_fullness'] = np.where(
                    df['rpc_mempool_maxmempool'] > 0,
                    df['rpc_mempool_usage'] / df['rpc_mempool_maxmempool'],
                    0
                )

            # Agreement score: how close are mempool.space and RPC estimates
            if 'rpc_est_fee_1_sat_vb' in df.columns:
                df['fee_consensus_1block'] = np.where(
                    df['fee_fastest'] > 0,
                    df['rpc_est_fee_1_sat_vb'] / df['fee_fastest'],
                    1.0
                )

        return df

    # =========================================================================
    # Target Creation
    # =========================================================================

    def create_block_horizon_targets(
        self,
        df: pd.DataFrame,
        horizons: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Create target columns for block-horizon fee prediction.

        The target for each snapshot is the actual fee rate that was required
        to be included within the next N blocks. This is computed retrospectively
        by looking at confirmed block data.

        For training, we use the 'fee_fastest' (next block fee) recorded at
        the time when N blocks have actually been mined since the snapshot.
        This approximates the minimum fee needed.

        Args:
            df: DataFrame with features (must include timestamps and fee data)
            horizons: List of block horizons (e.g., [1, 3, 6])

        Returns:
            DataFrame with added target columns
        """
        if horizons is None:
            horizons = self.config['model']['horizons']

        logger.info(f"Creating targets for block horizons: {horizons}")

        df = df.copy()

        # Strategy: Use block height changes to determine when N blocks passed.
        # For each snapshot, find the snapshot where 'last_block_height' increased by N.
        if 'last_block_height' not in df.columns:
            logger.warning("No 'last_block_height' column — falling back to time-based targets")
            return self._create_time_based_targets(df, horizons)

        for horizon in horizons:
            target_col = f'target_{horizon}block_fee'
            df[target_col] = np.nan

            heights = df['last_block_height'].values
            fees_fastest = df['fee_fastest'].values

            for i in range(len(df)):
                current_height = heights[i]
                target_height = current_height + horizon

                # Find first snapshot where block height >= target_height
                future_mask = heights[i:] >= target_height
                if future_mask.any():
                    future_idx = i + np.argmax(future_mask)
                    # The fee_fastest at that future point represents what was needed
                    # But more accurately, we want the min fee of the block that achieved inclusion
                    # For now, use the last_block_min_fee at the future snapshot
                    if 'last_block_min_fee' in df.columns:
                        df.iloc[i, df.columns.get_loc(target_col)] = df.iloc[future_idx]['last_block_min_fee']
                    else:
                        # Fallback: use the median fee of the block at that point
                        if 'last_block_median_fee' in df.columns:
                            df.iloc[i, df.columns.get_loc(target_col)] = df.iloc[future_idx]['last_block_median_fee']
                        else:
                            df.iloc[i, df.columns.get_loc(target_col)] = fees_fastest[future_idx]

        # Drop rows without targets (tail of dataset where future blocks aren't known)
        df = df.dropna(subset=[f'target_{h}block_fee' for h in horizons])

        logger.info(f"✓ Created targets for {len(horizons)} block horizons. {len(df)} samples remain.")
        return df

    def _create_time_based_targets(
        self,
        df: pd.DataFrame,
        horizons: List[int]
    ) -> pd.DataFrame:
        """
        Fallback: Create time-based targets when block height data is unavailable.
        Approximates N blocks as N*10 minutes.
        """
        logger.warning("Using time-based target approximation (N blocks ≈ N*10 min)")

        for horizon in horizons:
            # Approximate: 1 block = ~10 min = ~5 snapshots at 2-min intervals
            shift_amount = horizon * 5
            df[f'target_{horizon}block_fee'] = df['fee_fastest'].shift(-shift_amount)

        df = df.dropna(subset=[f'target_{h}block_fee' for h in horizons])
        return df

    # =========================================================================
    # Feature Column Selection
    # =========================================================================

    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Get list of feature columns (excluding metadata, raw identifiers, and targets)

        Args:
            df: DataFrame with features

        Returns:
            List of feature column names
        """
        exclude_patterns = [
            'timestamp', 'timestamp_unix',                      # identifiers
            'target_',                                          # target variables
            'last_block_height', 'last_block_timestamp',        # raw block identifiers
            'last_block_reward',                                # not a fee feature
            'mempool_vsize',                                    # raw (use _mb version)
        ]

        # Also exclude columns that are just raw projected block data
        # (we keep their derived features like gradients)
        exclude_exact = set()

        feature_cols = []
        for col in df.columns:
            if col in exclude_exact:
                continue
            if any(pattern == col for pattern in exclude_exact):
                continue
            if any(pattern in col for pattern in exclude_patterns):
                continue
            # Exclude non-numeric columns
            if df[col].dtype == 'object':
                continue
            feature_cols.append(col)

        return feature_cols

    # =========================================================================
    # Data Persistence
    # =========================================================================

    def save_processed_data(
        self,
        df: pd.DataFrame,
        filename: Optional[str] = None
    ) -> str:
        """
        Save processed data to Parquet

        Args:
            df: DataFrame to save
            filename: Custom filename (optional)

        Returns:
            Path where data was saved
        """
        try:
            if filename is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"features_{timestamp}.parquet"

            filepath = self.processed_dir / filename

            if filepath.suffix == '.parquet':
                df.to_parquet(filepath, index=False, engine='pyarrow')
            else:
                df.to_csv(filepath, index=False)

            logger.info(f"✓ Processed data saved to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save processed data: {e}")
            raise

    def load_latest_processed_data(self) -> Optional[pd.DataFrame]:
        """
        Load the most recent processed data file

        Returns:
            DataFrame with processed data or None if not found
        """
        try:
            # Try parquet first, then CSV
            for ext in ['*.parquet', '*.csv']:
                files = sorted(
                    self.processed_dir.glob(ext),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                if files:
                    latest_file = files[0]
                    logger.info(f"Loading processed data from {latest_file}")

                    if latest_file.suffix == '.parquet':
                        df = pd.read_parquet(latest_file)
                    else:
                        df = pd.read_csv(latest_file)

                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])

                    logger.info(f"✓ Loaded {len(df)} rows from {latest_file.name}")
                    return df

            logger.warning("No processed data files found")
            return None

        except Exception as e:
            logger.error(f"Failed to load processed data: {e}")
            return None

    def process_and_save(self, df: pd.DataFrame) -> Optional[str]:
        """
        Convenience method: Create features, targets, and save

        Args:
            df: Raw mempool snapshot DataFrame

        Returns:
            Path to saved file
        """
        # Create features
        df = self.create_all_features(df)

        # Create block-horizon targets
        df = self.create_block_horizon_targets(df)

        # Save
        return self.save_processed_data(df)


def main():
    """CLI entry point for feature engineering"""
    import argparse
    from src.ingestion import MempoolDataIngestion

    parser = argparse.ArgumentParser(description="Create features from mempool snapshots")
    parser.add_argument('--input', type=str, default=None, help='Input Parquet/CSV file')
    parser.add_argument('--config', type=str, default='config/config.yaml', help='Config file path')

    args = parser.parse_args()

    # Setup logging
    logger.add("logs/features.log", rotation="1 day", retention="7 days")

    # Load data
    if args.input:
        logger.info(f"Loading data from {args.input}")
        if args.input.endswith('.parquet'):
            df = pd.read_parquet(args.input)
        else:
            df = pd.read_csv(args.input)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
    else:
        logger.info("Loading latest snapshot data")
        ingestion = MempoolDataIngestion(config_path=args.config)
        df = ingestion.load_snapshots()

    if df is None:
        logger.error("No data to process")
        return 1

    # Process features
    engineer = FeatureEngineer(config_path=args.config)
    filepath = engineer.process_and_save(df)

    if filepath:
        print(f"✓ Features saved to: {filepath}")
        return 0
    else:
        print("✗ Feature engineering failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
