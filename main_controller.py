#!/usr/bin/env python3
"""
Main Controller - Trading Setup Scanner
Orchestrates data fetching, setup analysis, and alerting
"""

import sys
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any

# Import our modules
from data_fetcher import DataFetcher
from setup_loader import SetupLoader
from alert_manager import AlertManager
from result_aggregator import ResultAggregator
from backtest_engine import BacktestEngine
from backtest_report import BacktestReport
from utils.logger import setup_logger


class MainController:
    """Main controller that orchestrates the entire trading setup scanner"""
    
    def __init__(self, mode: str = 'live'):
        """
        Initialize the main controller
        
        Args:
            mode: 'live' for real-time scanning, 'backtest' for historical analysis
        """
        self.mode = mode
        self.logger = setup_logger('controller')
        
        # Initialize components
        self.data_fetcher = DataFetcher()
        self.setup_loader = SetupLoader()
        self.alert_manager = AlertManager()
        self.result_aggregator = ResultAggregator()
        self.backtest_engine = BacktestEngine() if mode == 'backtest' else None
        
        # State tracking
        self.active_setups = []
        self.last_scan_time = None
        self.scan_count = 0
        
        self.logger.info(f"Main Controller initialized in {mode} mode")
        
    def load_configuration(self) -> bool:
        """Load all configurations and setups"""
        try:
            # Load global configuration
            config_loaded = self.data_fetcher.load_config()
            if not config_loaded:
                self.logger.error("Failed to load global configuration")
                return False
            
            # Load all trading setups
            setups_loaded = self.setup_loader.load_all_setups()
            if not setups_loaded:
                self.logger.error("No trading setups loaded")
                return False
            
            # Initialize alert manager with config
            self.alert_manager.initialize(self.data_fetcher.config)
            
            self.logger.info(f"Loaded {len(self.setup_loader.setups)} trading setups")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration loading failed: {e}")
            return False
    
    def fetch_market_data(self) -> Dict[str, Any]:
        """Fetch market data once for all setups"""
        try:
            self.logger.debug("Fetching market data...")
            
            # Get symbols from configuration
            symbols = self.data_fetcher.config.get('pairs', [])
            if not symbols:
                self.logger.error("No trading pairs configured")
                return {}
            
            # Fetch data for all symbols
            market_data = {}
            for symbol in symbols:
                data = self.data_fetcher.fetch_data(symbol)
                if data is not None and not data.empty:
                    market_data[symbol] = data
                    self.logger.debug(f"Fetched {len(data)} candles for {symbol}")
                else:
                    self.logger.warning(f"No data fetched for {symbol}")
            
            self.logger.info(f"Fetched data for {len(market_data)}/{len(symbols)} symbols")
            return market_data
            
        except Exception as e:
            self.logger.error(f"Market data fetch failed: {e}")
            return {}
    
    def run_setup_analysis(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Run analysis on all loaded setups
        
        Args:
            market_data: Dictionary of symbol -> DataFrame pairs
            
        Returns:
            List of all setup results
        """
        all_results = []
        
        if not market_data:
            self.logger.warning("No market data available for analysis")
            
            return all_results
        
        # Run each setup on each symbol
        for setup_name, setup_module in self.setup_loader.setups.items():
            self.logger.debug(f"Running analysis for setup: {setup_name}")
            
            for symbol, data in market_data.items():
                try:
                    # Get setup-specific configuration
                    setup_config = self.setup_loader.get_setup_config(setup_name)
                    
                    # Run the setup analysis
                    result = setup_module['analyze'](
                        data=data,
                        symbol=symbol,
                        global_config=self.data_fetcher.config,
                        setup_config=setup_config,
                        mode=self.mode
                    )
                    
                    if result:
                        # Add metadata
                        result['setup_name'] = setup_name
                        result['symbol'] = symbol
                        result['analysis_time'] = datetime.utcnow()
                        
                        all_results.append(result)
                        self.logger.debug(f"Setup {setup_name} found result for {symbol}")
                        
                except Exception as e:
                    self.logger.error(f"Analysis failed for {setup_name} on {symbol}: {e}")
        
        if not all_results:
            print(f"\n📊 No setups detected in this scan.")
            self.logger.info("No setups detected in this scan")
        
        return all_results
    
    def process_results(self, all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process and aggregate all setup results
        
        Args:
            all_results: Raw results from all setups
            
        Returns:
            Aggregated and processed results
        """
        if not all_results:
            self.logger.debug("No results to process")
            return {}
        
        # Aggregate results
        aggregated = self.result_aggregator.aggregate_results(all_results)
        
        # Filter significant results (for alerts)
        significant_results = self.result_aggregator.filter_significant_results(all_results)
        
        # Print results to console
        self._print_results_to_console(aggregated, significant_results)
        
        return {
            'aggregated': aggregated,
            'significant': significant_results,
            'raw': all_results
        }
    
    def _print_results_to_console(self, aggregated: Dict[str, Any], 
                                  significant_results: List[Dict[str, Any]]) -> None:
        """Print analysis results to console"""
        print("\n" + "="*60)
        print(f"SCAN RESULTS - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("="*60)
        
        # Print aggregated summary
        total_setups = aggregated.get('total_setups_analyzed', 0)
        total_signals = aggregated.get('total_signals_found', 0)
        print(f"\n📊 Summary: Analyzed {total_setups} setup/symbol combinations")
        print(f"📈 Signals Found: {total_signals}")
        
        # Print significant signals
        if significant_results:
            print(f"\n🔔 SIGNIFICANT SIGNALS ({len(significant_results)}):")
            for result in significant_results:
                setup = result.get('setup_name', 'Unknown')
                symbol = result.get('symbol', 'Unknown')
                signal = result.get('signal_type', 'Unknown')
                confidence = result.get('confidence', 0)
                print(f"   • {setup} on {symbol}: {signal} (Confidence: {confidence}%)")
        else:
            print("\n📭 No significant signals found")
        
        print("\n" + "="*60)
    
    async def send_alerts(self, results: Dict[str, Any]) -> None:
        """Send alerts for significant results"""
        significant_results = results.get('significant', [])
        
        if not significant_results:
            self.logger.debug("No significant results to alert")
            # Send test message when no results
            try:
                # Direct Telegram test message
                test_message = "TEST: Single scan working! No trading setups found in this scan."
                telegram_sent = await self.alert_manager._send_telegram_alert(test_message)
                if telegram_sent:
                    self.logger.info("Sent test alert (no setups found)")
                else:
                    self.logger.warning("Failed to send test alert")
            except Exception as e:
                self.logger.error(f"Test alert failed: {e}")
            return
        
        try:
            success_count = 0
            for result in significant_results:
                alert_sent = await self.alert_manager.send_setup_alert(result)
                if alert_sent:
                    success_count += 1
            
            self.logger.info(f"Sent {success_count}/{len(significant_results)} alerts")
            
        except Exception as e:
            self.logger.error(f"Alert sending failed: {e}")   

    async def run_backtest(self, days: int = 30) -> Dict[str, Any]:
        """Run historical backtest"""
        if self.mode != 'backtest':
            self.logger.error("Backtest called in live mode")
            return {}
        
        self.logger.info(f"Starting backtest for {days} days")
        
        try:
            # Run backtest
            backtest_results = self.backtest_engine.run(
                setups=self.setup_loader.setups,
                config=self.data_fetcher.config,
                days=days
            )
            
            # ✅ CORRECT: Use BacktestReport class
            report_generator = BacktestReport()  # Create report generator
            report = report_generator.generate_comprehensive_report(backtest_results)
            
            # Print report to console
            self._print_backtest_report(report)
            
            # Send summary via Telegram
            await self.alert_manager.send_backtest_report(report)
            
            return backtest_results
            
        except Exception as e:
            self.logger.error(f"Backtest failed: {e}")
            return {}
    
    def _print_backtest_report(self, backtest_results: Dict[str, Any]) -> None:
        """Print backtest report to console by reading the latest .txt file"""
        import os
        import glob
        
        print("\n" + "="*60)
        print("BACKTEST RESULTS SUMMARY")
        print("="*60)
        
        # Find all .txt report files
        report_files = glob.glob("reports/*.txt")
        
        if not report_files:
            print("No backtest report files found")
            print("="*60)
            return
        
        # Sort by modification time (newest first)
        report_files.sort(key=os.path.getmtime, reverse=True)
        latest_file = report_files[0]
        
        print(f"\n📄 Reading latest report: {os.path.basename(latest_file)}")
        print("-" * 60)
        
        try:
            # Read and print the entire file
            with open(latest_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
                print(file_content)
            
        except Exception as e:
            print(f"❌ Error reading report file: {e}")
            print("="*60)

    async def run_single_scan(self) -> bool:
        """Run a single scanning cycle"""
        try:
            self.scan_count += 1
            self.last_scan_time = datetime.utcnow()
            
            self.logger.info(f"Starting scan #{self.scan_count}")
            
            # Fetch market data once
            market_data = self.fetch_market_data()
            if not market_data:
                self.logger.warning("No market data available, skipping scan")
                return False
            
            # Run all setups
            all_results = self.run_setup_analysis(market_data)
            
            # Process results
            processed_results = self.process_results(all_results)
            
            # Send alerts (in live mode only)
            if self.mode == 'live' and processed_results:
                await self.send_alerts(processed_results)

            if self.mode == 'live':
                await self.send_alerts(processed_results)

            self.logger.info(f"Scan #{self.scan_count} completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Scan #{self.scan_count} failed: {e}")
            return False
 
    async def run_continuous(self, interval_minutes: int = 1) -> None:
        """Run continuous scanning (live mode only)"""
        if self.mode != 'live':
            self.logger.error("Continuous mode only available in live mode")
            return
        
        import subprocess
        
        # Prevent Ubuntu from sleeping while script runs
        inhibit_cmd = [
            'systemd-inhibit',
            '--what=idle:sleep',
            '--who=TradingScanner',
            '--why=Continuous market scanning',
            '--mode=block',
            'sleep', 'infinity'
        ]
        
        inhibit_process = None
        try:
            inhibit_process = subprocess.Popen(inhibit_cmd)
            self.logger.info("🛡️ System sleep/suspend inhibited while scanner runs")
            print("🛡️ Ubuntu sleep/suspend disabled while scanner is active")
        except Exception as e:
            self.logger.warning(f"Failed to inhibit system sleep: {e}")
            print(f"⚠️ Note: Ubuntu may still auto-sleep. Error: {e}")
        
        try:
            self.logger.info(f"Starting continuous scanning every {interval_minutes} minutes")
            print(f"📡 Starting continuous scanning every {interval_minutes} minutes")
            print("💤 System will NOT sleep while scanner is running")
            print("🛑 Press Ctrl+C to stop scanner and restore normal sleep behavior")
            
            while True:
                # Run single scan
                scan_success = await self.run_single_scan()
                
                # Calculate sleep time
                if scan_success:
                    sleep_seconds = interval_minutes * 60
                else:
                    # Retry sooner if scan failed
                    sleep_seconds = 60
                
                self.logger.info(f"Next scan in {sleep_seconds//60} minutes...")
                time.sleep(sleep_seconds)
                
        except KeyboardInterrupt:
            self.logger.info("Scanning stopped by user")
            print("\n🔄 Scanner stopped by user")
        except Exception as e:
            self.logger.error(f"Continuous scanning failed: {e}")
            print(f"\n❌ Scanner failed: {e}")
        finally:
            # Kill inhibit process when done
            if inhibit_process:
                inhibit_process.terminate()
                inhibit_process.wait()
                self.logger.info("System sleep inhibition removed")
                print("✅ System sleep/suspend behavior restored to normal")

async def main_async():
    """Async main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Trading Setup Scanner Controller")
    parser.add_argument('--mode', choices=['live', 'backtest'], default='backtest',
                       help='Operation mode: live or backtest (default: backtest)')
    parser.add_argument('--days', type=int, default=30,
                       help='Days to backtest (default: 30)')
    parser.add_argument('--single-scan', action='store_true',
                       help='Run a single scan instead of continuous')
    
    args = parser.parse_args()
    
    # Create and run controller
    controller = MainController(mode=args.mode)
    
    # Load configuration
    if not controller.load_configuration():
        print("Failed to load configuration. Exiting.")
        sys.exit(1)
    
    # Run in appropriate mode
    if args.mode == 'backtest':
        await controller.run_backtest(days=args.days)
    elif args.single_scan:
        await controller.run_single_scan()
    else:
        await controller.run_continuous(interval_minutes=1)


def main():
    """Main entry point - wraps async function"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()