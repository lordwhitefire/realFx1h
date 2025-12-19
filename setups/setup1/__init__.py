"""
Setup1 - Hammer and Shooting Star Pattern with Support/Resistance
Binary options trading setup for 5-minute timeframe
"""

__version__ = "1.0.0"
__author__ = "Trading Setup Scanner"
__description__ = "Hammer/Shooting Star patterns with triple touch confirmation"
__timeframe__ = "5min"
__signal_types__ = ["CALL", "PUT"]

# Export key functions and classes
from .pattern_detector import (
    analyze,
    detect_pattern,
    calculate_confidence,
    get_support_resistance,
    triple_touch,
    hammer,
    shooting_star,
    calculate_rsi,
    get_required_columns,
    validate_data
)

from .strategy import (
    apply_strategy,
    calculate_position_size,
    get_entry_price,
    get_expiry_time,
    calculate_risk_reward,
    get_stop_loss,
    get_take_profit
)

# Setup information
SETUP_INFO = {
    'name': 'setup1',
    'display_name': 'Hammer & Shooting Star with S/R',
    'version': __version__,
    'author': __author__,
    'description': __description__,
    'timeframe': __timeframe__,
    'signal_types': __signal_types__,
    'patterns': ['hammer', 'shooting_star'],
    'indicators': ['rsi', 'support_resistance'],
    'trade_type': 'binary_options',  # binary_options, regular_trading
    'expiry_period': '15min',  # For binary options
    'min_confidence': 70,
    'created_date': '2024-01-01',
    'last_modified': '2024-01-01'
}

# Export everything
__all__ = [
    # Pattern detector functions
    'analyze',
    'detect_pattern',
    'calculate_confidence',
    'get_support_resistance',
    'triple_touch',
    'hammer',
    'shooting_star',
    'calculate_rsi',
    'get_required_columns',
    'validate_data',
    
    # Strategy functions
    'apply_strategy',
    'calculate_position_size',
    'get_entry_price',
    'get_expiry_time',
    'calculate_risk_reward',
    'get_stop_loss',
    'get_take_profit',
    
    # Setup info
    'SETUP_INFO'
]

# Quick test function
def test_setup():
    """Quick test to verify setup is working"""
    print(f"Setup1 v{__version__} loaded successfully")
    print(f"Description: {__description__}")
    print(f"Timeframe: {__timeframe__}")
    print(f"Patterns: {SETUP_INFO['patterns']}")
    print(f"Signal Types: {__signal_types__}")
    return True

# Auto-run test when imported in development
if __name__ == "__main__":
    test_setup()