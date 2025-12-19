import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

def pip_size(symbol: str) -> float:
    """Return the pip size for a given symbol."""
    return 0.01 if 'JPY' in symbol else 0.0001

def find_support_resistance_levels(df: pd.DataFrame, symbol: str, window: int = 15, lookback: int = 100) -> tuple:
    """
    Find actual support/resistance levels where price has reversed multiple times.
    Returns arrays of support and resistance levels.
    """
    if len(df) < lookback:
        logging.warning(f"Insufficient data for {symbol}: {len(df)} < {lookback}")
        return np.array([]), np.array([])
    
    pips = pip_size(symbol) * window
    data = df.iloc[-lookback:].copy()
    
    # Find local minima and maxima
    minima_idx = argrelextrema(data['low'].values, np.less, order=5)[0]
    maxima_idx = argrelextrema(data['high'].values, np.greater, order=5)[0]
    
    support_levels = data['low'].iloc[minima_idx].values if len(minima_idx) > 0 else np.array([])
    resistance_levels = data['high'].iloc[maxima_idx].values if len(maxima_idx) > 0 else np.array([])
    
    # Cluster nearby levels (within window pips)
    def cluster_levels(levels: np.ndarray) -> np.ndarray:
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

def triple_touch(df: pd.DataFrame, symbol: str, touches: int = 3, window: int = 15, lookback: int = 100) -> tuple:
    """
    Check if current candle touches any support/resistance level.
    Returns: (touches_resistance, touches_support)
    """
    if len(df) < lookback:
        logging.warning(f"Insufficient data for {symbol}: {len(df)} < {lookback}")
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
    """Detect Hammer pattern."""
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    if body == 0:
        return False
    lower_shadow = min(df['close'].iloc[-1], df['open'].iloc[-1]) - df['low'].iloc[-1]
    upper_shadow = df['high'].iloc[-1] - max(df['close'].iloc[-1], df['open'].iloc[-1])
    return (lower_shadow > 2 * body) and (upper_shadow < body * 0.5)

def shooting_star(df: pd.DataFrame) -> bool:
    """Detect Shooting Star pattern."""
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    if body == 0:
        return False
    upper_shadow = df['high'].iloc[-1] - max(df['close'].iloc[-1], df['open'].iloc[-1])
    lower_shadow = min(df['close'].iloc[-1], df['open'].iloc[-1]) - df['low'].iloc[-1]
    return (upper_shadow > 2 * body) and (lower_shadow < body * 0.5)

