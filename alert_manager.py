"""
Alert Manager - Handles all alert notifications
Sends alerts via Telegram and other channels
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import csv
import os


class AlertManager:
    """Manages sending alerts for trading setups"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.telegram_bot = None
        self.telegram_chat_id = None
        self.config = None
        self.alert_history = []
        self.max_history_size = 1000
        
        # Alert cooldown tracking (symbol -> last alert time)
        self.cooldown_tracker = {}
        self.cooldown_minutes = 5
        
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize alert manager with configuration
        
        Args:
            config: Global configuration dictionary
            
        Returns:
            bool: True if initialized successfully
        """
        try:
            self.config = config
            
            # Initialize Telegram bot if configured
            telegram_config = config.get('telegram', {})
            self.telegram_chat_id = telegram_config.get('chat_id')
            bot_token = telegram_config.get('bot_token')
            
            if bot_token and self.telegram_chat_id:
                self._initialize_telegram_bot(bot_token)
                self.logger.info("Telegram bot initialized")
            else:
                self.logger.warning("Telegram not configured or missing credentials")
            
            # Create logs directory if it doesn't exist
            os.makedirs('logs', exist_ok=True)
            
            self.logger.info("Alert Manager initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Alert Manager: {e}")
            return False
    
    def _initialize_telegram_bot(self, bot_token: str) -> None:
        """Initialize Telegram bot with error handling"""
        try:
            # Lazy import to avoid dependency if not using Telegram
            from telegram import Bot
            self.telegram_bot = Bot(token=bot_token)
        except ImportError:
            self.logger.error("python-telegram-bot not installed. Install with: pip install python-telegram-bot")
            self.telegram_bot = None
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
            self.telegram_bot = None
    
    def check_cooldown(self, symbol: str, setup_name: str) -> bool:
        """
        Check if we should send alert (cooldown period)
        
        Args:
            symbol: Trading symbol
            setup_name: Name of the setup
            
        Returns:
            bool: True if alert should be sent (not in cooldown)
        """
        key = f"{symbol}_{setup_name}"
        current_time = datetime.now()
        
        if key in self.cooldown_tracker:
            last_alert_time = self.cooldown_tracker[key]
            time_diff = (current_time - last_alert_time).total_seconds() / 60
            
            if time_diff < self.cooldown_minutes:
                self.logger.debug(f"Alert cooldown active for {key}: {self.cooldown_minutes - time_diff:.1f} minutes remaining")
                return False
        
        return True
    
    def update_cooldown(self, symbol: str, setup_name: str) -> None:
        """
        Update cooldown tracker after sending alert
        
        Args:
            symbol: Trading symbol
            setup_name: Name of the setup
        """
        key = f"{symbol}_{setup_name}"
        self.cooldown_tracker[key] = datetime.now()
    
    async def send_setup_alert(self, setup_result: Dict[str, Any]) -> bool:
        """
        Send alert for a trading setup
        
        Args:
            setup_result: Setup analysis result dictionary
            
        Returns:
            bool: True if alert sent successfully
        """
        try:
            symbol = setup_result.get('symbol')
            setup_name = setup_result.get('setup_name')
            
            if not symbol or not setup_name:
                self.logger.error("Missing symbol or setup_name in setup result")
                return False
            
            # Check cooldown
            if not self.check_cooldown(symbol, setup_name):
                self.logger.debug(f"Skipping alert for {symbol}_{setup_name} (cooldown)")
                return False
            
            # Create alert message
            alert_message = self._create_alert_message(setup_result)
            
            # Log alert to file
            log_success = self._log_alert_to_file(setup_result, alert_message)
            
            # Send via Telegram
            telegram_success = await self._send_telegram_alert(alert_message)
            
            # Send via console
            self._send_console_alert(alert_message, setup_result)
            
            # Update cooldown if any alert method succeeded
            if telegram_success or log_success:
                self.update_cooldown(symbol, setup_name)
                self._add_to_history(setup_result)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error sending setup alert: {e}")
            return False
    
    def _create_alert_message(self, setup_result: Dict[str, Any]) -> str:
        """
        Create formatted alert message from setup result
        
        Args:
            setup_result: Setup analysis result
            
        Returns:
            str: Formatted alert message
        """
        # Extract data from setup result
        symbol = setup_result.get('symbol', 'Unknown')
        setup_name = setup_result.get('setup_name', 'Unknown')
        signal_type = setup_result.get('signal_type', 'Unknown')
        confidence = setup_result.get('confidence', 0)
        pattern = setup_result.get('pattern_name', 'Unknown')
        
        # Get price info
        current_price = setup_result.get('current_price', 0)
        entry_price = setup_result.get('entry_price', current_price)
        target_price = setup_result.get('target_price')
        stop_price = setup_result.get('stop_price')
        
        # Get timing info
        timestamp = setup_result.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            alert_time = timestamp
        else:
            alert_time = timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp)
        
        # Get additional info
        rsi = setup_result.get('rsi', 'N/A')
        support_resistance = setup_result.get('support_resistance_level', 'N/A')
        level_type = setup_result.get('level_type', 'N/A')
        
        # Create message based on template from config
        template = self.config.get('alert', {}).get('template', None)
        
        if template:
            # Use custom template
            message = template.format(
                pair=symbol,
                signal=signal_type,
                time=alert_time,
                pattern=pattern,
                rsi=rsi,
                ema_status='N/A',
                win_rate=confidence
            )
        else:
            # Default template
            message = f"🔔 TRADING SETUP ALERT\n"
            message += f"📊 {symbol} | {setup_name}\n"
            message += f"📈 Signal: {signal_type}\n"
            message += f"🎯 Pattern: {pattern}\n"
            message += f"📊 Confidence: {confidence}%\n"
            message += f"💰 Current: {current_price:.5f}"
            
            if entry_price != current_price:
                message += f" | Entry: {entry_price:.5f}"
            
            if target_price:
                message += f"\n🎯 Target: {target_price:.5f}"
            
            if stop_price:
                message += f" | ⛔ Stop: {stop_price:.5f}"
            
            message += f"\n📊 RSI: {rsi}"
            
            if support_resistance != 'N/A':
                message += f"\n📍 {level_type}: {support_resistance:.5f}"
            
            message += f"\n⏰ Alert Time: {alert_time} UTC"
            
            # Add risk info if available
            risk_reward = setup_result.get('risk_reward_ratio')
            if risk_reward:
                message += f"\n⚖️ Risk/Reward: 1:{risk_reward:.2f}"
        
        return message
    
    async def _send_telegram_alert(self, message: str) -> bool:
        """
        Send alert via Telegram
        
        Args:
            message: Alert message to send
            
        Returns:
            bool: True if sent successfully
        """
        if not self.telegram_bot or not self.telegram_chat_id:
            self.logger.debug("Telegram not configured, skipping")
            return False
        
        try:
            # Split long messages if needed
            if len(message) > 4000:
                # Split by lines
                lines = message.split('\n')
                chunks = []
                current_chunk = ""
                
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > 4000:
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += "\n" + line if current_chunk else line
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Send all chunks
                for chunk in chunks:
                    await self.telegram_bot.send_message(
                        chat_id=self.telegram_chat_id,
                        text=chunk,
                        parse_mode=None  # Use None for plain text
                    )
                
                self.logger.debug("Sent Telegram alert (multiple messages)")
            else:
                # Send single message
                await self.telegram_bot.send_message(
                    chat_id=self.telegram_chat_id,
                    text=message,
                    parse_mode=None
                )
                self.logger.debug("Sent Telegram alert")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Telegram alert: {e}")
            return False
    
    def _send_console_alert(self, message: str, setup_result: Dict[str, Any]) -> None:
        """
        Print alert to console with formatting
        
        Args:
            message: Alert message
            setup_result: Setup result for additional info
        """
        signal_type = setup_result.get('signal_type', '').upper()
        
        # Color coding based on signal type
        if signal_type == 'CALL' or signal_type == 'BUY':
            color_code = '\033[92m'  # Green
        elif signal_type == 'PUT' or signal_type == 'SELL':
            color_code = '\033[91m'  # Red
        else:
            color_code = '\033[93m'  # Yellow
        
        reset_code = '\033[0m'
        
        print(f"\n{'='*60}")
        print(f"{color_code}🚨 LIVE TRADING ALERT{reset_code}")
        print(f"{'='*60}")
        print(message)
        print(f"{'='*60}\n")
    
    def _log_alert_to_file(self, setup_result: Dict[str, Any], message: str) -> bool:
        """
        Log alert to CSV file
        
        Args:
            setup_result: Setup analysis result
            message: Alert message
            
        Returns:
            bool: True if logged successfully
        """
        try:
            symbol = setup_result.get('symbol', 'unknown')
            log_file = f"logs/{symbol}_alerts.csv"
            
            # Prepare log entry
            timestamp = datetime.now()
            log_entry = {
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'date': timestamp.strftime('%Y-%m-%d'),
                'time': timestamp.strftime('%H:%M:%S'),
                'symbol': symbol,
                'setup_name': setup_result.get('setup_name', 'unknown'),
                'signal_type': setup_result.get('signal_type', 'unknown'),
                'pattern': setup_result.get('pattern_name', 'unknown'),
                'confidence': setup_result.get('confidence', 0),
                'price': setup_result.get('current_price', 0),
                'rsi': setup_result.get('rsi', 'N/A'),
                'message': message.replace('\n', ' | ')
            }
            
            # Write to CSV
            file_exists = os.path.isfile(log_file)
            
            with open(log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=log_entry.keys())
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(log_entry)
            
            self.logger.debug(f"Logged alert to {log_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to log alert to file: {e}")
            return False
    
    def _add_to_history(self, setup_result: Dict[str, Any]) -> None:
        """
        Add alert to in-memory history
        
        Args:
            setup_result: Setup analysis result
        """
        history_entry = {
            'timestamp': datetime.now(),
            'result': setup_result.copy()
        }
        
        self.alert_history.append(history_entry)
        
        # Keep history size limited
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]
    
    def get_recent_alerts(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent alerts from history
        
        Args:
            count: Number of recent alerts to return
            
        Returns:
            List[Dict[str, Any]]: List of recent alerts
        """
        return self.alert_history[-count:] if self.alert_history else []
    
    async def send_backtest_report(self, report: Dict[str, Any]) -> bool:
        """
        Send backtest report via Telegram
        
        Args:
            report: Backtest report dictionary
            
        Returns:
            bool: True if sent successfully
        """
        if not self.telegram_bot or not self.telegram_chat_id:
            self.logger.debug("Telegram not configured, skipping backtest report")
            return False
        
        try:
            # Create summary message
            metadata = report.get('metadata', {})
            exec_summary = report.get('executive_summary', {}).get('overview', {})
            
            message = f"📊 BACKTEST REPORT - {metadata.get('report_name', 'Unknown')}\n"
            message += f"📅 Period: {exec_summary.get('period', 'Unknown')}\n"
            message += f"📈 Total Trades: {exec_summary.get('total_trades', 0)}\n"
            message += f"🏆 Win Rate: {exec_summary.get('win_rate', '0%')}\n"
            message += f"💰 Net Profit: {exec_summary.get('net_profit', '$0.00')}\n"
            message += f"📊 Profit Factor: {exec_summary.get('profit_factor', '0.00')}\n"
            message += f"📉 Max Drawdown: {exec_summary.get('max_drawdown', '0.00%')}\n"
            
            # Add setup performance if available
            setup_analysis = report.get('setup_analysis', {})
            setup_perf = setup_analysis.get('setup_performance', {})
            
            if setup_perf:
                message += f"\n📋 Top Setup Performance:\n"
                # Get top 3 setups
                top_setups = list(setup_perf.items())[:3]
                for setup_name, perf in top_setups:
                    trades = perf.get('trades', 0)
                    win_rate = perf.get('win_rate', 0)
                    if trades > 0:
                        message += f"• {setup_name}: {win_rate:.1f}% ({trades} trades)\n"
            
            # Send via Telegram
            await self.telegram_bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message
            )
            
            self.logger.info("Sent backtest report via Telegram")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send backtest report: {e}")
            return False
    
    async def send_error_alert(self, error_message: str, context: str = "") -> bool:
        """
        Send error alert
        
        Args:
            error_message: Error description
            context: Additional context information
            
        Returns:
            bool: True if sent successfully
        """
        try:
            message = f"🚨 SYSTEM ERROR\n"
            message += f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"📝 Context: {context}\n"
            message += f"❌ Error: {error_message}\n"
            
            # Log to console
            print(f"\n{'='*60}")
            print("🚨 SYSTEM ERROR")
            print(f"{'='*60}")
            print(message)
            print(f"{'='*60}\n")
            
            # Send via Telegram if configured
            if self.telegram_bot and self.telegram_chat_id:
                await self.telegram_bot.send_message(
                    chat_id=self.telegram_chat_id,
                    text=message
                )
            
            # Log to error file
            error_log = "logs/errors.log"
            with open(error_log, 'a') as f:
                f.write(f"{datetime.now().isoformat()} | {context} | {error_message}\n")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send error alert: {e}")
            return False
    
    def clear_cooldowns(self) -> None:
        """Clear all cooldown timers"""
        self.cooldown_tracker.clear()
        self.logger.debug("Cleared all alert cooldowns")
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """
        Get alert statistics
        
        Returns:
            Dict[str, Any]: Alert statistics
        """
        return {
            'total_alerts_sent': len(self.alert_history),
            'active_cooldowns': len(self.cooldown_tracker),
            'telegram_configured': self.telegram_bot is not None
        }