"""
Backtesting Module
Simulates trading strategies and calculates performance metrics
Tests model predictions against historical data
"""

import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from loguru import logger


class Backtester:
    """
    Backtesting engine for BTC trading strategies
    Simulates trades based on model predictions and calculates metrics
    """

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        initial_capital: float = 10000.0,
        position_size: float = 1.0,
        commission: float = 0.001
    ):
        """
        Initialize backtester

        Args:
            config_path: Path to configuration file
            initial_capital: Starting capital in USD
            position_size: Fraction of capital to use per trade (0-1)
            commission: Trading commission (0.001 = 0.1%)
        """
        self.config = self._load_config(config_path)
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.commission = commission

        self.results_dir = Path("backtest_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Trading state
        self.trades = []
        self.equity_curve = []
        self.positions = []

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def run_backtest(
        self,
        predictions_df: pd.DataFrame,
        actual_prices_df: pd.DataFrame,
        strategy: str = "simple"
    ) -> Dict:
        """
        Run backtest on predictions vs actual prices

        Args:
            predictions_df: DataFrame with columns [timestamp, horizon, predicted_price, signal]
            actual_prices_df: DataFrame with columns [timestamp, price]
            strategy: Trading strategy to use ("simple", "threshold", "multi_horizon")

        Returns:
            Dictionary with backtest results and metrics
        """
        logger.info(f"Starting backtest with {strategy} strategy")
        logger.info(f"Initial capital: ${self.initial_capital:,.2f}")
        logger.info(f"Position size: {self.position_size:.1%}")

        # Reset state
        self.trades = []
        self.equity_curve = []
        self.positions = []

        capital = self.initial_capital
        position = None  # Current position: None, 'LONG', or 'SHORT'
        entry_price = 0.0
        position_size_btc = 0.0

        # Sort predictions by timestamp
        predictions_df = predictions_df.sort_values('timestamp').reset_index(drop=True)

        for idx, pred_row in predictions_df.iterrows():
            timestamp = pred_row['timestamp']
            signal = pred_row['signal']
            predicted_price = pred_row['predicted_price']

            # Get actual price at this timestamp
            actual_row = actual_prices_df[actual_prices_df['timestamp'] == timestamp]
            if actual_row.empty:
                continue

            current_price = actual_row.iloc[0]['price']

            # Execute trading logic
            if strategy == "simple":
                capital, position, entry_price, position_size_btc = self._execute_simple_strategy(
                    signal, current_price, capital, position, entry_price, position_size_btc, timestamp
                )

            # Record equity
            if position == 'LONG':
                equity = capital + (position_size_btc * current_price)
            elif position == 'SHORT':
                equity = capital + (entry_price - current_price) * position_size_btc
            else:
                equity = capital

            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': equity,
                'capital': capital,
                'position': position,
                'price': current_price
            })

        # Close any open position at the end
        if position is not None:
            final_price = self.equity_curve[-1]['price']
            capital = self._close_position(position, entry_price, final_price, capital, position_size_btc, timestamp)
            position = None

        # Calculate metrics
        metrics = self._calculate_metrics(capital)

        logger.info(f"Backtest complete. Final capital: ${capital:,.2f}")
        logger.info(f"Total return: {metrics['total_return']:.2%}")

        return {
            'metrics': metrics,
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'final_capital': capital
        }

    def _execute_simple_strategy(
        self,
        signal: str,
        current_price: float,
        capital: float,
        position: Optional[str],
        entry_price: float,
        position_size_btc: float,
        timestamp: datetime
    ) -> Tuple[float, Optional[str], float, float]:
        """
        Execute simple trading strategy
        BUY signal -> go LONG, SELL signal -> close position or go SHORT
        """
        # Close existing position if signal changes
        if position == 'LONG' and signal == 'SELL':
            capital = self._close_position(position, entry_price, current_price, capital, position_size_btc, timestamp)
            position = None
            position_size_btc = 0.0
            entry_price = 0.0

        # Open new position
        if position is None and signal == 'BUY':
            # Go LONG
            trade_capital = capital * self.position_size
            commission_paid = trade_capital * self.commission
            position_size_btc = (trade_capital - commission_paid) / current_price
            capital -= trade_capital
            entry_price = current_price
            position = 'LONG'

            self.positions.append({
                'timestamp': timestamp,
                'type': 'LONG',
                'entry_price': entry_price,
                'size_btc': position_size_btc,
                'capital_used': trade_capital
            })

        return capital, position, entry_price, position_size_btc

    def _close_position(
        self,
        position: str,
        entry_price: float,
        exit_price: float,
        capital: float,
        position_size_btc: float,
        timestamp: datetime
    ) -> float:
        """Close a position and calculate PnL"""
        if position == 'LONG':
            gross_proceeds = position_size_btc * exit_price
            commission_paid = gross_proceeds * self.commission
            net_proceeds = gross_proceeds - commission_paid
            capital += net_proceeds

            pnl = net_proceeds - (position_size_btc * entry_price)
            pnl_pct = (exit_price - entry_price) / entry_price

            self.trades.append({
                'timestamp': timestamp,
                'type': 'LONG',
                'entry_price': entry_price,
                'exit_price': exit_price,
                'size_btc': position_size_btc,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'gross_proceeds': gross_proceeds,
                'commission': commission_paid
            })

        return capital

    def _calculate_metrics(self, final_capital: float) -> Dict[str, float]:
        """Calculate backtesting metrics"""
        metrics = {}

        # Basic returns
        metrics['initial_capital'] = self.initial_capital
        metrics['final_capital'] = final_capital
        metrics['total_return'] = (final_capital - self.initial_capital) / self.initial_capital
        metrics['total_pnl'] = final_capital - self.initial_capital

        # Trade statistics
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            metrics['num_trades'] = len(self.trades)
            metrics['winning_trades'] = (trades_df['pnl'] > 0).sum()
            metrics['losing_trades'] = (trades_df['pnl'] < 0).sum()
            metrics['win_rate'] = metrics['winning_trades'] / metrics['num_trades'] if metrics['num_trades'] > 0 else 0

            metrics['avg_win'] = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if metrics['winning_trades'] > 0 else 0
            metrics['avg_loss'] = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if metrics['losing_trades'] > 0 else 0
            metrics['largest_win'] = trades_df['pnl'].max()
            metrics['largest_loss'] = trades_df['pnl'].min()

            # Profit factor
            total_wins = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
            total_losses = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
            metrics['profit_factor'] = total_wins / total_losses if total_losses > 0 else float('inf')
        else:
            metrics['num_trades'] = 0
            metrics['win_rate'] = 0
            metrics['profit_factor'] = 0

        # Equity curve metrics
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)

            # Drawdown
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']
            metrics['max_drawdown'] = equity_df['drawdown'].min()

            # Sharpe ratio (annualized, assuming 365 days)
            equity_df['returns'] = equity_df['equity'].pct_change()
            if len(equity_df) > 1:
                daily_returns = equity_df['returns'].dropna()
                if len(daily_returns) > 0 and daily_returns.std() > 0:
                    metrics['sharpe_ratio'] = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365)
                else:
                    metrics['sharpe_ratio'] = 0
            else:
                metrics['sharpe_ratio'] = 0
        else:
            metrics['max_drawdown'] = 0
            metrics['sharpe_ratio'] = 0

        return metrics

    def save_results(self, results: Dict, filename: Optional[str] = None) -> str:
        """
        Save backtest results to file

        Args:
            results: Backtest results dictionary
            filename: Custom filename (optional)

        Returns:
            Path where results were saved
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_{timestamp}.json"

        filepath = self.results_dir / filename

        # Convert to JSON-serializable format
        def convert_to_native(obj):
            """Convert numpy types to native Python types"""
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif isinstance(obj, pd.Timestamp):
                return str(obj)
            elif hasattr(obj, 'item'):  # numpy scalar
                return obj.item()
            else:
                return obj

        results_serializable = convert_to_native({
            'metrics': results['metrics'],
            'trades': results['trades'],
            'equity_curve': results['equity_curve'],
            'final_capital': results['final_capital']
        })

        with open(filepath, 'w') as f:
            json.dump(results_serializable, f, indent=2)

        logger.info(f"✓ Backtest results saved to {filepath}")
        return str(filepath)

    def print_summary(self, results: Dict) -> None:
        """Print backtest summary to console"""
        metrics = results['metrics']

        print("\n" + "=" * 80)
        print("BACKTEST RESULTS SUMMARY")
        print("=" * 80)

        print(f"\n💰 CAPITAL:")
        print(f"  Initial Capital: ${metrics['initial_capital']:,.2f}")
        print(f"  Final Capital: ${metrics['final_capital']:,.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:,.2f}")
        print(f"  Total Return: {metrics['total_return']:.2%}")

        print(f"\n📊 TRADE STATISTICS:")
        print(f"  Total Trades: {metrics['num_trades']}")
        print(f"  Winning Trades: {metrics['winning_trades']}")
        print(f"  Losing Trades: {metrics['losing_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.2%}")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")

        if metrics['num_trades'] > 0:
            print(f"\n💵 PROFIT/LOSS:")
            print(f"  Average Win: ${metrics['avg_win']:,.2f}")
            print(f"  Average Loss: ${metrics['avg_loss']:,.2f}")
            print(f"  Largest Win: ${metrics['largest_win']:,.2f}")
            print(f"  Largest Loss: ${metrics['largest_loss']:,.2f}")

        print(f"\n📉 RISK METRICS:")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")

        print("\n" + "=" * 80)


def main():
    """CLI entry point for backtesting"""
    import argparse

    parser = argparse.ArgumentParser(description="Backtest BTC trading strategies")
    parser.add_argument('--predictions', type=str, required=True, help='Path to predictions CSV')
    parser.add_argument('--prices', type=str, required=True, help='Path to actual prices CSV')
    parser.add_argument('--capital', type=float, default=10000.0, help='Initial capital')
    parser.add_argument('--position-size', type=float, default=1.0, help='Position size (0-1)')
    parser.add_argument('--commission', type=float, default=0.001, help='Commission rate')
    parser.add_argument('--strategy', type=str, default='simple', help='Trading strategy')

    args = parser.parse_args()

    # Setup logging
    logger.add("logs/backtest.log", rotation="1 day", retention="7 days")

    # Load data
    predictions_df = pd.read_csv(args.predictions)
    predictions_df['timestamp'] = pd.to_datetime(predictions_df['timestamp'])

    prices_df = pd.read_csv(args.prices)
    prices_df['timestamp'] = pd.to_datetime(prices_df['timestamp'])

    # Run backtest
    backtester = Backtester(
        initial_capital=args.capital,
        position_size=args.position_size,
        commission=args.commission
    )

    results = backtester.run_backtest(predictions_df, prices_df, strategy=args.strategy)

    # Print and save results
    backtester.print_summary(results)
    backtester.save_results(results)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