def rsi(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate the Relative Strength Index (RSI)."""
    if len(df) < period:
        return 50
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.iloc[-1]

def get_signal(df: pd.DataFrame, symbol: str, cfg: dict, historical_index: int = None) -> tuple:
    """
    Generate trading signals based on the provided configuration.
    """
    if historical_index is not None:
        if historical_index < 1 or historical_index >= len(df):
            logging.warning(f"Invalid historical index: {historical_index}")
            return None, {}
        
        candle_a_df = df.iloc[:historical_index]      # Data up to Candle A
        candle_b_df = df.iloc[:historical_index+1]    # Data up to Candle B
    else:
        if len(df) < 2:
            logging.warning("Not enough data for signal generation")
            return None, {}
        
        candle_a_df = df.iloc[:-1]  # All except current (Candle A)
        candle_b_df = df            # Current is Candle B

    # === CANDLE A: Setup Detection ===
    touch_h, touch_l = triple_touch(candle_a_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    rsi_val = rsi(candle_a_df)
    
    bull_hammer = hammer(candle_a_df)
    bear_star = shooting_star(candle_a_df)

    # === CANDLE B: Direction Confirmation ===
    candle_b_bullish = candle_b_df['close'].iloc[-1] > candle_b_df['open'].iloc[-1]
    candle_b_bearish = candle_b_df['close'].iloc[-1] < candle_b_df['open'].iloc[-1]

    conditions_info = {
        'candle_a_touch_h': touch_h,
        'candle_a_touch_l': touch_l,
        'candle_a_rsi': rsi_val,
        'candle_a_hammer': bull_hammer,
        'candle_a_shooting_star': bear_star,
        'candle_b_bullish': candle_b_bullish,
        'candle_b_bearish': candle_b_bearish,
        'triggered_pattern': None
    }

    # CALL: Hammer setup on Candle A + Bullish confirmation on Candle B
    if touch_l and bull_hammer and rsi_val < cfg['filters']['rsi_oversold'] and candle_b_bullish:
        conditions_info['triggered_pattern'] = "Hammer"
        return 'CALL', conditions_info

    # PUT: Shooting Star setup on Candle A + Bearish confirmation on Candle B
    if touch_h and bear_star and rsi_val > cfg['filters']['rsi_overbought'] and candle_b_bearish:
        conditions_info['triggered_pattern'] = "Shooting Star"
        return 'PUT', conditions_info

    return None, conditions_info

def detect_setup_only(df: pd.DataFrame, symbol: str, cfg: dict, historical_index: int = None) -> tuple:
    """
    Detect setup on Candle A only (no confirmation needed).
    """
    if historical_index is not None:
        if historical_index < 1 or historical_index >= len(df):
            logging.warning(f"Invalid historical index: {historical_index}")
            return None, {}
        candle_a_df = df.iloc[:historical_index]  # Data up to Candle A
    else:
        if len(df) < 2:
            logging.warning("Not enough data for setup detection")
            return None, {}
        candle_a_df = df.iloc[:-1]  # All except current (Candle A is previous)

    touch_h, touch_l = triple_touch(candle_a_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    rsi_val = rsi(candle_a_df)
    
    bull_hammer = hammer(candle_a_df)
    bear_star = shooting_star(candle_a_df)

    conditions_info = {
        'candle_a_touch_h': touch_h,
        'candle_a_touch_l': touch_l,
        'candle_a_rsi': rsi_val,
        'candle_a_hammer': bull_hammer,
        'candle_a_shooting_star': bear_star,
        'triggered_pattern': None
    }

    # CALL: Hammer setup on Candle A at support with oversold RSI
    if touch_l and bull_hammer and rsi_val < cfg['filters']['rsi_oversold']:
        conditions_info['triggered_pattern'] = "Hammer"
        return 'CALL', conditions_info

    # PUT: Shooting Star setup on Candle A at resistance with overbought RSI
    if touch_h and bear_star and rsi_val > cfg['filters']['rsi_overbought']:
        conditions_info['triggered_pattern'] = "Shooting Star"
        return 'PUT', conditions_info

    return None, conditions_info

def get_support_resistance_price(df: pd.DataFrame, symbol: str, cfg: dict, conditions: dict, historical_index: int = None) -> tuple:
    """
    Extract the S/R price level that was touched.
    Returns: (price_level, level_type)
    """
    if historical_index is not None:
        if historical_index < 1:
            return None, None
        candle_a_df = df.iloc[:historical_index]
        candle_a = df.iloc[historical_index - 1]
    else:
        if len(df) < 2:
            return None, None
        candle_a = df.iloc[-2]
    
    support_levels, resistance_levels = find_support_resistance_levels(df, symbol, cfg['filters']['touch_window_pips'], 100)
    
    pips = pip_size(symbol) * cfg['filters']['touch_window_pips']
    
    if conditions['candle_a_touch_l']:
        for level in support_levels:
            if abs(candle_a['low'] - level) <= pips:
                return float(level), 'Support'
    
    if conditions['candle_a_touch_h']:
        for level in resistance_levels:
            if abs(candle_a['high'] - level) <= pips:
                return float(level), 'Resistance'
    
    return None, None

def debug_signal_conditions(df: pd.DataFrame, symbol: str, cfg: dict, historical_index: int = None):
    """
    Debug function to check signal conditions at specific points.
    """
    if historical_index is not None:
        if historical_index < 1 or historical_index >= len(df):
            logging.warning(f"Invalid index: {historical_index}")
            return
        
        candle_a_df = df.iloc[:historical_index]      # Data up to Candle A
        candle_b_df = df.iloc[:historical_index+1]    # Data up to Candle B
    else:
        if len(df) < 2:
            logging.warning("Not enough data")
            return
        
        candle_a_df = df.iloc[:-1]  # Candle A
        candle_b_df = df            # Candle B

    touch_h, touch_l = triple_touch(candle_a_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    rsi_val = rsi(candle_a_df)
    bull_hammer = hammer(candle_a_df)
    bear_star = shooting_star(candle_a_df)

    candle_b_bullish = candle_b_df['close'].iloc[-1] > candle_b_df['open'].iloc[-1]
    candle_b_bearish = candle_b_df['close'].iloc[-1] < candle_b_df['open'].iloc[-1]

    logging.info(f"\n=== DEBUG Signal conditions for {symbol} at Candle B index {historical_index if historical_index else 'latest'} ===")
    logging.info(f"Candle A Date: {candle_a_df['timestamp'].iloc[-1] if 'timestamp' in candle_a_df.columns else 'N/A'}")
    logging.info(f"Candle B Date: {candle_b_df['timestamp'].iloc[-1] if 'timestamp' in candle_b_df.columns else 'N/A'}")
    logging.info(f"Candle A - Touch High: {touch_h}, Touch Low: {touch_l}")
    logging.info(f"Candle A - Hammer: {bull_hammer}, Shooting Star: {bear_star}")
    logging.info(f"Candle A - RSI: {rsi_val:.2f} (Oversold<{cfg['filters']['rsi_oversold']}, Overbought>{cfg['filters']['rsi_overbought']})")
    logging.info(f"Candle B - Bullish: {candle_b_bullish}, Bearish: {candle_b_bearish}")
    
    call_ok = all([
        touch_l,
        bull_hammer,
        rsi_val < cfg['filters']['rsi_oversold'],
        candle_b_bullish
    ])
    
    put_ok = all([
        touch_h,
        bear_star,
        rsi_val > cfg['filters']['rsi_overbought'],
        candle_b_bearish
    ])
    
    logging.info(f"CALL conditions met: {call_ok}")
    logging.info(f"PUT conditions met: {put_ok}")
    logging.info("=" * 60)