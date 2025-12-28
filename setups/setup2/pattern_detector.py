"""
Pattern Detector for Setup2
MA Crossover Momentum Strategy with Stochastic and Bollinger Band confirmation
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional
import logging


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average
    
    Args:
        data: Price series
        period: EMA period
        
    Returns:
        pd.Series: EMA values
    """
    return data.ewm(span=period, adjust=False).mean()


def calculate_stochastic(df: pd.DataFrame, k_period: int = 5, 
                        d_period: int = 3, smooth_k: int = 3) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic Oscillator
    
    Args:
        df: DataFrame with high, low, close
        k_period: Period for %K
        d_period: Period for %D
        smooth_k: Smoothing period for %K
        
    Returns:
        Tuple of (%K, %D) series
    """
    # Calculate raw stochastic
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    stoch_k = 100 * (df['close'] - low_min) / (high_max - low_min)
    
    # Smooth %K
    stoch_k = stoch_k.rolling(window=smooth_k).mean()
    
    # Calculate %D (signal line)
    stoch_d = stoch_k.rolling(window=d_period).mean()
    
    return stoch_k, stoch_d


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, 
                             std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands
    
    Args:
        df: DataFrame with close prices
        period: Moving average period
        std_dev: Standard deviation multiplier
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle_band = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band


def detect_ma_crossover(ema_fast: pd.Series, ema_slow: pd.Series) -> Tuple[bool, bool]:
    """
    Detect MA crossover
    
    Args:
        ema_fast: Fast EMA series
        ema_slow: Slow EMA series
        
    Returns:
        Tuple of (bullish_cross, bearish_cross)
    """
    if len(ema_fast) < 2 or len(ema_slow) < 2:
        return False, False
    
    # Current values
    fast_now = ema_fast.iloc[-1]
    slow_now = ema_slow.iloc[-1]
    
    # Previous values
    fast_prev = ema_fast.iloc[-2]
    slow_prev = ema_slow.iloc[-2]
    
    # Bullish crossover: fast crosses above slow
    bullish_cross = (fast_prev <= slow_prev) and (fast_now > slow_now)
    
    # Bearish crossover: fast crosses below slow
    bearish_cross = (fast_prev >= slow_prev) and (fast_now < slow_now)
    
    return bullish_cross, bearish_cross


def check_trend_direction(price: float, ema_100: float) -> str:
    """
    Check trend direction based on price vs EMA 100
    
    Args:
        price: Current price
        ema_100: EMA 100 value
        
    Returns:
        str: 'bullish', 'bearish', or 'neutral'
    """
    if price > ema_100:
        return 'bullish'
    elif price < ema_100:
        return 'bearish'
    else:
        return 'neutral'


def check_stochastic_crossover(stoch_k: pd.Series, stoch_d: pd.Series) -> Tuple[bool, bool]:
    """
    Check stochastic crossover
    
    Args:
        stoch_k: Stochastic %K series
        stoch_d: Stochastic %D series
        
    Returns:
        Tuple of (bullish_cross, bearish_cross)
    """
    if len(stoch_k) < 2 or len(stoch_d) < 2:
        return False, False
    
    k_now = stoch_k.iloc[-1]
    d_now = stoch_d.iloc[-1]
    k_prev = stoch_k.iloc[-2]
    d_prev = stoch_d.iloc[-2]
    
    # Bullish: K crosses above D
    bullish_cross = (k_prev <= d_prev) and (k_now > d_now)
    
    # Bearish: K crosses below D
    bearish_cross = (k_prev >= d_prev) and (k_now < d_now)
    
    return bullish_cross, bearish_cross


def check_bollinger_position(price: float, upper_band: float, 
                            lower_band: float) -> str:
    """
    Check price position relative to Bollinger Bands
    
    Args:
        price: Current price
        upper_band: Upper Bollinger Band
        lower_band: Lower Bollinger Band
        
    Returns:
        str: 'above', 'below', or 'inside'
    """
    if price > upper_band:
        return 'above'
    elif price < lower_band:
        return 'below'
    else:
        return 'inside'


def check_ema_touch(df: pd.DataFrame, ema_100: pd.Series, 
                   symbol: str, lookback: int = 3) -> bool:
    """
    Check if price touched EMA 100 in recent candles
    
    Args:
        df: DataFrame with price data
        ema_100: EMA 100 series
        symbol: Trading symbol
        lookback: Number of candles to look back
        
    Returns:
        bool: True if touched
    """
    if len(df) < lookback or len(ema_100) < lookback:
        return False
    
    pip_size = 0.01 if 'JPY' in symbol else 0.0001
    touch_distance = pip_size * 10  # Within 10 pips
    
    recent_df = df.iloc[-lookback:]
    recent_ema = ema_100.iloc[-lookback:]
    
    for i in range(len(recent_df)):
        candle = recent_df.iloc[i]
        ema_val = recent_ema.iloc[i]
        
        # Check if price came within touch distance
        if (candle['low'] <= ema_val + touch_distance and 
            candle['high'] >= ema_val - touch_distance):
            return True
    
    return False


def check_volume_confirmation(df: pd.DataFrame, volume_period: int = 20, 
                             multiplier: float = 1.2) -> bool:
    """
    Check if current volume is above average
    
    Args:
        df: DataFrame with volume data
        volume_period: Period for average volume
        multiplier: Required multiplier above average
        
    Returns:
        bool: True if volume confirmed
    """
    if len(df) < volume_period + 1:
        return True  # Default to true if not enough data
    
    if 'volume' not in df.columns:
        return True  # Default to true if no volume data
    
    avg_volume = df['volume'].iloc[-volume_period-1:-1].mean()
    current_volume = df['volume'].iloc[-1]
    
    return current_volume > (avg_volume * multiplier)


def detect_pattern(data: pd.DataFrame, symbol: str, 
                  global_config: Dict[str, Any], 
                  setup_config: Dict[str, Any],
                  mode: str = 'live') -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Detect MA Crossover patterns with confirmations
    
    Args:
        data: Market data DataFrame
        symbol: Trading symbol
        global_config: Global configuration
        setup_config: Setup-specific configuration
        mode: Analysis mode ('live' or 'backtest')
        
    Returns:
        Tuple of (signal_type, conditions_dict) or (None, {})
    """
    if len(data) < 100:  # Need at least 100 candles for EMA 100
        return None, {}
    
    # Get configuration
    filters = setup_config.get('filters', {})
    stoch_overbought = filters.get('stoch_overbought', 70)
    stoch_oversold = filters.get('stoch_oversold', 30)
    
    # Calculate indicators
    ema_2 = calculate_ema(data['close'], 2)
    ema_5 = calculate_ema(data['close'], 5)
    ema_100 = calculate_ema(data['close'], 100)
    
    stoch_k, stoch_d = calculate_stochastic(data, k_period=5, d_period=3, smooth_k=3)
    
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(data, period=20, std_dev=2.0)
    
    # Current values
    current_price = data['close'].iloc[-1]
    current_ema_2 = ema_2.iloc[-1]
    current_ema_5 = ema_5.iloc[-1]
    current_ema_100 = ema_100.iloc[-1]
    current_stoch_k = stoch_k.iloc[-1]
    current_stoch_d = stoch_d.iloc[-1]
    current_upper_bb = upper_bb.iloc[-1]
    current_lower_bb = lower_bb.iloc[-1]
    
    # Detect crossovers
    ma_bullish_cross, ma_bearish_cross = detect_ma_crossover(ema_2, ema_5)
    stoch_bullish_cross, stoch_bearish_cross = check_stochastic_crossover(stoch_k, stoch_d)
    
    # Check trend
    trend = check_trend_direction(current_price, current_ema_100)
    
    # Check Bollinger position
    bb_position = check_bollinger_position(current_price, current_upper_bb, current_lower_bb)
    
    # Check EMA touch
    ema_touched = check_ema_touch(data, ema_100, symbol, lookback=3)
    
    # Check volume
    volume_confirmed = check_volume_confirmation(data)
    
    # Check if coming from oversold/overbought
    stoch_from_oversold = any(stoch_k.iloc[-3:-1] < 15)
    stoch_from_overbought = any(stoch_k.iloc[-3:-1] > 85)
    
    # Current candle direction
    current_candle = data.iloc[-1]
    candle_bullish = current_candle['close'] > current_candle['open']
    candle_bearish = current_candle['close'] < current_candle['open']
    candle_body_pct = abs(current_candle['close'] - current_candle['open']) / (current_candle['high'] - current_candle['low']) if (current_candle['high'] - current_candle['low']) > 0 else 0
    
    # Conditions dictionary
    conditions_info = {
        'ema_2': float(current_ema_2),
        'ema_5': float(current_ema_5),
        'ema_100': float(current_ema_100),
        'stoch_k': float(current_stoch_k),
        'stoch_d': float(current_stoch_d),
        'ma_bullish_cross': ma_bullish_cross,
        'ma_bearish_cross': ma_bearish_cross,
        'stoch_bullish_cross': stoch_bullish_cross,
        'stoch_bearish_cross': stoch_bearish_cross,
        'trend': trend,
        'bb_position': bb_position,
        'ema_touched': ema_touched,
        'volume_confirmed': volume_confirmed,
        'stoch_from_oversold': stoch_from_oversold,
        'stoch_from_overbought': stoch_from_overbought,
        'candle_bullish': candle_bullish,
        'candle_bearish': candle_bearish,
        'candle_body_pct': candle_body_pct,
        'current_price': float(current_price),
        'timestamp': current_candle['timestamp'] if 'timestamp' in current_candle else None
    }
    
    # === CALL SIGNAL DETECTION ===
    if ma_bullish_cross and trend == 'bullish':
        # Count secondary conditions
        secondary_count = 0
        
        if stoch_bullish_cross:
            secondary_count += 1
        if current_stoch_k < stoch_oversold or stoch_from_oversold:
            secondary_count += 1
        if ema_touched:
            secondary_count += 1
        if candle_bullish:
            secondary_count += 1
        
        # Need at least 2 secondary conditions
        if secondary_count >= 2:
            conditions_info['triggered_pattern'] = 'MA Crossover Bullish'
            conditions_info['secondary_conditions_met'] = secondary_count
            return 'CALL', conditions_info
    
    # === PUT SIGNAL DETECTION ===
    if ma_bearish_cross:
        # Check if trend is bearish OR price is overextended (outside upper BB)
        valid_trend = (trend == 'bearish') or (bb_position == 'above')
        
        if valid_trend:
            # Count secondary conditions
            secondary_count = 0
            
            if stoch_bearish_cross:
                secondary_count += 1
            if current_stoch_k > stoch_overbought or stoch_from_overbought:
                secondary_count += 1
            if bb_position == 'above' or any(data['close'].iloc[-3:-1] > upper_bb.iloc[-3:-1]):
                secondary_count += 1
            if candle_bearish:
                secondary_count += 1
            
            # Need at least 2 secondary conditions
            if secondary_count >= 2:
                conditions_info['triggered_pattern'] = 'MA Crossover Bearish'
                conditions_info['secondary_conditions_met'] = secondary_count
                return 'PUT', conditions_info
    
    return None, conditions_info


