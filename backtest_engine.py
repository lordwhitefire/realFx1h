"""
Backtest Engine - Historical analysis of trading setups
Runs setups on historical data to evaluate performance
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yaml
import os


class BacktestEngine:
    """Engine for backtesting trading setups on historical data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.results = []
        self.trades = []
        self.metrics = {}
        
        # Backtest configuration
        self.default_config = {
            'initial_capital': 10000,
            'position_size_pct': 1.0,
            'commission_per_trade': 0,
            'slippage_pct': 0.01,
            'max_trades_per_day': 5,
            'risk_free_rate': 0.02,  # 2% annual
            'start_date': None,
            'end_date': None,
            'timeframe': '5min'
        }
        
        # BINARY TRADING SETTINGS - YOU CAN CHANGE THESE!
        self.bet_amount = 1.0          # Change this to $2, $5, $10, etc.
        self.win_percentage = 0.70     # 70% profit on win
        self.loss_percentage = 1.0     # 100% loss on lose

    def run(self, setups: Dict[str, Any], config: Dict[str, Any], 
            days: int = 30, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Run backtest on historical data
        
        Args:
            setups: Dictionary of loaded setup modules
            config: Global configuration
            days: Number of days to backtest
            symbols: List of symbols to backtest (None = all configured)
            
        Returns:
            Dict[str, Any]: Backtest results
        """
        print(f"\n🎯 DEBUG: Starting backtest engine run()")
        print(f"   Days: {days}")
        print(f"   Number of setups: {len(setups)}")
        print(f"   Setup names: {list(setups.keys())}")
        
        self.logger.info(f"Starting backtest for {days} days")
        
        try:
            # Initialize backtest
            self._initialize_backtest(config, days)
            
            # Get symbols to backtest
            if symbols is None:
                symbols = config.get('pairs', [])
            
            if not symbols:
                print("❌ ERROR: No symbols configured for backtest")
                self.logger.error("No symbols configured for backtest")
                return {}
            
            print(f"✅ DEBUG: Backtesting {len(symbols)} symbols: {symbols}")
            self.logger.info(f"Backtesting {len(symbols)} symbols: {symbols}")
            
            # Run backtest for each symbol
            for symbol in symbols:
                self._backtest_symbol(symbol, setups, config)
            
            # Calculate final metrics
            results = self._calculate_metrics()
            
            print(f"\n📊 DEBUG: Backtest completed")
            print(f"   Total trades found: {len(self.trades)}")
            print(f"   Total results: {len(self.results)}")
            
            self.logger.info(f"Backtest completed: {len(self.trades)} trades analyzed")
            return results
            
        except Exception as e:
            print(f"❌ ERROR: Backtest failed: {e}")
            self.logger.error(f"Backtest failed: {e}")
            return {}
    
    def _initialize_backtest(self, config: Dict[str, Any], days: int) -> None:
        """
        Initialize backtest parameters
        
        Args:
            config: Global configuration
            days: Number of days to backtest
        """
        print(f"\n🔧 DEBUG: Initializing backtest")
        print(f"   Days parameter: {days}")
        
        # Merge config with defaults
        self.backtest_config = {**self.default_config, **config.get('backtest', {})}
        
        # Set date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        self.backtest_config['start_date'] = start_date
        self.backtest_config['end_date'] = end_date
        
        # Initialize results storage
        self.results = []
        self.trades = []
        
        print(f"✅ DEBUG: Backtest period set")
        print(f"   Start date: {start_date.strftime('%Y-%m-%d')}")
        print(f"   End date: {end_date.strftime('%Y-%m-%d')}")
        
        self.logger.info(f"Backtest period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    def _backtest_symbol(self, symbol: str, setups: Dict[str, Any], 
                        config: Dict[str, Any]) -> None:
        """
        Run backtest for a single symbol
        
        Args:
            symbol: Trading symbol
            setups: Dictionary of setup modules
            config: Global configuration
        """
        print(f"\n📈 DEBUG: Starting backtest for {symbol}")
        print(f"   Number of setups to run: {len(setups)}")
        
        self.logger.debug(f"Backtesting {symbol}")
        
        try:
            # Load historical data for this symbol
            print(f"   Loading historical data for {symbol}...")
            historical_data = self._load_historical_data(symbol, config)
            
            if historical_data is None or historical_data.empty:
                print(f"❌ WARNING: No historical data for {symbol}")
                self.logger.warning(f"No historical data for {symbol}")
                return
            
            print(f"✅ DEBUG: Loaded {len(historical_data)} candles for {symbol}")
            print(f"   Date range: {historical_data['timestamp'].iloc[0]} to {historical_data['timestamp'].iloc[-1]}")
            print(f"   Starting analysis from candle 100 to {len(historical_data)}")
            
            # Process each candle
            candles_processed = 0
            signals_found = 0
            
            for i in range(100, len(historical_data) - 1):  # Need at least 2 more candles for exit
                current_data = historical_data.iloc[:i+1].copy()
                current_time = historical_data.iloc[i]['timestamp']
                
                candles_processed += 1
                
                # Run all setups on this data point
                for setup_name, setup_module in setups.items():
                    try:
                        # Get setup-specific config
                        setup_config = self._get_setup_config(setup_name)
                        
                        # DEBUG: Show what we're analyzing
                        if candles_processed % 500 == 0:  # Print every 500 candles
                            print(f"   Analyzing candle {i}/{len(historical_data)} at {current_time}")
                        
                        # Run setup analysis
                        result = setup_module['analyze'](
                            data=current_data,
                            symbol=symbol,
                            global_config=config,
                            setup_config=setup_config,
                            mode='backtest'
                        )
                        
                        if result and result.get('signal_type'):
                            signals_found += 1
                            print(f"🎯 DEBUG: SIGNAL FOUND for {symbol} at {current_time}")
                            print(f"   Signal type: {result.get('signal_type')}")
                            print(f"   Pattern: {result.get('pattern_name')}")
                            print(f"   Confidence: {result.get('confidence', 0):.1f}%")
                            
                            # Process signal as trade
                            trade = self._process_signal_as_trade(
                                result=result,
                                setup_name=setup_name,
                                symbol=symbol,
                                current_data=current_data,
                                current_index=i,
                                historical_data=historical_data
                            )
                            
                            if trade:
                                self.trades.append(trade)
                                self.results.append({
                                    'timestamp': current_time,
                                    'symbol': symbol,
                                    'setup_name': setup_name,
                                    'result': result,
                                    'trade': trade
                                })
                                print(f"💰 DEBUG: Trade processed for {symbol}")
                                print(f"   Entry: {trade.get('entry_price')} at {trade.get('entry_time')}")
                                print(f"   Exit: {trade.get('exit_price')} at {trade.get('exit_time')}")
                                print(f"   Result: {trade.get('result')}")
                        
                    except Exception as e:
                        print(f"❌ ERROR: Error running {setup_name} on {symbol}: {e}")
                        self.logger.error(f"Error running {setup_name} on {symbol}: {e}")
                        continue
            
            print(f"✅ DEBUG: Completed backtest for {symbol}")
            print(f"   Candles processed: {candles_processed}")
            print(f"   Signals found: {signals_found}")
            print(f"   Trades executed: {len([t for t in self.trades if t['symbol'] == symbol])}")
            
            self.logger.debug(f"Completed backtest for {symbol}: {len([t for t in self.trades if t['symbol'] == symbol])} trades")
            
        except Exception as e:
            print(f"❌ ERROR: Error backtesting {symbol}: {e}")
            self.logger.error(f"Error backtesting {symbol}: {e}")
    
    def _load_historical_data(self, symbol: str, config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Load historical data for backtesting
        Uses the same data_fetcher as live mode
        """
        print(f"\n📥 DEBUG: Loading historical data for {symbol}")
        
        try:
            # Use our existing data fetcher
            from data_fetcher import DataFetcher
            
            fetcher = DataFetcher()
            fetcher.load_config()
            
            # Fetch data - this gets the latest 2000 candles (≈7 days)
            print(f"   Fetching data for {symbol}...")
            df = fetcher.fetch_data(symbol, force_refresh=True)  # Force fresh data
            
            if df is not None and not df.empty:
                # For backtesting, we might want more data
                # But for now, use what we can get
                print(f"✅ DEBUG: Successfully loaded {len(df)} candles for {symbol}")
                print(f"   Data shape: {df.shape}")
                print(f"   Columns: {df.columns.tolist()}")
                print(f"   First timestamp: {df['timestamp'].iloc[0]}")
                print(f"   Last timestamp: {df['timestamp'].iloc[-1]}")
                
                self.logger.info(f"Loaded {len(df)} candles for {symbol} for backtesting")
                return df
            else:
                print(f"❌ WARNING: No data fetched for {symbol}")
                self.logger.warning(f"No data fetched for {symbol}")
                return None
                
        except Exception as e:
            print(f"❌ ERROR: Error loading historical data for {symbol}: {e}")
            self.logger.error(f"Error loading historical data for {symbol}: {e}")
            return None
        
    def _get_setup_config(self, setup_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific setup
        
        Args:
            setup_name: Name of the setup
            
        Returns:
            Dict[str, Any]: Setup configuration
        """
        # This should be loaded from the setup's YAML file
        # For now, return empty dict
        return {}
    
    def _process_signal_as_trade(self, result: Dict[str, Any], setup_name: str, 
                                symbol: str, current_data: pd.DataFrame,
                                current_index: int, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Process a signal as a trade for backtesting
        
        Args:
            result: Signal result
            setup_name: Name of the setup
            symbol: Trading symbol
            current_data: Data up to current point
            current_index: Current index in historical data
            historical_data: Full historical data
            
        Returns:
            Optional[Dict[str, Any]]: Trade dictionary or None
        """
        print(f"   🔄 DEBUG: Processing trade for signal")
        
        try:
            # Extract signal info
            signal_type = result.get('signal_type')  # CALL/PUT or BUY/SELL
            confidence = result.get('confidence', 50)
            entry_price = result.get('entry_price')
            
            print(f"      Signal type: {signal_type}")
            print(f"      Confidence: {confidence}")
            print(f"      Entry price: {entry_price}")
            
            if not signal_type or not entry_price:
                print("❌ WARNING: Missing signal_type or entry_price")
                return None
            
            # Determine trade parameters based on setup
            trade_params = self._get_trade_parameters(setup_name, result)
            
            # Find exit conditions (BINARY TRADING: Exit on next candle's opening)
            exit_info = self._binary_trade_exit(
                signal_type=signal_type,
                entry_price=entry_price,
                entry_index=current_index,
                historical_data=historical_data,
                trade_params=trade_params
            )
            
            if not exit_info:
                print("❌ WARNING: Could not simulate trade exit")
                return None
            
            print(f"      Exit info: price={exit_info['exit_price']}, reason={exit_info['exit_reason']}")
            
            # Calculate trade result
            trade_result = self._binary_trade_result(
                signal_type=signal_type,
                entry_price=entry_price,
                exit_price=exit_info['exit_price'],
                trade_params=trade_params
            )
            
            print(f"      Trade result: {trade_result['result']}, P&L={trade_result['pnl']:.4f}")
            
            # Create trade record
            trade = {
                'entry_time': historical_data.iloc[current_index]['timestamp'],
                'exit_time': exit_info['exit_time'],
                'symbol': symbol,
                'setup_name': setup_name,
                'signal_type': signal_type,
                'entry_price': float(entry_price),
                'exit_price': float(exit_info['exit_price']),
                'exit_reason': exit_info['exit_reason'],
                'holding_period_minutes': exit_info['holding_period_minutes'],
                'pnl': trade_result['pnl'],
                'pnl_pct': trade_result['pnl_pct'],
                'result': trade_result['result'],  # WIN/LOSS/BREAKEVEN
                'confidence': confidence,
                'rsi': result.get('rsi'),
                'pattern': result.get('pattern_name'),
            }
            
            print(f"✅ DEBUG: Trade created successfully")
            return trade
            
        except Exception as e:
            print(f"❌ ERROR: Error processing trade: {e}")
            self.logger.error(f"Error processing trade: {e}")
            return None
    
    def _get_trade_parameters(self, setup_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get trade parameters for a setup
        
        Args:
            setup_name: Name of the setup
            result: Signal result
            
        Returns:
            Dict[str, Any]: Trade parameters
        """
        # Simple parameters for binary trading
        params = {
            'position_size': 1.0,  # Fixed position size for binary trading
            'commission': 0,        # No commission
            'slippage': 0,          # No slippage
        }
        
        # Setup-specific parameters could be loaded from setup config
        # For now, use defaults
        
        return params
    
    def _binary_trade_exit(self, signal_type: str, entry_price: float,
                          entry_index: int, historical_data: pd.DataFrame,
                          trade_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        BINARY TRADING: Exit on the NEXT CANDLE's OPENING price
        
        Logic:
        - Candle A: Used to determine setup (pattern detection)
        - Entry at opening of Candle B (immediately after detection)
        - Exit at opening of Candle C (next candle after entry)
        
        Args:
            signal_type: CALL/PUT
            entry_price: Entry price (opening of Candle B)
            entry_index: Entry index in historical data (Candle A's index)
            historical_data: Full historical data
            trade_params: Trade parameters
            
        Returns:
            Optional[Dict[str, Any]]: Exit information or None
        """
        # We need at least 2 candles after the entry candle (Candle A)
        # Candle B = entry_index + 1 (we enter at its opening)
        # Candle C = entry_index + 2 (we exit at its opening)
        
        if entry_index + 2 >= len(historical_data):
            print(f"      ❌ Not enough candles for exit (need 2, have {len(historical_data) - entry_index - 1})")
            return None
        
        # Entry is at opening of Candle B (candle after detection)
        entry_candle_b = historical_data.iloc[entry_index + 1]
        entry_time_b = entry_candle_b['timestamp']
        
        # Exit is at opening of Candle C (next candle after entry)
        exit_candle_c = historical_data.iloc[entry_index + 2]
        exit_time_c = exit_candle_c['timestamp']
        exit_price_c = exit_candle_c['open']
        
        # Calculate holding period in minutes
        # Assuming 5-minute candles, holding from open of B to open of C = 5 minutes
        timeframe_minutes = 5  # Default to 5min, should match your config
        holding_minutes = timeframe_minutes
        
        print(f"      Entry Candle B: {entry_time_b}, Open: {entry_candle_b['open']}")
        print(f"      Exit Candle C: {exit_time_c}, Open: {exit_price_c}")
        print(f"      Holding period: {holding_minutes} minutes")
        
        # Determine win/loss based on binary logic
        if signal_type in ['CALL', 'BUY']:
            # CALL: Win if Candle C opening > Candle B opening
            result = 'WIN' if exit_price_c > entry_candle_b['open'] else 'LOSS'
        else:  # PUT or SELL
            # PUT: Win if Candle C opening < Candle B opening
            result = 'WIN' if exit_price_c < entry_candle_b['open'] else 'LOSS'
        
        return {
            'exit_price': float(exit_price_c),
            'exit_time': exit_time_c,
            'exit_index': entry_index + 2,
            'holding_period_minutes': holding_minutes,
            'exit_reason': result  # 'WIN' or 'LOSS'
        }
    
    def _binary_trade_result(self, signal_type: str, entry_price: float,
                            exit_price: float, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate binary trade result with 70% win / 100% loss
        
        Args:
            signal_type: CALL/PUT
            entry_price: Entry price (opening of Candle B)
            exit_price: Exit price (opening of Candle C)
            trade_params: Trade parameters
            
        Returns:
            Dict[str, Any]: Trade result
        """
        # Determine win/loss
        if signal_type == 'CALL':
            # CALL: Win if exit_price > entry_price
            win = exit_price > entry_price
        else:  # PUT
            # PUT: Win if exit_price < entry_price
            win = exit_price < entry_price
        
        # Calculate P&L based on binary trading rules
        if win:
            # Win: Profit = bet_amount × win_percentage
            pnl = self.bet_amount * self.win_percentage
            result = 'WIN'
        else:
            # Loss: Loss = bet_amount × loss_percentage
            pnl = -self.bet_amount * self.loss_percentage
            result = 'LOSS'
        
        # Percentage return based on initial capital
        pnl_pct = (pnl / self.default_config['initial_capital']) * 100
        
        return {
            'pnl': float(pnl),
            'pnl_pct': float(pnl_pct),
            'result': result,
            'commission': 0,
            'slippage': 0,
            'bet_amount': self.bet_amount  # Store bet amount for reference
        }    
  
    def _calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate backtest performance metrics
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        print(f"\n📊 DEBUG: Calculating metrics")
        print(f"   Total trades: {len(self.trades)}")
        print(f"   Total results: {len(self.results)}")
        
        if not self.trades:
            print("⚠️ WARNING: No trades to calculate metrics for")
            return {
                'summary': {'total_trades': 0, 'message': 'No trades executed'},
                'trades': [],
                'period': f"{self.backtest_config['start_date'].strftime('%Y-%m-%d')} to {self.backtest_config['end_date'].strftime('%Y-%m-%d')}"
            }
        
        # Convert trades to DataFrame
        trades_df = pd.DataFrame(self.trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['result'] == 'WIN'])
        losing_trades = len(trades_df[trades_df['result'] == 'LOSS'])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        print(f"✅ DEBUG: Basic metrics calculated")
        print(f"   Total trades: {total_trades}")
        print(f"   Winning trades: {winning_trades}")
        print(f"   Losing trades: {losing_trades}")
        print(f"   Win rate: {win_rate:.1f}%")
        
        # P&L metrics
        total_pnl = trades_df['pnl'].sum()
        total_pnl_pct = trades_df['pnl_pct'].sum()
        
        avg_pnl = trades_df['pnl'].mean() if total_trades > 0 else 0
        avg_pnl_pct = trades_df['pnl_pct'].mean() if total_trades > 0 else 0
        
        print(f"   Total P&L: ${total_pnl:.2f}")
        print(f"   Average P&L: ${avg_pnl:.2f}")
        
        # Risk metrics
        winning_pnl = trades_df[trades_df['result'] == 'WIN']['pnl'].mean() if winning_trades > 0 else 0
        losing_pnl = trades_df[trades_df['result'] == 'LOSS']['pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(winning_pnl * winning_trades / (losing_pnl * losing_trades)) if losing_trades > 0 and losing_pnl != 0 else float('inf')
        
        # Largest win/loss
        largest_win = trades_df['pnl'].max() if not trades_df['pnl'].empty else 0
        largest_loss = trades_df['pnl'].min() if not trades_df['pnl'].empty else 0
        
        # Setup performance
        setup_performance = {}
        for setup_name in trades_df['setup_name'].unique():
            setup_trades = trades_df[trades_df['setup_name'] == setup_name]
            setup_wins = len(setup_trades[setup_trades['result'] == 'WIN'])
            setup_win_rate = (setup_wins / len(setup_trades) * 100) if len(setup_trades) > 0 else 0
            setup_pnl = setup_trades['pnl'].sum()
            
            setup_performance[setup_name] = {
                'trades': len(setup_trades),
                'wins': setup_wins,
                'win_rate': setup_win_rate,
                'total_pnl': float(setup_pnl),
                'avg_pnl': float(setup_trades['pnl'].mean()) if len(setup_trades) > 0 else 0
            }
        
        # Symbol performance
        symbol_performance = {}
        for symbol in trades_df['symbol'].unique():
            symbol_trades = trades_df[trades_df['symbol'] == symbol]
            symbol_wins = len(symbol_trades[symbol_trades['result'] == 'WIN'])
            symbol_win_rate = (symbol_wins / len(symbol_trades) * 100) if len(symbol_trades) > 0 else 0
            
            # Fix: Convert groupby result to simple dict (not tuple)
            symbol_performance[symbol] = {
                'trades': len(symbol_trades),
                'wins': symbol_wins,
                'win_rate': symbol_win_rate,
                'total_pnl': float(symbol_trades['pnl'].sum()),
                'avg_pnl': float(symbol_trades['pnl'].mean()) if len(symbol_trades) > 0 else 0
            }
        
        # Time-based analysis - FIX tuple keys issue
        trades_df['entry_date'] = pd.to_datetime(trades_df['entry_time']).dt.date
        daily_stats = trades_df.groupby('entry_date').agg({
            'pnl': ['count', 'sum', 'mean']
        })
        
        # Convert MultiIndex columns to simple dict
        daily_analysis = {}
        if not daily_stats.empty:
            # Flatten the MultiIndex columns
            daily_stats.columns = ['_'.join(col).strip() for col in daily_stats.columns.values]
            daily_analysis = {
                'avg_trades_per_day': float(daily_stats['pnl_count'].mean()),
                'max_trades_per_day': int(daily_stats['pnl_count'].max()),
                'most_active_day': daily_stats['pnl_count'].idxmax().strftime('%Y-%m-%d')
            }
        else:
            daily_analysis = {
                'avg_trades_per_day': 0,
                'max_trades_per_day': 0,
                'most_active_day': 'N/A'
            }
        
        # Equity curve
        initial_capital = self.backtest_config['initial_capital']
        equity_curve = [initial_capital]
        
        for pnl in trades_df['pnl'].cumsum():
            equity_curve.append(initial_capital + pnl)
        
        # Add binary trading summary
        binary_summary = {
            'bet_amount': self.bet_amount,
            'win_percentage': self.win_percentage,
            'loss_percentage': self.loss_percentage,
            'expected_value_per_trade': (win_rate/100 * self.bet_amount * self.win_percentage) - 
                                      ((100-win_rate)/100 * self.bet_amount * self.loss_percentage)
        }
        
        metrics = {
            'summary': {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': float(win_rate),
                'total_pnl': float(total_pnl),
                'total_pnl_pct': float(total_pnl_pct),
                'avg_pnl': float(avg_pnl),
                'avg_pnl_pct': float(avg_pnl_pct),
                'profit_factor': float(profit_factor),
                'largest_win': float(largest_win),
                'largest_loss': float(largest_loss),
                'initial_capital': initial_capital,
                'final_equity': float(equity_curve[-1]) if equity_curve else initial_capital
            },
            'binary_settings': binary_summary,
            'setup_performance': setup_performance,
            'symbol_performance': symbol_performance,
            'daily_analysis': daily_analysis,
            'equity_curve': equity_curve,
            'trades': self.trades,
            'period': f"{self.backtest_config['start_date'].strftime('%Y-%m-%d')} to {self.backtest_config['end_date'].strftime('%Y-%m-%d')}"
        }
        
        print(f"✅ DEBUG: Metrics calculation complete")
        print(f"   Bet Amount: ${self.bet_amount}")
        print(f"   Win Payout: {self.win_percentage*100}%")
        print(f"   Loss Payout: {self.loss_percentage*100}%")
        
        return metrics
    
    # ... (rest of the methods remain the same: generate_report, save_report, export_trades_to_csv, etc.)


# Quick test
if __name__ == "__main__":
    print("🧪 Testing BacktestEngine directly...")
    engine = BacktestEngine()
    print("✅ BacktestEngine created successfully")