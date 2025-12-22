"""
web_controller.py - Standalone Flask web scanner for realFx1h
Independent implementation that avoids circular imports
"""

import os
import sys
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Flask
from flask import Flask, render_template_string, jsonify

# Initialize Flask app FIRST
app = Flask(__name__)

# Import individual components (NOT MainController)
try:
    from data_fetcher import DataFetcher
    from setup_loader import SetupLoader
    from alert_manager import AlertManager
    from result_aggregator import ResultAggregator
    from utils.logger import setup_logger
    COMPONENTS_LOADED = True
except ImportError as e:
    print(f"[WEB] Failed to import components: {e}")
    COMPONENTS_LOADED = False


class WebScanner:
    """Standalone web scanner - mirrors MainController single scan functionality"""
    
    def __init__(self, mode: str = 'live'):
        """
        Initialize the web scanner
        
        Args:
            mode: 'live' for real-time scanning
        """
        self.mode = mode
        self.logger = setup_logger('web_scanner')
        
        # Initialize components directly
        self.data_fetcher = DataFetcher()
        self.setup_loader = SetupLoader()
        self.alert_manager = AlertManager()
        self.result_aggregator = ResultAggregator()
        
        # State tracking
        self.active_setups = []
        self.last_scan_time = None
        self.scan_count = 0
        
        self.logger.info(f"Web Scanner initialized in {mode} mode")
        
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
        
        # Print results to console (this output will be captured)
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
        self.logger.info("send_alerts method called - starting alert process")  # New: Confirm method entry
        
        significant_results = results.get('significant', [])
        
        if not significant_results:
            self.logger.debug("No significant results to alert")
            # Send test message when no results
            self.logger.info("No significant results - attempting to send test alert")  # New: Log attempt start
            try:
                # Direct Telegram test message
                test_message = "TEST: Single scan working! No trading setups found in this scan."
                self.logger.debug(f"Test message content: {test_message}")  # New: Log message for visibility
                telegram_sent = await self.alert_manager._send_telegram_alert(test_message)
                if telegram_sent:
                    self.logger.info("Test alert sent successfully")  # Updated: More specific success log
                else:
                    self.logger.warning("Test alert send returned False - check alert_manager._send_telegram_alert")  # Updated: Log failure with hint
            except Exception as e:
                self.logger.error(f"Test alert attempt failed with exception: {e}")  # Updated: More context
            return
        
        self.logger.info(f"Found {len(significant_results)} significant results - starting alert sends")  # New: Log before looping
        try:
            success_count = 0
            for i, result in enumerate(significant_results, start=1):
                self.logger.info(f"Attempting alert send {i}/{len(significant_results)} for result: {result.get('symbol', 'unknown')}")  # New: Log each attempt start with index and key detail
                alert_sent = await self.alert_manager.send_setup_alert(result)
                if alert_sent:
                    success_count += 1
                    self.logger.info(f"Alert send {i} succeeded")  # New: Log success per attempt
                else:
                    self.logger.warning(f"Alert send {i} returned False - check alert_manager.send_setup_alert for result: {result}")  # New: Log failure per attempt with result details
            
            self.logger.info(f"Alert sending complete: {success_count}/{len(significant_results)} succeeded")  # Updated: More context
            
        except Exception as e:
            self.logger.error(f"Alert sending loop failed with exception: {e}")  # Updated: More context


    async def run_single_scan(self) -> bool:
        """Run a single scanning cycle - main method for web interface"""
        try:
            self.scan_count += 1
            self.last_scan_time = datetime.utcnow()
            
            self.logger.info(f"Starting web scan #{self.scan_count}")
            
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
            

            self.logger.info(f"Web scan #{self.scan_count} completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Web scan #{self.scan_count} failed: {e}")
            return False


# Global scanner instance (initialized on first use)
scanner = None