def calculate_confidence(conditions: Dict[str, Any]) -> float:
    """
    Calculate confidence score for detected pattern
    
    Args:
        conditions: Pattern conditions dictionary
        
    Returns:
        float: Confidence score (0-100)
    """
    confidence = 60.0  # Base confidence
    
    # Stochastic crossover adds confidence
    if conditions.get('stoch_bullish_cross') or conditions.get('stoch_bearish_cross'):
        confidence += 10
    
    # Coming from extreme zones adds confidence
    if conditions.get('stoch_from_oversold') or conditions.get('stoch_from_overbought'):
        confidence += 10
    
    # EMA touch/bounce adds confidence
    if conditions.get('ema_touched'):
        confidence += 10
    
    # Bollinger Band position adds confidence for PUT
    if conditions.get('bb_position') == 'above' and conditions.get('triggered_pattern') == 'MA Crossover Bearish':
        confidence += 10
    
    # Strong candle body adds confidence
    if conditions.get('candle_body_pct', 0) > 0.6:
        confidence += 5
    
    # Volume confirmation adds confidence
    if conditions.get('volume_confirmed'):
        confidence += 5
    
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
    
    # Calculate confidence
    confidence = calculate_confidence(conditions)
    
    # Check minimum confidence
    min_confidence = setup_config.get('min_confidence', 60)
    if confidence < min_confidence:
        return None
    
    # Create result dictionary
    result = {
        'signal_type': signal_type,
        'pattern_name': conditions.get('triggered_pattern', 'Unknown'),
        'confidence': confidence,
        'current_price': conditions.get('current_price', 0),
        'timestamp': conditions.get('timestamp'),
        'conditions': conditions,
        'ema_2': conditions.get('ema_2'),
        'ema_5': conditions.get('ema_5'),
        'ema_100': conditions.get('ema_100'),
        'stoch_k': conditions.get('stoch_k'),
        'stoch_d': conditions.get('stoch_d'),
        'trend': conditions.get('trend'),
        'secondary_conditions': conditions.get('secondary_conditions_met', 0),
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
    
    if len(data) < 100:
        return False, "Insufficient data (need at least 100 candles for EMA 100)"
    
    # Check for NaN values
    nan_counts = data[required_columns].isna().sum()
    if nan_counts.any():
        return False, f"NaN values found in: {nan_counts[nan_counts > 0].to_dict()}"
    
    return True, "Data is valid"