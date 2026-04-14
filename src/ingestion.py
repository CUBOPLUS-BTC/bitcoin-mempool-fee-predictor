"""
Mempool Data Ingestion Module
Fetches mempool state, fee estimates, and block data from Mempool.space API
Replaces the previous OHLCV/CCXT-based ingestion for price prediction
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
import time
import json
import yaml
from loguru import logger
from typing import Optional, Dict, List, Tuple


class MempoolDataIngestion:
    """
    Fetches real-time mempool and blockchain data from mempool.space API.
    Collects snapshots for training and live inference.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize mempool data ingestion

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.base_url = self.config['data']['mempool_api_base']

        # Setup directories
        self.raw_dir = Path(self.config['data']['raw_dir'])
        self.snapshots_dir = Path(self.config['data']['snapshots_dir'])
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        # HTTP session with retry
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BitcoinFeePredictor/1.0',
            'Accept': 'application/json'
        })

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def _api_get(self, endpoint: str, max_retries: int = 3) -> Optional[dict]:
        """
        Make a GET request to the mempool.space API with retry logic

        Args:
            endpoint: API endpoint path (e.g., '/v1/fees/recommended')
            max_retries: Maximum retry attempts

        Returns:
            Parsed JSON response or None on failure
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    wait_time = 2 ** (attempt + 2)  # 4, 8, 16 seconds
                    logger.warning(f"Rate limited. Waiting {wait_time}s... (attempt {attempt + 1})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP error for {endpoint}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {endpoint}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        logger.error(f"All {max_retries} retries failed for {endpoint}")
        return None

    # =========================================================================
    # Individual API Fetchers
    # =========================================================================

    def fetch_recommended_fees(self) -> Optional[Dict]:
        """
        Fetch recommended fee rates from mempool.space

        Returns:
            Dict with fastestFee, halfHourFee, hourFee, economyFee, minimumFee
        """
        return self._api_get("/v1/fees/recommended")

    def fetch_mempool_state(self) -> Optional[Dict]:
        """
        Fetch current mempool statistics

        Returns:
            Dict with count (tx count), vsize (total vBytes), total_fee, etc.
        """
        return self._api_get("/mempool")

    def fetch_mempool_blocks(self) -> Optional[List]:
        """
        Fetch projected mempool blocks (fee ranges per projected block)

        Returns:
            List of projected block dicts with fee ranges
        """
        return self._api_get("/v1/fees/mempool-blocks")

    def fetch_recent_blocks(self, count: int = 10) -> Optional[List]:
        """
        Fetch recently mined blocks

        Args:
            count: Number of recent blocks to analyze

        Returns:
            List of block dicts
        """
        blocks = self._api_get("/v1/blocks")
        if blocks:
            return blocks[:count]
        return None

    def fetch_hashrate(self) -> Optional[Dict]:
        """
        Fetch recent hashrate data

        Returns:
            Dict with hashrate information
        """
        return self._api_get("/v1/mining/hashrate/3d")

    def fetch_difficulty_adjustment(self) -> Optional[Dict]:
        """
        Fetch difficulty adjustment info

        Returns:
            Dict with progressPercent, difficultyChange, estimatedRetargetDate, etc.
        """
        return self._api_get("/v1/difficulty-adjustment")

    # =========================================================================
    # Composite Snapshot
    # =========================================================================

    def fetch_full_snapshot(self) -> Optional[Dict]:
        """
        Fetch a complete mempool snapshot combining all data sources.
        This is the primary method for data collection.

        Returns:
            Dict with all mempool, fee, block, and mining data
        """
        logger.debug("Fetching full mempool snapshot...")

        try:
            snapshot = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'timestamp_unix': int(datetime.now(timezone.utc).timestamp()),
            }

            # 1. Recommended fees (CRITICAL)
            fees = self.fetch_recommended_fees()
            if fees is None:
                logger.error("Failed to fetch recommended fees - aborting snapshot")
                return None

            snapshot['fee_fastest'] = fees.get('fastestFee', 0)
            snapshot['fee_half_hour'] = fees.get('halfHourFee', 0)
            snapshot['fee_hour'] = fees.get('hourFee', 0)
            snapshot['fee_economy'] = fees.get('economyFee', 0)
            snapshot['fee_minimum'] = fees.get('minimumFee', 0)

            # 2. Mempool state
            mempool = self.fetch_mempool_state()
            if mempool:
                snapshot['mempool_tx_count'] = mempool.get('count', 0)
                snapshot['mempool_vsize'] = mempool.get('vsize', 0)
                snapshot['mempool_total_fee'] = mempool.get('total_fee', 0)
            else:
                snapshot['mempool_tx_count'] = 0
                snapshot['mempool_vsize'] = 0
                snapshot['mempool_total_fee'] = 0

            # 3. Projected mempool blocks
            mempool_blocks = self.fetch_mempool_blocks()
            if mempool_blocks:
                for i, block in enumerate(mempool_blocks[:8]):  # Up to 8 projected blocks
                    prefix = f"projected_block_{i}"
                    snapshot[f"{prefix}_median_fee"] = block.get('medianFee', 0)
                    snapshot[f"{prefix}_fee_range_min"] = block.get('feeRange', [0])[0] if block.get('feeRange') else 0
                    snapshot[f"{prefix}_fee_range_max"] = block.get('feeRange', [0])[-1] if block.get('feeRange') else 0
                    snapshot[f"{prefix}_n_tx"] = block.get('nTx', 0)
                    snapshot[f"{prefix}_total_vsize"] = block.get('blockVSize', 0)

                # Pad missing projected blocks with zeros
                for i in range(len(mempool_blocks), 8):
                    prefix = f"projected_block_{i}"
                    snapshot[f"{prefix}_median_fee"] = 0
                    snapshot[f"{prefix}_fee_range_min"] = 0
                    snapshot[f"{prefix}_fee_range_max"] = 0
                    snapshot[f"{prefix}_n_tx"] = 0
                    snapshot[f"{prefix}_total_vsize"] = 0

            # 4. Recent confirmed blocks
            blocks = self.fetch_recent_blocks(count=10)
            if blocks:
                # Latest block info
                latest = blocks[0]
                snapshot['last_block_height'] = latest.get('height', 0)
                snapshot['last_block_timestamp'] = latest.get('timestamp', 0)
                snapshot['last_block_tx_count'] = latest.get('tx_count', 0)
                snapshot['last_block_size'] = latest.get('size', 0)
                snapshot['last_block_weight'] = latest.get('weight', 0)

                # Extract median fee rates from block extras if available
                extras = latest.get('extras', {})
                snapshot['last_block_median_fee'] = extras.get('medianFee', 0)
                snapshot['last_block_avg_fee'] = extras.get('avgFee', 0)
                snapshot['last_block_min_fee'] = extras.get('feeRange', [0])[0] if extras.get('feeRange') else 0
                snapshot['last_block_max_fee'] = extras.get('feeRange', [0])[-1] if extras.get('feeRange') else 0
                snapshot['last_block_reward'] = extras.get('reward', 0)

                # Block timing analysis
                block_times = []
                for j in range(len(blocks) - 1):
                    t_diff = blocks[j].get('timestamp', 0) - blocks[j + 1].get('timestamp', 0)
                    if t_diff > 0:
                        block_times.append(t_diff)

                if block_times:
                    snapshot['avg_block_time_last3'] = np.mean(block_times[:3]) if len(block_times) >= 3 else np.mean(block_times)
                    snapshot['avg_block_time_last6'] = np.mean(block_times[:6]) if len(block_times) >= 6 else np.mean(block_times)
                    snapshot['std_block_time_last6'] = np.std(block_times[:6]) if len(block_times) >= 6 else np.std(block_times)
                else:
                    snapshot['avg_block_time_last3'] = 600
                    snapshot['avg_block_time_last6'] = 600
                    snapshot['std_block_time_last6'] = 0

                # Blocks mined in last hour (approximate)
                one_hour_ago = int(datetime.now(timezone.utc).timestamp()) - 3600
                blocks_last_hour = sum(1 for b in blocks if b.get('timestamp', 0) > one_hour_ago)
                snapshot['blocks_last_hour'] = blocks_last_hour

                # Time since last block (seconds)
                snapshot['time_since_last_block'] = int(datetime.now(timezone.utc).timestamp()) - latest.get('timestamp', int(datetime.now(timezone.utc).timestamp()))

                # Fee statistics from recent blocks
                recent_fees = []
                for b in blocks[:6]:
                    ext = b.get('extras', {})
                    mf = ext.get('medianFee', 0)
                    if mf > 0:
                        recent_fees.append(mf)

                if recent_fees:
                    snapshot['avg_block_median_fee_last6'] = np.mean(recent_fees)
                    snapshot['min_block_median_fee_last6'] = np.min(recent_fees)
                    snapshot['max_block_median_fee_last6'] = np.max(recent_fees)
                else:
                    snapshot['avg_block_median_fee_last6'] = 0
                    snapshot['min_block_median_fee_last6'] = 0
                    snapshot['max_block_median_fee_last6'] = 0
            else:
                # Default block values
                for key in ['last_block_height', 'last_block_timestamp', 'last_block_tx_count',
                            'last_block_size', 'last_block_weight', 'last_block_median_fee',
                            'last_block_avg_fee', 'last_block_min_fee', 'last_block_max_fee',
                            'last_block_reward', 'blocks_last_hour', 'time_since_last_block',
                            'avg_block_median_fee_last6', 'min_block_median_fee_last6',
                            'max_block_median_fee_last6']:
                    snapshot[key] = 0
                snapshot['avg_block_time_last3'] = 600
                snapshot['avg_block_time_last6'] = 600
                snapshot['std_block_time_last6'] = 0

            # 5. Mining / Difficulty (less frequent, OK if fails)
            difficulty = self.fetch_difficulty_adjustment()
            if difficulty:
                snapshot['difficulty_progress_pct'] = difficulty.get('progressPercent', 0)
                snapshot['difficulty_change_pct'] = difficulty.get('difficultyChange', 0)
                snapshot['difficulty_remaining_blocks'] = difficulty.get('remainingBlocks', 0)
                snapshot['estimated_retarget_change_pct'] = difficulty.get('estimatedRetargetPercentage', 0)
            else:
                snapshot['difficulty_progress_pct'] = 0
                snapshot['difficulty_change_pct'] = 0
                snapshot['difficulty_remaining_blocks'] = 0
                snapshot['estimated_retarget_change_pct'] = 0

            hashrate_data = self.fetch_hashrate()
            if hashrate_data and 'currentHashrate' in hashrate_data:
                snapshot['hashrate_current'] = hashrate_data.get('currentHashrate', 0)
                snapshot['hashrate_avg_3d'] = hashrate_data.get('avgHashrate', 0)
            else:
                snapshot['hashrate_current'] = 0
                snapshot['hashrate_avg_3d'] = 0

            logger.info(
                f"✓ Snapshot captured: "
                f"fees=[{snapshot['fee_fastest']}/{snapshot['fee_half_hour']}/{snapshot['fee_hour']}] sats/vB, "
                f"mempool={snapshot['mempool_tx_count']} txs, "
                f"vsize={snapshot['mempool_vsize'] / 1e6:.1f} MvB"
            )

            return snapshot

        except Exception as e:
            logger.error(f"Failed to fetch full snapshot: {e}")
            return None

    # =========================================================================
    # Data Persistence
    # =========================================================================

    def save_snapshot(self, snapshot: Dict, filename: Optional[str] = None) -> str:
        """
        Save a single snapshot to disk as JSON

        Args:
            snapshot: Snapshot dictionary
            filename: Custom filename

        Returns:
            Path where snapshot was saved
        """
        try:
            ts = datetime.fromisoformat(snapshot['timestamp'].replace('Z', '+00:00'))
            date_dir = self.snapshots_dir / ts.strftime("%Y/%m/%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            if filename is None:
                filename = f"snapshot_{ts.strftime('%H%M%S')}.json"

            filepath = date_dir / filename
            with open(filepath, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)

            logger.debug(f"Snapshot saved to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            raise

    def save_snapshots_batch(
        self,
        snapshots: List[Dict],
        filename: Optional[str] = None
    ) -> str:
        """
        Save multiple snapshots as a Parquet file for efficient storage

        Args:
            snapshots: List of snapshot dictionaries
            filename: Custom filename

        Returns:
            Path where data was saved
        """
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"mempool_snapshots_{timestamp}.parquet"

            df = pd.DataFrame(snapshots)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])

            filepath = self.snapshots_dir / filename
            df.to_parquet(filepath, index=False, engine='pyarrow')

            logger.info(f"✓ Saved {len(snapshots)} snapshots to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save snapshots batch: {e}")
            raise

    def load_snapshots(self, filepath: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Load snapshots from Parquet or CSV file

        Args:
            filepath: Path to data file. If None, loads the latest file.

        Returns:
            DataFrame with snapshot data
        """
        try:
            if filepath:
                fp = Path(filepath)
            else:
                # Find latest parquet file
                parquet_files = sorted(
                    self.snapshots_dir.glob("**/*.parquet"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                if not parquet_files:
                    # Try CSV fallback
                    csv_files = sorted(
                        self.snapshots_dir.glob("**/*.csv"),
                        key=lambda x: x.stat().st_mtime,
                        reverse=True
                    )
                    if not csv_files:
                        logger.warning("No snapshot files found")
                        return None
                    fp = csv_files[0]
                else:
                    fp = parquet_files[0]

            logger.info(f"Loading snapshots from {fp}")

            if fp.suffix == '.parquet':
                df = pd.read_parquet(fp)
            else:
                df = pd.read_csv(fp)

            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])

            logger.info(f"✓ Loaded {len(df)} snapshots from {fp.name}")
            return df

        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")
            return None

    def load_all_snapshots_from_json(self) -> Optional[pd.DataFrame]:
        """
        Load all individual JSON snapshots and combine into a DataFrame

        Returns:
            DataFrame with all historical snapshots
        """
        try:
            json_files = sorted(self.snapshots_dir.glob("**/*.json"))

            if not json_files:
                logger.warning("No JSON snapshot files found")
                return None

            snapshots = []
            for jf in json_files:
                try:
                    with open(jf, 'r') as f:
                        snapshots.append(json.load(f))
                except Exception as e:
                    logger.warning(f"Skipping corrupt file {jf}: {e}")

            if not snapshots:
                return None

            df = pd.DataFrame(snapshots)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)

            # Remove duplicates
            if 'timestamp_unix' in df.columns:
                df = df.drop_duplicates(subset=['timestamp_unix']).reset_index(drop=True)

            logger.info(f"✓ Loaded {len(df)} snapshots from JSON files")
            return df

        except Exception as e:
            logger.error(f"Failed to load JSON snapshots: {e}")
            return None

    def _validate_snapshot(self, snapshot: Dict) -> Tuple[bool, str]:
        """
        Validate a snapshot for data quality

        Args:
            snapshot: Snapshot dictionary to validate

        Returns:
            Tuple of (is_valid, message)
        """
        issues = []

        # Check required fields
        required_fields = ['fee_fastest', 'fee_half_hour', 'fee_hour',
                           'mempool_tx_count', 'mempool_vsize']
        for field in required_fields:
            if field not in snapshot or snapshot[field] is None:
                issues.append(f"Missing required field: {field}")

        # Check fee sanity
        if snapshot.get('fee_fastest', 0) < snapshot.get('fee_hour', 0):
            issues.append("fee_fastest < fee_hour (unexpected inversion)")

        if snapshot.get('fee_fastest', 0) <= 0:
            issues.append("fee_fastest <= 0")

        # Check mempool sanity
        if snapshot.get('mempool_tx_count', 0) < 0:
            issues.append("Negative mempool tx count")

        if issues:
            return False, "; ".join(issues)
        return True, "Snapshot quality: OK"

    def fetch_and_save(self) -> Optional[str]:
        """
        Convenience method: Fetch a snapshot and save it

        Returns:
            Path to saved file
        """
        snapshot = self.fetch_full_snapshot()

        if snapshot is not None:
            is_valid, msg = self._validate_snapshot(snapshot)
            logger.info(f"Validation: {msg}")
            return self.save_snapshot(snapshot)
        else:
            logger.error("Snapshot fetching failed")
            return None


