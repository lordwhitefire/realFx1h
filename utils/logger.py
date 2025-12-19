"""
Logger - Centralized logging system for Trading Setup Scanner
Handles all logging across the application with proper formatting and rotation
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional, Dict, Any
from datetime import datetime
import traceback


class ConsoleFormatter(logging.Formatter):
    """Custom formatter for console output with colors"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[41m',  # Red background
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = (f"{self.COLORS[record.levelname]}"
                              f"{record.levelname}"
                              f"{self.COLORS['RESET']}")
        
        # Format the message
        return super().format(record)


class FileFormatter(logging.Formatter):
    """Custom formatter for file output (no colors)"""
    
    def format(self, record):
        # Remove any ANSI color codes from the message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            import re
            record.msg = re.sub(r'\033\[[0-9;]*m', '', record.msg)
        
        return super().format(record)


class TradingLogger:
    """Main logger class for the trading system"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TradingLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.loggers = {}
        self.handlers = {}
        self.log_directory = "logs"
        
        # Create log directory if it doesn't exist
        os.makedirs(self.log_directory, exist_ok=True)
        
        self._initialized = True
    
    def setup_logger(self, 
                    name: str, 
                    level: str = "INFO",
                    log_to_console: bool = True,
                    log_to_file: bool = True,
                    max_file_size_mb: int = 10,
                    backup_count: int = 5) -> logging.Logger:
        """
        Setup a logger with console and file handlers
        
        Args:
            name: Logger name (e.g., 'controller', 'setup1', 'data')
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_console: Whether to log to console
            log_to_file: Whether to log to file
            max_file_size_mb: Maximum log file size in MB
            backup_count: Number of backup files to keep
            
        Returns:
            logging.Logger: Configured logger instance
        """
        # If logger already exists, return it
        if name in self.loggers:
            return self.loggers[name]
        
        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # Create formatters
        console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        file_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        console_formatter = ConsoleFormatter(console_format, datefmt='%H:%M:%S')
        file_formatter = FileFormatter(file_format, datefmt='%Y-%m-%d %H:%M:%S')
        
        # Console handler
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            self.handlers[f"{name}_console"] = console_handler
        
        # File handler
        if log_to_file:
            log_file = os.path.join(self.log_directory, f"{name}.log")
            
            # Use RotatingFileHandler for log rotation
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
                backupCount=backup_count,
                encoding='utf-8'
            )
            
            file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            self.handlers[f"{name}_file"] = file_handler
        
        # Store logger
        self.loggers[name] = logger
        
        return logger
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get an existing logger or create a new one with default settings
        
        Args:
            name: Logger name
            
        Returns:
            logging.Logger: Logger instance
        """
        if name in self.loggers:
            return self.loggers[name]
        
        # Create with default settings if it doesn't exist
        return self.setup_logger(name)
    
    def set_level(self, name: str, level: str) -> None:
        """
        Set logging level for a logger
        
        Args:
            name: Logger name
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if name in self.loggers:
            self.loggers[name].setLevel(getattr(logging, level.upper(), logging.INFO))
            
            # Update all handlers
            for handler in self.loggers[name].handlers:
                handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    def log_performance(self, 
                       operation: str, 
                       start_time: datetime,
                       end_time: datetime = None,
                       details: Dict[str, Any] = None,
                       logger_name: str = "performance") -> None:
        """
        Log performance metrics for an operation
        
        Args:
            operation: Name of the operation
            start_time: Operation start time
            end_time: Operation end time (defaults to now)
            details: Additional performance details
            logger_name: Logger to use
        """
        if end_time is None:
            end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        logger = self.get_logger(logger_name)
        
        log_msg = f"PERFORMANCE - {operation}: {duration:.3f}s"
        
        if details:
            detail_str = " | ".join([f"{k}: {v}" for k, v in details.items()])
            log_msg += f" | {detail_str}"
        
        logger.info(log_msg)
    
    def log_exception(self, 
                     exception: Exception, 
                     context: str = "",
                     logger_name: str = "error") -> None:
        """
        Log an exception with full traceback
        
        Args:
            exception: Exception object
            context: Additional context about where the error occurred
            logger_name: Logger to use
        """
        logger = self.get_logger(logger_name)
        
        # Get full traceback
        exc_info = sys.exc_info()
        tb_str = "".join(traceback.format_exception(*exc_info))
        
        log_msg = f"EXCEPTION - {type(exception).__name__}: {str(exception)}"
        if context:
            log_msg += f" | Context: {context}"
        
        logger.error(log_msg)
        logger.debug(f"Traceback:\n{tb_str}")
    
    def log_trade_signal(self,
                        symbol: str,
                        setup_name: str,
                        signal_type: str,
                        confidence: float,
                        price: float,
                        logger_name: str = "trading") -> None:
        """
        Log a trading signal
        
        Args:
            symbol: Trading symbol
            setup_name: Name of the setup that generated the signal
            signal_type: Type of signal (CALL/PUT, BUY/SELL)
            confidence: Confidence level (0-100)
            price: Current price
            logger_name: Logger to use
        """
        logger = self.get_logger(logger_name)
        
        log_msg = (f"TRADE SIGNAL - {symbol} | {setup_name} | "
                  f"{signal_type} | Confidence: {confidence:.1f}% | "
                  f"Price: {price:.5f}")
        
        logger.info(log_msg)
    
    def log_backtest_result(self,
                           setup_name: str,
                           total_trades: int,
                           win_rate: float,
                           total_pnl: float,
                           logger_name: str = "backtest") -> None:
        """
        Log backtest results
        
        Args:
            setup_name: Name of the setup
            total_trades: Total number of trades
            win_rate: Win rate percentage
            total_pnl: Total profit/loss
            logger_name: Logger to use
        """
        logger = self.get_logger(logger_name)
        
        log_msg = (f"BACKTEST RESULT - {setup_name} | "
                  f"Trades: {total_trades} | "
                  f"Win Rate: {win_rate:.1f}% | "
                  f"P&L: ${total_pnl:.2f}")
        
        logger.info(log_msg)
    
    def log_alert(self,
                 symbol: str,
                 alert_type: str,
                 message: str,
                 priority: str = "INFO",
                 logger_name: str = "alerts") -> None:
        """
        Log an alert
        
        Args:
            symbol: Trading symbol
            alert_type: Type of alert (SETUP, ERROR, SYSTEM, etc.)
            message: Alert message
            priority: Alert priority (INFO, WARNING, ERROR)
            logger_name: Logger to use
        """
        logger = self.get_logger(logger_name)
        
        log_msg = f"ALERT - {symbol} | {alert_type} | {message}"
        
        log_method = getattr(logger, priority.lower(), logger.info)
        log_method(log_msg)
    
    def log_data_quality(self,
                        symbol: str,
                        data_points: int,
                        missing_values: int,
                        time_range_days: float,
                        logger_name: str = "data") -> None:
        """
        Log data quality metrics
        
        Args:
            symbol: Trading symbol
            data_points: Number of data points
            missing_values: Number of missing values
            time_range_days: Time range in days
            logger_name: Logger to use
        """
        logger = self.get_logger(logger_name)
        
        completeness = ((data_points - missing_values) / data_points * 100 
                       if data_points > 0 else 0)
        
        log_msg = (f"DATA QUALITY - {symbol} | "
                  f"Points: {data_points} | "
                  f"Missing: {missing_values} | "
                  f"Completeness: {completeness:.1f}% | "
                  f"Range: {time_range_days:.1f} days")
        
        logger.info(log_msg)
    
    def create_daily_log_file(self, prefix: str = "") -> str:
        """
        Create a new log file with today's date
        
        Args:
            prefix: Prefix for the log file name
            
        Returns:
            str: Path to the new log file
        """
        today = datetime.now().strftime("%Y%m%d")
        
        if prefix:
            filename = f"{prefix}_{today}.log"
        else:
            filename = f"{today}.log"
        
        log_path = os.path.join(self.log_directory, filename)
        
        # Touch the file to create it
        with open(log_path, 'a'):
            os.utime(log_path, None)
        
        return log_path
    
    def rotate_logs(self) -> None:
        """Manually trigger log rotation for all file handlers"""
        for handler_name, handler in self.handlers.items():
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.doRollover()
        
        # Log the rotation
        main_logger = self.get_logger("system")
        main_logger.info("Manual log rotation performed")
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about logging system
        
        Returns:
            Dict[str, Any]: Logging statistics
        """
        stats = {
            'total_loggers': len(self.loggers),
            'total_handlers': len(self.handlers),
            'loggers': list(self.loggers.keys()),
            'log_directory': self.log_directory,
            'log_files': []
        }
        
        # Get information about log files
        if os.path.exists(self.log_directory):
            log_files = os.listdir(self.log_directory)
            stats['log_files'] = log_files
            
            # Calculate total size of log files
            total_size = 0
            for log_file in log_files:
                file_path = os.path.join(self.log_directory, log_file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
            
            stats['total_log_size_mb'] = total_size / 1024 / 1024
        
        return stats
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """
        Clean up log files older than specified days
        
        Args:
            days_to_keep: Number of days to keep logs
            
        Returns:
            int: Number of files deleted
        """
        if not os.path.exists(self.log_directory):
            return 0
        
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        
        for filename in os.listdir(self.log_directory):
            file_path = os.path.join(self.log_directory, filename)
            
            if os.path.isfile(file_path):
                file_time = os.path.getmtime(file_path)
                
                if file_time < cutoff_time:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        self.log_exception(e, f"Failed to delete {filename}")
        
        if deleted_count > 0:
            main_logger = self.get_logger("system")
            main_logger.info(f"Cleaned up {deleted_count} old log files "
                           f"(older than {days_to_keep} days)")
        
        return deleted_count


# Global instance
_logger_instance = None


def setup_logger(name: str, **kwargs) -> logging.Logger:
    """
    Convenience function to setup a logger
    
    Args:
        name: Logger name
        **kwargs: Additional arguments for setup_logger
        
    Returns:
        logging.Logger: Configured logger
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger()
    
    return _logger_instance.setup_logger(name, **kwargs)


def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a logger
    
    Args:
        name: Logger name
        
    Returns:
        logging.Logger: Logger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger()
    
    return _logger_instance.get_logger(name)


def log_performance(operation: str, start_time: datetime, **kwargs) -> None:
    """
    Convenience function to log performance
    
    Args:
        operation: Name of the operation
        start_time: Operation start time
        **kwargs: Additional arguments for log_performance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger()
    
    _logger_instance.log_performance(operation, start_time, **kwargs)


def log_exception(exception: Exception, **kwargs) -> None:
    """
    Convenience function to log an exception
    
    Args:
        exception: Exception object
        **kwargs: Additional arguments for log_exception
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger()
    
    _logger_instance.log_exception(exception, **kwargs)


# Example usage
if __name__ == "__main__":
    # Setup main logger
    logger = setup_logger("main", level="DEBUG")
    
    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Test performance logging
    import time
    start = datetime.now()
    time.sleep(0.1)
    log_performance("Test operation", start, details={"iterations": 100})
    
    # Test exception logging
    try:
        raise ValueError("Test exception")
    except ValueError as e:
        log_exception(e, context="Testing exception logging")
    
    # Get statistics
    stats = _logger_instance.get_log_statistics()
    print(f"Log statistics: {stats}")