"""
Pattern Detector for Setup1
Hammer and Shooting Star patterns with support/resistance confirmation
Adapted from original patterns.py
"""

import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from typing import Dict, Any, Tuple, Optional
import logging


def pip_size(symbol: str) -> float:
    """Calculate pip size for a symbol"""
    return 0.01 if 'JPY' in symbol else 0.0001


def find_support_resistance_levels(df: pd.DataFrame, symbol: str, 
                                  window: int = 15, lookback: int = 100) -> Tuple[np.ndarray, np.ndarray]:
    """
    Find actual support/resistance levels where price has reversed multiple times
    
    Args:
        df: DataFrame with price data
        symbol: Trading symbol
        window: Window size for clustering
        lookback: Number of candles to look back
        
    Returns:
        Tuple of (support_levels, resistance_levels)
    """
    if len(df) < lookback:
        return np.array([]), np.array([])
    
    pips = pip_size(symbol) * window
    data = df.iloc[-lookback:].copy()
    
    # Find local minima and maxima
    minima_idx = argrelextrema(data['low'].values, np.less, order=5)[0]
    maxima_idx = argrelextrema(data['high'].values, np.greater, order=5)[0]
    
    support_levels = data['low'].iloc[minima_idx].values if len(minima_idx) > 0 else np.array([])
    resistance_levels = data['high'].iloc[maxima_idx].values if len(maxima_idx) > 0 else np.array([])
    
    # Cluster nearby levels (within window pips)
    def cluster_levels(levels):
        if len(levels) == 0:
            return np.array([])
        levels = np.sort(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for price in levels[1:]:
            if price - current_cluster[-1] <= pips:
                current_cluster.append(price)
            else:
                clusters.append(np.mean(current_cluster))
                current_cluster = [price]
        
        if current_cluster:
            clusters.append(np.mean(current_cluster))
        
        return np.array(clusters)
    
    support_clusters = cluster_levels(support_levels)
    resistance_clusters = cluster_levels(resistance_levels)
    
    return support_clusters, resistance_clusters


def triple_touch(df: pd.DataFrame, symbol: str, touches: int = 3, 
                window: int = 15, lookback: int = 100) -> Tuple[bool, bool]:
    """
    Check if current candle touches any support/resistance level
    
    Args:
        df: DataFrame with price data
        symbol: Trading symbol
        touches: Minimum number of touches required
        window: Window size in pips
        lookback: Number of candles to look back
        
    Returns:
        Tuple of (touches_resistance, touches_support)
    """
    if len(df) < lookback:
        return False, False
    
    support_levels, resistance_levels = find_support_resistance_levels(df, symbol, window, lookback)
    
    current_candle = df.iloc[-1]
    current_high = current_candle['high']
    current_low = current_candle['low']
    pips = pip_size(symbol) * window
    
    # Check if touches resistance (within window pips)
    touches_resistance = False
    for level in resistance_levels:
        if abs(current_high - level) <= pips:
            touches_resistance = True
            break
    
    # Check if touches support (within window pips)
    touches_support = False
    for level in support_levels:
        if abs(current_low - level) <= pips:
            touches_support = True
            break
    
    # Count how many times price has touched this level recently
    if touches_resistance or touches_support:
        # Get recent candles
        recent_df = df.iloc[-lookback:-1] if len(df) > lookback else df.iloc[:-1]
        
        # Count resistance touches
        resistance_touch_count = 0
        if touches_resistance:
            for level in resistance_levels:
                if abs(current_high - level) <= pips:
                    # Check previous touches to this level
                    for i in range(len(recent_df)):
                        candle = recent_df.iloc[i]
                        if abs(candle['high'] - level) <= pips or abs(candle['low'] - level) <= pips:
                            resistance_touch_count += 1
        
        # Count support touches
        support_touch_count = 0
        if touches_support:
            for level in support_levels:
                if abs(current_low - level) <= pips:
                    # Check previous touches to this level
                    for i in range(len(recent_df)):
                        candle = recent_df.iloc[i]
                        if abs(candle['low'] - level) <= pips or abs(candle['high'] - level) <= pips:
                            support_touch_count += 1
        
        return resistance_touch_count >= touches, support_touch_count >= touches
    
    return False, False


def hammer(df: pd.DataFrame) -> bool:
    """
    Detect hammer candlestick pattern
    
    Args:
        df: DataFrame with price data
        
    Returns:
        bool: True if hammer pattern detected
    """
    if len(df) < 1:
        return False
    
    current_candle = df.iloc[-1]
    body = abs(current_candle['close'] - current_candle['open'])
    
    if body == 0:
        return False
    
    lower_shadow = min(current_candle['close'], current_candle['open']) - current_candle['low']
    upper_shadow = current_candle['high'] - max(current_candle['close'], current_candle['open'])
    
    # Hammer criteria: long lower shadow (> 2x body), small upper shadow (< 0.5x body)
    return (lower_shadow > 2 * body) and (upper_shadow < body * 0.5)


def shooting_star(df: pd.DataFrame) -> bool:
    """
    Detect shooting star candlestick pattern
    
    Args:
        df: DataFrame with price data
        
    Returns:
        bool: True if shooting star pattern detected
    """
    if len(df) < 1:
        return False
    
    current_candle = df.iloc[-1]
    body = abs(current_candle['close'] - current_candle['open'])
    
    if body == 0:
        return False
    
    upper_shadow = current_candle['high'] - max(current_candle['close'], current_candle['open'])
    lower_shadow = min(current_candle['close'], current_candle['open']) - current_candle['low']
    
    # Shooting star criteria: long upper shadow (> 2x body), small lower shadow (< 0.5x body)
    return (upper_shadow > 2 * body) and (lower_shadow < body * 0.5)


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate RSI indicator
    
    Args:
        df: DataFrame with price data
        period: RSI period
        
    Returns:
        float: RSI value
    """
    if len(df) < period:
        return 50.0
    
    close_prices = df['close']
    delta = close_prices.diff()
    
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    
    rs = gain / loss
    rsi_val = 100 - (100 / (1 + rs))
    
    return rsi_val.iloc[-1] if not pd.isna(rsi_val.iloc[-1]) else 50.0


def detect_pattern(data: pd.DataFrame, symbol: str, 
                  global_config: Dict[str, Any], 
                  setup_config: Dict[str, Any],
                  mode: str = 'live') -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Detect trading patterns in market data
    
    Args:
        data: Market data DataFrame
        symbol: Trading symbol
        global_config: Global configuration
        setup_config: Setup-specific configuration
        mode: Analysis mode ('live' or 'backtest')
        
    Returns:
        Tuple of (signal_type, conditions_dict) or (None, {})
    """
    if len(data) < 2:
        return None, {}
    
    # Get configuration values
    filters = setup_config.get('filters', global_config.get('filters', {}))
    
    min_touches = filters.get('min_touches', 3)
    touch_window = filters.get('touch_window_pips', 15)
    rsi_oversold = filters.get('rsi_oversold', 35)
    rsi_overbought = filters.get('rsi_overbought', 65)
    
    # Determine which candles to analyze based on mode
    if mode == 'backtest':
        # In backtest mode, we analyze all candles
        # For simplicity, analyze the last candle
        candle_a_df = data.iloc[:-1]  # Previous candle
        candle_b_df = data  # Current candle
        candle_a_index = -2
    else:
        # Live mode: Candle A is previous, Candle B is current
        candle_a_df = data.iloc[:-1]  # Previous candle (setup)
        candle_b_df = data  # Current candle (confirmation)
        candle_a_index = -2
    
    # === CANDLE A: Setup Detection ===
    touch_high, touch_low = triple_touch(
        candle_a_df, symbol, min_touches, touch_window
    )
    
    rsi_val = calculate_rsi(candle_a_df)
    is_hammer = hammer(candle_a_df)
    is_shooting_star = shooting_star(candle_a_df)
    
    # === CANDLE B: Direction Confirmation ===
    candle_b = candle_b_df.iloc[-1]
    candle_b_bullish = candle_b['close'] > candle_b['open']
    candle_b_bearish = candle_b['close'] < candle_b['open']
    
    # Conditions info for result
    conditions_info = {
        'candle_a_touch_high': touch_high,
        'candle_a_touch_low': touch_low,
        'candle_a_rsi': rsi_val,
        'candle_a_hammer': is_hammer,
        'candle_a_shooting_star': is_shooting_star,
        'candle_b_bullish': candle_b_bullish,
        'candle_b_bearish': candle_b_bearish,
        'triggered_pattern': None,
        'current_price': float(candle_b['close']),
        'timestamp': candle_b['timestamp'] if 'timestamp' in candle_b else None
    }
    
    # CALL Signal: Hammer at support with oversold RSI + bullish confirmation
    if (touch_low and is_hammer and rsi_val < rsi_oversold and candle_b_bullish):
        conditions_info['triggered_pattern'] = "Hammer"
        return 'CALL', conditions_info
    
    # PUT Signal: Shooting Star at resistance with overbought RSI + bearish confirmation
    if (touch_high and is_shooting_star and rsi_val > rsi_overbought and candle_b_bearish):
        conditions_info['triggered_pattern'] = "Shooting Star"
        return 'PUT', conditions_info
    
    return None, conditions_info


def get_support_resistance_price(df: pd.DataFrame, symbol: str, 
                                conditions: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    """
    Get the exact support/resistance price level that was touched
    
    Args:
        df: Market data DataFrame
        symbol: Trading symbol
        conditions: Pattern conditions dictionary
        
    Returns:
        Tuple of (price_level, level_type) or (None, None)
    """
    if not conditions.get('candle_a_touch_low') and not conditions.get('candle_a_touch_high'):
        return None, None
    
    # Get candle A (the setup candle)
    candle_a = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    
    # Get S/R levels
    support_levels, resistance_levels = find_support_resistance_levels(
        df, symbol, window=15, lookback=100
    )
    
    pips = pip_size(symbol) * 15  # Default window
    
    # Check support level
    if conditions.get('candle_a_touch_low'):
        for level in support_levels:
            if abs(candle_a['low'] - level) <= pips:
                return float(level), 'Support'
    
    # Check resistance level
    if conditions.get('candle_a_touch_high'):
        for level in resistance_levels:
            if abs(candle_a['high'] - level) <= pips:
                return float(level), 'Resistance'
    
    return None, None


def calculate_confidence(conditions: Dict[str, Any]) -> float:
    """
    Calculate confidence score for detected pattern
    
    Args:
        conditions: Pattern conditions dictionary
        
    Returns:
        float: Confidence score (0-100)
    """
    confidence = 50.0  # Base confidence
    
    # RSI proximity to extremes adds confidence
    rsi = conditions.get('candle_a_rsi', 50)
    if rsi < 30 or rsi > 70:
        confidence += 15
    elif rsi < 35 or rsi > 65:
        confidence += 10
    
    # Strong pattern confirmation
    if conditions.get('candle_a_hammer') or conditions.get('candle_a_shooting_star'):
        confidence += 10
    
    # Clear touch confirmation
    if conditions.get('candle_a_touch_low') or conditions.get('candle_a_touch_high'):
        confidence += 10
    
    # Candle B confirmation adds confidence
    if conditions.get('candle_b_bullish') or conditions.get('candle_b_bearish'):
        confidence += 15
    
    # Cap at 100
    return min(confidence, 100.0)


def analyze(data: pd.DataFrame, symbol: str, 
           global_config: Dict[str, Any], 
           setup_config: Dict[str, Any],
           mode: str = 'live') -> Optional[Dict[str, Any]]:
    """
    Main analysis function - called by controller
    
    Args:
        data: Market data DataFrame
        symbol: Trading symbol
        global_config: Global configuration
        setup_config: Setup-specific configuration
        mode: Analysis mode ('live' or 'backtest')
        
    Returns:
        Dict with analysis results or None
    """
    # Detect pattern
    signal_type, conditions = detect_pattern(data, symbol, global_config, setup_config, mode)
    
    if not signal_type:
        return None
    
    # Get S/R price level
    sr_price, sr_type = get_support_resistance_price(data, symbol, conditions)
    
    # Calculate confidence
    confidence = calculate_confidence(conditions)
    
    # Create result dictionary
    result = {
        'signal_type': signal_type,
        'pattern_name': conditions.get('triggered_pattern', 'Unknown'),
        'confidence': confidence,
        'rsi': conditions.get('candle_a_rsi', 50),
        'current_price': conditions.get('current_price', 0),
        'timestamp': conditions.get('timestamp'),
        'conditions': conditions,
        'support_resistance_level': sr_price,
        'level_type': sr_type,
        'signal_strength': 'STRONG' if confidence > 80 else 'MODERATE' if confidence > 65 else 'WEAK'
    }
    
    return result


def get_required_columns() -> list:
    """
    Get list of required data columns for this setup
    
    Returns:
        list: Required column names
    """
    return ['timestamp', 'open', 'high', 'low', 'close', 'volume']


def validate_data(data: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate that data has required columns and structure
    
    Args:
        data: DataFrame to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_columns = get_required_columns()
    
    missing_columns = [col for col in required_columns if col not in data.columns]
    if missing_columns:
        return False, f"Missing columns: {missing_columns}"
    
    if len(data) < 10:
        return False, "Insufficient data (need at least 10 candles)"
    
    # Check for NaN values
    nan_counts = data[required_columns].isna().sum()
    if nan_counts.any():
        return False, f"NaN values found in: {nan_counts[nan_counts > 0].to_dict()}"
    
    return True, "Data is valid"


# Test function
if __name__ == "__main__":
    # Create sample data for testing
    sample_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='5min'),
        'open': np.random.randn(100).cumsum() + 100,
        'high': np.random.randn(100).cumsum() + 101,
        'low': np.random.randn(100).cumsum() + 99,
        'close': np.random.randn(100).cumsum() + 100,
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    sample_config = {
        'filters': {
            'min_touches': 3,
            'touch_window_pips': 15,
            'rsi_oversold': 35,
            'rsi_overbought': 65
        }
    }
    
    # Test pattern detection
    signal, conditions = detect_pattern(sample_data, 'EUR/USD', sample_config, sample_config)
    
    if signal:
        print(f"Signal detected: {signal}")
        print(f"Conditions: {conditions}")
    else:
        print("No signal detected")
    
    # Test validation
    is_valid, msg = validate_data(sample_data)
    print(f"Data validation: {is_valid}, {msg}")