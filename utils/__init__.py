"""
Utils Package - Utility modules for Trading Setup Scanner
"""

__version__ = "1.0.0"
__author__ = "Trading Setup Scanner"
__description__ = "Utility functions for data processing and logging"

# Import key utilities for easy access

# TO:
from .data_processor import DataProcessor

# Then create standalone function aliases:
validate_dataframe = DataProcessor.validate_dataframe
clean_ohlc_data = DataProcessor.clean_ohlc_data
calculate_returns = DataProcessor.calculate_returns
resample_data = DataProcessor.resample_data
detect_gaps = DataProcessor.detect_gaps
remove_outliers = DataProcessor.remove_outliers


from .logger import (
    setup_logger,
    get_logger,
    log_performance,
    log_exception,
    ConsoleFormatter,
    FileFormatter
)

# Define what gets imported with "from utils import *"
__all__ = [
    # Data Processor
    'DataProcessor',
    'validate_dataframe',
    'clean_ohlc_data',
    'calculate_returns',
    'resample_data',
    'detect_gaps',
    'remove_outliers',
    
    # Logger
    'setup_logger',
    'get_logger',
    'log_performance',
    'log_exception',
    'ConsoleFormatter',
    'FileFormatter'
]