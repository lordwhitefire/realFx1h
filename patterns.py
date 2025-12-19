import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

def pip_size(symbol):
    return 0.01 if 'JPY' in symbol else 0.0001

def find_support_resistance_levels(df, symbol, window=15, lookback=100):
    """
    Find actual support/resistance levels where price has reversed multiple times
    Returns arrays of support and resistance levels
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

def triple_touch(df, symbol, touches=3, window=15, lookback=100):
    """
    Check if current candle touches any support/resistance level
    Returns: (touches_resistance, touches_support)
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

def hammer(df):
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    if body == 0:
        return False
    lower_shadow = min(df['close'].iloc[-1], df['open'].iloc[-1]) - df['low'].iloc[-1]
    upper_shadow = df['high'].iloc[-1] - max(df['close'].iloc[-1], df['open'].iloc[-1])
    return (lower_shadow > 2 * body) and (upper_shadow < body * 0.5)

def shooting_star(df):
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    if body == 0:
        return False
    upper_shadow = df['high'].iloc[-1] - max(df['close'].iloc[-1], df['open'].iloc[-1])
    lower_shadow = min(df['close'].iloc[-1], df['open'].iloc[-1]) - df['low'].iloc[-1]
    return (upper_shadow > 2 * body) and (lower_shadow < body * 0.5)

def rsi(df, period=14):
    if len(df) < period:
        return 50
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.iloc[-1]