def get_scanner():
    """Get or create the WebScanner instance"""
    global scanner
    if scanner is None:
        print("[WEB] Initializing WebScanner...")
        scanner = WebScanner(mode='live')
        
        # Load configuration
        if not scanner.load_configuration():
            raise RuntimeError("Failed to load configuration")
        
        print(f"[WEB] Scanner ready. Loaded setups")
    
    return scanner

def run_scan_and_capture():
    """
    Run scan and capture ALL console output including print() statements
    Returns: (success: bool, output: str)
    """
    import io
    import sys
    
    # Check if components are loaded
    if not COMPONENTS_LOADED:
        return False, "ERROR: Failed to import required components. Check server logs."
    
    # Get scanner
    try:
        scanner = get_scanner()
    except Exception as e:
        return False, f"ERROR: Failed to initialize scanner: {str(e)}"
    
    # Redirect stdout to capture print() statements
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    
    try:
        # Create new event loop for this scan
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the scan - this will print to our buffer
        print(f"\n{'='*60}")
        print(f"WEB SCAN STARTED - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"{'='*60}\n")
        
        success = loop.run_until_complete(scanner.run_single_scan())
        
        print(f"\n{'='*60}")
        print(f"WEB SCAN COMPLETED - {'SUCCESS' if success else 'FAILED'}")
        print(f"{'='*60}")
        
        # Get captured output
        output = buffer.getvalue()
        
        # If no output was captured, show a message
        if not output.strip() or "No setups detected" in output:
            output += "\n📭 No trading signals detected in this scan."
        
        loop.close()
        return success, output
        
    except Exception as e:
        # Capture the error in output
        error_msg = f"\n❌ SCAN ERROR: {str(e)}\n"
        print(error_msg)
        output = buffer.getvalue() + error_msg
        return False, output
        
    finally:
        # Always restore stdout
        sys.stdout = old_stdout

# HTML Template for dashboard (same as before)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Forex Scanner Web</title>
    <meta http-equiv="refresh" content="60"> <!-- Refresh every 1 minute -->
    <style>
        body { 
            font-family: 'Courier New', monospace; 
            background: #0a0a0a; 
            color: #00ff00; 
            margin: 0;
            padding: 20px;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto;
            background: #111111;
            border: 1px solid #333;
            border-radius: 5px;
            overflow: hidden;
        }
        .header { 
            background: #1a1a1a; 
            padding: 20px; 
            border-bottom: 2px solid #00ff00;
            text-align: center;
        }
        .header h1 { 
            margin: 0; 
            color: #00ff00;
            font-size: 24px;
        }
        .header p { 
            margin: 5px 0 0 0; 
            color: #66ff66;
            font-size: 14px;
        }
        .scan-info { 
            margin: 0;
            padding: 20px;
            min-height: 400px;
        }
        .status { 
            padding: 10px 15px; 
            margin-bottom: 20px;
            border-radius: 4px; 
            font-weight: bold;
        }
        .status-success { 
            background: #002200; 
            color: #00ff00; 
            border-left: 5px solid #00ff00;
        }
        .status-error { 
            background: #220000; 
            color: #ff6666; 
            border-left: 5px solid #ff0000;
        }
        .output-box {
            background: #000000;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 15px;
            margin-top: 15px;
            overflow-x: auto;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.4;
            max-height: 600px;
            overflow-y: auto;
        }
        .timestamp { 
            background: #1a1a1a; 
            padding: 15px; 
            color: #888; 
            font-size: 12px;
            border-top: 1px solid #333;
            display: flex;
            justify-content: space-between;
        }
        .refresh-notice {
            background: #001a00;
            padding: 10px;
            margin: 15px 0;
            border-left: 3px solid #00ff00;
            font-size: 13px;
        }
        .symbols {
            display: inline-block;
            background: #003300;
            padding: 3px 8px;
            border-radius: 3px;
            margin-left: 10px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚡ FOREX SCANNER - REALFX1H WEB MODE</h1>
            <p>
                📡 Live Market Scanning | 🔄 Auto-refresh: 60s | 
                🕒 Mode: Single Scan | 
                <span class="symbols">EURUSD GBPUSD USDJPY</span>
            </p>
        </div>
        
        <div class="refresh-notice">
            ⚡ Page auto-refreshes every 60 seconds to trigger a new market scan.
            Keep this tab open for continuous operation.
        </div>
        
        <div class="scan-info">
            <h3 style="margin-top: 0; color: #66ff66;">📊 LATEST SCAN RESULTS</h3>
            
            <div class="status status-{{ status_class }}">
                {% if status_class == 'success' %}
                    ✅ {{ status_message }}
                {% else %}
                    ❌ {{ status_message }}
                {% endif %}
            </div>
            
            <div class="output-box">
{{ scan_output }}
            </div>
        </div>
        
        <div class="timestamp">
            <div>
                <strong>🕒 Scan Time:</strong> {{ scan_time }} UTC
            </div>
            <div>
                <strong>⏱️ Next Scan:</strong> In 60 seconds (auto-refresh)
            </div>
        </div>
    </div>
    
    <script>
        // Auto-scroll to bottom of output on page load
        window.onload = function() {
            var outputBox = document.querySelector('.output-box');
            if (outputBox) {
                outputBox.scrollTop = outputBox.scrollHeight;
            }
            
            // Show countdown timer
            var timeLeft = 60;
            var timerElement = document.querySelector('.timestamp div:last-child');
            
            var countdown = setInterval(function() {
                timeLeft--;
                if (timerElement) {
                    timerElement.innerHTML = '<strong>⏱️ Next Scan:</strong> In ' + timeLeft + ' seconds';
                }
                if (timeLeft <= 0) {
                    clearInterval(countdown);
                }
            }, 1000);
        };
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    """Main dashboard - runs single scan and shows results"""
    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Run scan AND capture all console output
        success, scan_output = run_scan_and_capture()
        
        if success:
            status = "Scan completed successfully"
            status_class = "success"
        else:
            status = "Scan encountered issues - check details below"
            status_class = "error"
            
    except Exception as e:
        status = f"System error: {str(e)}"
        status_class = "error"
        scan_output = f"CRITICAL ERROR:\n{str(e)}\n\nPlease check server logs."
    
    return render_template_string(
        HTML_TEMPLATE,
        status_message=status,
        status_class=status_class,
        scan_output=scan_output,
        scan_time=scan_time
    )

@app.route('/api/scan')
def api_scan():
    """JSON API endpoint - returns scan results for programmatic use"""
    try:
        success, output = run_scan_and_capture()
        
        # Extract just the signal lines from output
        signals = []
        lines = output.split('\n')
        for line in lines:
            if '•' in line or 'SIGNAL' in line.upper() or 'BUY' in line.upper() or 'SELL' in line.upper():
                signals.append(line.strip())
        
        return jsonify({
            "success": success,
            "status": "Scan completed" if success else "Scan failed",
            "output": output,
            "signals": signals,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "online",
        "service": "realFx1h Web Scanner",
        "mode": "single_scan",
        "interval": "60s",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/control/stop')
def stop_scan():
    """Emergency stop endpoint (doesn't actually stop, just shows message)"""
    return jsonify({
        "status": "info",
        "message": "Web scanner runs per request. Close browser tab to stop.",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("[WEB] Starting Forex Scanner Web Controller...")
    print("[WEB] =========================================")
    print("[WEB] Dashboard: http://localhost:5000")
    print("[WEB] API Endpoint: http://localhost:5000/api/scan")
    print("[WEB] Health Check: http://localhost:5000/health")
    print("[WEB] Auto-refresh: 60 seconds")
    print("[WEB] =========================================")
    print("[WEB] Keep this tab open in browser for continuous scanning")
    print("[WEB] Each page refresh will trigger a new market scan")
    print("[WEB] =========================================")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)