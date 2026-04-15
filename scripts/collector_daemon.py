#!/usr/bin/env python3
"""
Mempool Collector Daemon
Runs 24/7 collecting mempool state snapshots every 2 minutes.
This is CRITICAL: mempool.space doesn't offer historical mempool state data,
so we must build our own dataset for training.

Supports optional Bitcoin Core RPC for higher quality data.

Usage:
    python scripts/collector_daemon.py                    # Run with defaults
    python scripts/collector_daemon.py --interval 60      # Every 60 seconds
    python scripts/collector_daemon.py --test-run          # Collect 5 snapshots and exit
    python scripts/collector_daemon.py --consolidate       # Merge JSONs to Parquet
"""

import sys
import os
import time
import json
import signal
from pathlib import Path
from datetime import datetime, timezone
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion import MempoolDataIngestion


class BitcoinRPCClient:
    """
    Lightweight Bitcoin Core RPC client for complementary mempool data.
    Provides estimatesmartfee and getmempoolinfo.
    """

    def __init__(self, host: str, port: int, user: str, password: str):
        self.url = f"http://{user}:{password}@{host}:{port}"
        self.enabled = bool(password)

    def _call(self, method: str, params: list = None) -> dict:
        """Make an RPC call to Bitcoin Core"""
        import requests

        payload = {
            "jsonrpc": "2.0",
            "id": "fee_predictor",
            "method": method,
            "params": params or []
        }

        try:
            response = requests.post(self.url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            if 'error' in result and result['error'] is not None:
                logger.warning(f"RPC error ({method}): {result['error']}")
                return None
            return result.get('result')
        except Exception as e:
            logger.debug(f"RPC call failed ({method}): {e}")
            return None

    def get_mempool_info(self) -> dict:
        """Call getmempoolinfo"""
        return self._call("getmempoolinfo")

    def estimate_smart_fee(self, conf_target: int) -> dict:
        """Call estimatesmartfee for a given confirmation target"""
        return self._call("estimatesmartfee", [conf_target])

    def get_blockchain_info(self) -> dict:
        """Call getblockchaininfo"""
        return self._call("getblockchaininfo")

    def enrich_snapshot(self, snapshot: dict) -> dict:
        """Add RPC data to a mempool.space snapshot"""
        if not self.enabled:
            return snapshot

        # getmempoolinfo
        mempool_info = self.get_mempool_info()
        if mempool_info:
            snapshot['rpc_mempool_size'] = mempool_info.get('size', 0)
            snapshot['rpc_mempool_bytes'] = mempool_info.get('bytes', 0)
            snapshot['rpc_mempool_usage'] = mempool_info.get('usage', 0)
            snapshot['rpc_mempool_maxmempool'] = mempool_info.get('maxmempool', 0)
            snapshot['rpc_mempool_minfee'] = mempool_info.get('mempoolminfee', 0)

        # estimatesmartfee for various confirmation targets
        for target in [1, 3, 6, 12, 25]:
            result = self.estimate_smart_fee(target)
            if result and 'feerate' in result:
                snapshot[f'rpc_est_fee_{target}'] = result['feerate']
            else:
                snapshot[f'rpc_est_fee_{target}'] = 0

        return snapshot


class CollectorDaemon:
    """
    Daemon process that continuously collects mempool snapshots.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.ingestion = MempoolDataIngestion(config_path=config_path)
        self.config = self.ingestion.config
        self.running = True
        self.snapshot_count = 0
        self.error_count = 0

        # Setup Bitcoin Core RPC if configured
        self.rpc_client = None
        rpc_config = self.config.get('data', {})
        if rpc_config.get('bitcoin_rpc_enabled', False):
            rpc_password = os.environ.get('BITCOIN_RPC_PASSWORD',
                                           rpc_config.get('bitcoin_rpc_password', ''))
            if rpc_password:
                self.rpc_client = BitcoinRPCClient(
                    host=rpc_config.get('bitcoin_rpc_host', '127.0.0.1'),
                    port=rpc_config.get('bitcoin_rpc_port', 8332),
                    user=rpc_config.get('bitcoin_rpc_user', 'bitcoinrpc'),
                    password=rpc_password,
                )
                logger.info("✓ Bitcoin Core RPC client initialized")
            else:
                logger.warning("Bitcoin RPC enabled but no password set. Skipping RPC.")

        # Handle graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Graceful shutdown handler"""
        logger.info(" Shutdown signal received. Finishing current snapshot...")
        self.running = False

    def collect_single(self) -> bool:
        """Collect a single snapshot"""
        try:
            snapshot = self.ingestion.fetch_full_snapshot()
            if snapshot is None:
                self.error_count += 1
                return False

            # Enrich with Bitcoin Core RPC data
            if self.rpc_client:
                snapshot = self.rpc_client.enrich_snapshot(snapshot)

            # Validate
            is_valid, msg = self.ingestion._validate_snapshot(snapshot)
            if not is_valid:
                logger.warning(f"Snapshot validation: {msg}")

            # Save
            self.ingestion.save_snapshot(snapshot)
            self.snapshot_count += 1

            # Log summary
            logger.info(
                f" #{self.snapshot_count} | "
                f"fees=[{snapshot.get('fee_fastest', '?')}/{snapshot.get('fee_half_hour', '?')}/{snapshot.get('fee_hour', '?')}] | "
                f"mempool={snapshot.get('mempool_tx_count', 0):,} txs | "
                f"vsize={snapshot.get('mempool_vsize', 0) / 1e6:.1f} MvB"
                + (f" | RPC✓" if self.rpc_client and 'rpc_mempool_size' in snapshot else "")
            )

            return True

        except Exception as e:
            logger.error(f"Collection error: {e}")
            self.error_count += 1
            return False

    def run(self, interval: int = None, max_snapshots: int = None):
        """
        Run the collector loop.

        Args:
            interval: Override polling interval (seconds)
            max_snapshots: Stop after N snapshots (for testing)
        """
        interval = interval or self.config['data']['polling_interval_seconds']

        logger.info("=" * 80)
        logger.info(" MEMPOOL COLLECTOR DAEMON STARTED")
        logger.info(f"   Interval: {interval}s")
        logger.info(f"   Snapshots dir: {self.ingestion.snapshots_dir}")
        logger.info(f"   Bitcoin Core RPC: {'✓ Enabled' if self.rpc_client else '✗ Disabled'}")
        if max_snapshots:
            logger.info(f"   Max snapshots: {max_snapshots}")
        logger.info("=" * 80)

        while self.running:
            self.collect_single()

            if max_snapshots and self.snapshot_count >= max_snapshots:
                logger.info(f"Reached max snapshots ({max_snapshots}). Stopping.")
                break

            # Sleep with interruptibility
            for _ in range(int(interval)):
                if not self.running:
                    break
                time.sleep(1)

        # Summary
        logger.info("=" * 80)
        logger.info(" COLLECTOR SUMMARY")
        logger.info(f"   Snapshots collected: {self.snapshot_count}")
        logger.info(f"   Errors: {self.error_count}")
        logger.info("=" * 80)

    def consolidate_to_parquet(self):
        """Merge all JSON snapshots into a single Parquet file"""
        logger.info(" Consolidating JSON snapshots to Parquet...")

        df = self.ingestion.load_all_snapshots_from_json()
        if df is not None and len(df) > 0:
            path = self.ingestion.save_snapshots_batch(df.to_dict('records'))
            logger.info(f"✓ Consolidated {len(df)} snapshots → {path}")
            return path
        else:
            logger.warning("No snapshots to consolidate")
            return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Mempool Collector Daemon")
    parser.add_argument('--config', type=str, default='config/config.yaml')
    parser.add_argument('--interval', type=int, default=None, help='Override polling interval (seconds)')
    parser.add_argument('--test-run', action='store_true', help='Collect 5 snapshots and exit')
    parser.add_argument('--consolidate', action='store_true', help='Merge JSON snapshots to Parquet')

    args = parser.parse_args()

    # Setup logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "collector_daemon.log",
        rotation="10 MB",
        retention="30 days",
        level="INFO"
    )

    daemon = CollectorDaemon(config_path=args.config)

    if args.consolidate:
        daemon.consolidate_to_parquet()
    elif args.test_run:
        daemon.run(interval=args.interval or 8, max_snapshots=args.max_snapshots)
    else:
        daemon.run(interval=args.interval)


if __name__ == "__main__":
    main()