def get_signal(df, symbol, cfg, historical_index=None):
    """
    BACKTEST MODE: Checks Candle A setup + Candle B confirmation together
    historical_index refers to CANDLE B (confirmation candle)
    - Candle A = historical_index - 1 (setup)
    - Candle B = historical_index (confirmation) 
    - Entry at Candle C open (next candle)
    - Expiry at Candle F open (15 minutes later)
    """
    if historical_index is not None:
        # For historical analysis
        if historical_index < 1 or historical_index >= len(df):
            return None, {}
        
        # Candle A = index-1 (setup), Candle B = index (confirmation)
        candle_a_df = df.iloc[:historical_index]      # Data up to Candle A
        candle_b_df = df.iloc[:historical_index+1]    # Data up to Candle B
        
    else:
        # For live trading - use latest data
        if len(df) < 2:
            return None, {}
        
        # Candle A = previous candle, Candle B = current candle
        candle_a_df = df.iloc[:-1]  # All except current (Candle A)
        candle_b_df = df            # Current is Candle B

    # === CANDLE A: Setup Detection ===
    touch_h, touch_l = triple_touch(candle_a_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    rsi_val = rsi(candle_a_df)
    
    # ONLY USE HAMMER AND SHOOTING STAR PATTERNS
    bull_hammer = hammer(candle_a_df)
    bear_star = shooting_star(candle_a_df)

    # === CANDLE B: Direction Confirmation ===
    candle_b_bullish = candle_b_df['close'].iloc[-1] > candle_b_df['open'].iloc[-1]
    candle_b_bearish = candle_b_df['close'].iloc[-1] < candle_b_df['open'].iloc[-1]

    # Conditions info for debugging
    conditions_info = {
        'candle_a_touch_h': touch_h,
        'candle_a_touch_l': touch_l,
        'candle_a_rsi': rsi_val,
        'candle_a_hammer': bull_hammer,
        'candle_a_shooting_star': bear_star,
        'candle_b_bullish': candle_b_bullish,
        'candle_b_bearish': candle_b_bearish,
        'triggered_pattern': None  # Track which pattern actually triggered
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

def detect_setup_only(df, symbol, cfg, historical_index=None):
    """
    LIVE MODE: Detects setup on Candle A ONLY (no Candle B confirmation needed)
    Returns signal and conditions if Candle A has valid setup
    """
    if historical_index is not None:
        # For debugging/testing
        if historical_index < 1 or historical_index >= len(df):
            return None, {}
        candle_a_df = df.iloc[:historical_index]  # Data up to Candle A
    else:
        # For live trading - Candle A is the previous candle
        if len(df) < 2:
            return None, {}
        candle_a_df = df.iloc[:-1]  # All except current (Candle A is previous)

    # === CANDLE A: Setup Detection ONLY ===
    touch_h, touch_l = triple_touch(candle_a_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    rsi_val = rsi(candle_a_df)
    
    # ONLY USE HAMMER AND SHOOTING STAR PATTERNS
    bull_hammer = hammer(candle_a_df)
    bear_star = shooting_star(candle_a_df)

    # Conditions info for alert
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

def get_support_resistance_price(df, symbol, cfg, conditions, historical_index=None):
    """
    Extract the S/R price level that was touched
    Returns: (price_level, level_type)
    """
    if historical_index is not None:
        # For historical analysis
        if historical_index < 1:
            return None, None
        candle_a_df = df.iloc[:historical_index]
        candle_a = df.iloc[historical_index - 1]
    else:
        # For live - Candle A is the previous candle
        if len(df) < 2:
            return None, None
        candle_a = df.iloc[-2]
    
    # Get S/R levels
    support_levels, resistance_levels = find_support_resistance_levels(
        df, symbol, cfg['filters']['touch_window_pips'], 100
    )
    
    pips = pip_size(symbol) * cfg['filters']['touch_window_pips']
    
    # Check which level was touched
    if conditions['candle_a_touch_l']:
        # Find closest support level
        for level in support_levels:
            if abs(candle_a['low'] - level) <= pips:
                return float(level), 'Support'
    
    if conditions['candle_a_touch_h']:
        # Find closest resistance level
        for level in resistance_levels:
            if abs(candle_a['high'] - level) <= pips:
                return float(level), 'Resistance'
    
    return None, None

# Debug function to check signal conditions at specific points
def debug_signal_conditions(df, symbol, cfg, historical_index=None):
    """Debug function using the same 2-candle logic as get_signal"""
    if historical_index is not None:
        if historical_index < 1 or historical_index >= len(df):
            print(f"Invalid index: {historical_index}")
            return
        
        candle_a_df = df.iloc[:historical_index]      # Data up to Candle A
        candle_b_df = df.iloc[:historical_index+1]    # Data up to Candle B
    else:
        if len(df) < 2:
            print("Not enough data")
            return
        
        candle_a_df = df.iloc[:-1]  # Candle A
        candle_b_df = df            # Candle B

    # CANDLE A: Setup Detection
    touch_h, touch_l = triple_touch(candle_a_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    rsi_val = rsi(candle_a_df)
    bull_hammer = hammer(candle_a_df)
    bear_star = shooting_star(candle_a_df)

    # CANDLE B: Direction
    candle_b_bullish = candle_b_df['close'].iloc[-1] > candle_b_df['open'].iloc[-1]
    candle_b_bearish = candle_b_df['close'].iloc[-1] < candle_b_df['open'].iloc[-1]

    print(f"\n=== DEBUG Signal conditions for {symbol} at Candle B index {historical_index if historical_index else 'latest'} ===")
    print(f"Candle A Date: {candle_a_df['timestamp'].iloc[-1] if 'timestamp' in candle_a_df.columns else 'N/A'}")
    print(f"Candle B Date: {candle_b_df['timestamp'].iloc[-1] if 'timestamp' in candle_b_df.columns else 'N/A'}")
    print(f"Candle A - Touch High: {touch_h}, Touch Low: {touch_l}")
    print(f"Candle A - Hammer: {bull_hammer}, Shooting Star: {bear_star}")
    print(f"Candle A - RSI: {rsi_val:.2f} (Oversold<{cfg['filters']['rsi_oversold']}, Overbought>{cfg['filters']['rsi_overbought']})")
    print(f"Candle B - Bullish: {candle_b_bullish}, Bearish: {candle_b_bearish}")
    
    # Check conditions
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
    
    print(f"CALL conditions met: {call_ok}")
    print(f"PUT conditions met: {put_ok}")
    print("=" * 60)