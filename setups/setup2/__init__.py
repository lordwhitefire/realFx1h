"""
Setup2 - MA Crossover Momentum Strategy
Binary options trading setup for 5-minute timeframe
"""

__version__ = "1.0.0"
__author__ = "Trading Setup Scanner"
__description__ = "MA Crossover with Stochastic and Bollinger Band confirmation"
__timeframe__ = "5min"
__signal_types__ = ["CALL", "PUT"]

# Export key functions and classes
from .pattern_detector import (
    analyze,
    detect_pattern,
    calculate_confidence,
    calculate_ema,
    calculate_stochastic,
    calculate_bollinger_bands,
    detect_ma_crossover,
    check_trend_direction,
    check_stochastic_crossover,
    check_bollinger_position,
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
    'name': 'setup2',
    'display_name': 'MA Crossover Momentum',
    'version': __version__,
    'author': __author__,
    'description': __description__,
    'timeframe': __timeframe__,
    'signal_types': __signal_types__,
    'patterns': ['ma_crossover_bullish', 'ma_crossover_bearish'],
    'indicators': ['ema_2', 'ema_5', 'ema_100', 'stochastic', 'bollinger_bands'],
    'trade_type': 'binary_options',
    'expiry_period': '15min',
    'min_confidence': 60,
    'created_date': '2024-01-01',
    'last_modified': '2024-01-01'
}

# Export everything
__all__ = [
    # Pattern detector functions
    'analyze',
    'detect_pattern',
    'calculate_confidence',
    'calculate_ema',
    'calculate_stochastic',
    'calculate_bollinger_bands',
    'detect_ma_crossover',
    'check_trend_direction',
    'check_stochastic_crossover',
    'check_bollinger_position',
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
    print(f"Setup2 v{__version__} loaded successfully")
    print(f"Description: {__description__}")
    print(f"Timeframe: {__timeframe__}")
    print(f"Indicators: {SETUP_INFO['indicators']}")
    print(f"Signal Types: {__signal_types__}")
    return True

# Auto-run test when imported in development
if __name__ == "__main__":
    test_setup()