def main():
    """CLI entry point for mempool data ingestion"""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch mempool state data")
    parser.add_argument('--config', type=str, default='config/config.yaml', help='Config file path')
    parser.add_argument('--continuous', action='store_true', help='Run continuously (collector mode)')
    parser.add_argument('--interval', type=int, default=None, help='Override polling interval (seconds)')
    parser.add_argument('--consolidate', action='store_true', help='Consolidate JSON snapshots to Parquet')

    args = parser.parse_args()

    # Setup logging
    logger.add("logs/ingestion.log", rotation="1 day", retention="7 days")

    ingestion = MempoolDataIngestion(config_path=args.config)

    if args.consolidate:
        # Load all JSON snapshots and save as Parquet
        df = ingestion.load_all_snapshots_from_json()
        if df is not None:
            path = ingestion.save_snapshots_batch(df.to_dict('records'))
            print(f"✓ Consolidated {len(df)} snapshots to: {path}")
        else:
            print("✗ No snapshots to consolidate")
        return 0

    if args.continuous:
        interval = args.interval or ingestion.config['data']['polling_interval_seconds']
        print(f"🔄 Starting continuous collection (every {interval}s)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                path = ingestion.fetch_and_save()
                if path:
                    print(f"  ✓ Saved: {path}")
                else:
                    print(f"  ✗ Failed to fetch snapshot")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n⏹ Collection stopped")
            return 0
    else:
        # Single fetch
        filepath = ingestion.fetch_and_save()
        if filepath:
            print(f"✓ Snapshot saved to: {filepath}")
            return 0
        else:
            print("✗ Failed to fetch mempool data")
            return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
