import pandas as pd
import numpy as np

def pip_size(symbol):
    return 0.01 if 'JPY' in symbol else 0.0001

def triple_touch(df, symbol, touches=3, window=15):
    pips = pip_size(symbol) * window
    highs = df['high'].rolling(50).max()
    lows  = df['low'].rolling(50).min()
    touch_h = ((df['high'] >= highs - pips) & (df['high'] <= highs + pips)).rolling(30).sum()
    touch_l = ((df['low']  >= lows  - pips) & (df['low']  <= lows  + pips)).rolling(30).sum()
    return touch_h.iloc[-1] >= touches, touch_l.iloc[-1] >= touches

def engulfing(df, ratio=1.3):
    if len(df) < 2:
        return False, False
    prev_body = abs(df['close'].iloc[-2] - df['open'].iloc[-2])
    curr_body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    bull = (df['close'].iloc[-1] > df['open'].iloc[-1]) and (df['close'].iloc[-2] < df['open'].iloc[-2])
    bull = bull and (curr_body > ratio * prev_body)
    bear = (df['close'].iloc[-1] < df['open'].iloc[-1]) and (df['close'].iloc[-2] > df['open'].iloc[-2])
    bear = bear and (curr_body > ratio * prev_body)
    return bull, bear

def hammer(df):
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    lower_shadow = min(df['close'].iloc[-1], df['open'].iloc[-1]) - df['low'].iloc[-1]
    upper_shadow = df['high'].iloc[-1] - max(df['close'].iloc[-1], df['open'].iloc[-1])
    return (lower_shadow > 2 * body) and (upper_shadow < body)

def shooting_star(df):
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    upper_shadow = df['high'].iloc[-1] - max(df['close'].iloc[-1], df['open'].iloc[-1])
    lower_shadow = min(df['close'].iloc[-1], df['open'].iloc[-1]) - df['low'].iloc[-1]
    return (upper_shadow > 2 * body) and (lower_shadow < body)

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
    # Use historical_index if provided, otherwise use latest data
    if historical_index is not None:
        current_df = df.iloc[:historical_index+1]
    else:
        current_df = df
    
    # Check if we have enough data for analysis
    if len(current_df) < 50:
        return None, {}
    
    touch_h, touch_l = triple_touch(current_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    bull_eng, bear_eng = engulfing(current_df, cfg['patterns']['engulfing_min_ratio'])
    bull_hammer = hammer(current_df)
    bear_star   = shooting_star(current_df)
    rsi_val     = rsi(current_df)
    direction_bull = current_df['close'].iloc[-1] > current_df['open'].iloc[-1]
    direction_bear = current_df['close'].iloc[-1] < current_df['open'].iloc[-1]

    # Create conditions info for analysis
    conditions_info = {
        'touch_h': touch_h,
        'touch_l': touch_l,
        'bull_eng': bull_eng,
        'bear_eng': bear_eng,
        'bull_hammer': bull_hammer,
        'bear_star': bear_star,
        'rsi': rsi_val,
        'direction_bull': direction_bull,
        'direction_bear': direction_bear
    }
    
    # CALL check (NO EMA)
    call_conditions_met = (
        touch_l and 
        (bull_eng or bull_hammer) and 
        rsi_val < cfg['filters']['rsi_oversold'] and
        direction_bull
    )
    
    # PUT check (NO EMA)
    put_conditions_met = (
        touch_h and 
        (bear_eng or bear_star) and 
        rsi_val > cfg['filters']['rsi_overbought'] and
        direction_bear
    )
    
    if call_conditions_met:
        return 'CALL', conditions_info
    elif put_conditions_met:
        return 'PUT', conditions_info
    else:
        # Log debug info for analysis
        if historical_index and historical_index % 100 == 0:  # Log every 100 candles for analysis
            print(f"Debug {symbol} index {historical_index}: {conditions_info}")
            print(f"  CALL conditions: touch_l={touch_l}, pattern={bull_eng or bull_hammer}, RSI={rsi_val:.1f}<{cfg['filters']['rsi_oversold']}, direction={direction_bull}")
            print(f"  PUT conditions: touch_h={touch_h}, pattern={bear_eng or bear_star}, RSI={rsi_val:.1f}>{cfg['filters']['rsi_overbought']}, direction={direction_bear}")
        return None, conditions_info






# Debug function to check signal conditions at specific points
def debug_signal_conditions(df, symbol, cfg, historical_index=None):
    """Debug function to see why signals aren't triggering"""
    if historical_index is not None:
        current_df = df.iloc[:historical_index+1]
    else:
        current_df = df
    
    if len(current_df) < 50:
        print(f"Not enough data: {len(current_df)} < 50")
        return
    
    touch_h, touch_l = triple_touch(current_df, symbol, cfg['filters']['min_touches'], cfg['filters']['touch_window_pips'])
    bull_eng, bear_eng = engulfing(current_df, cfg['patterns']['engulfing_min_ratio'])
    bull_hammer = hammer(current_df)
    bear_star   = shooting_star(current_df)
    rsi_val     = rsi(current_df)
    direction_bull = current_df['close'].iloc[-1] > current_df['open'].iloc[-1]
    direction_bear = current_df['close'].iloc[-1] < current_df['open'].iloc[-1]

    print(f"\n=== DEBUG Signal conditions for {symbol} at index {historical_index if historical_index else 'latest'} ===")
    print(f"Date: {current_df['timestamp'].iloc[-1] if 'timestamp' in current_df.columns else 'N/A'}")
    print(f"Price: {current_df['close'].iloc[-1]:.5f}")
    print(f"Touch High: {touch_h}, Touch Low: {touch_l}")
    print(f"Bull Engulfing: {bull_eng}, Bear Engulfing: {bear_eng}")
    print(f"Hummer: {bull_hammer}, Shooting Star: {bear_star}")
    print(f"RSI: {rsi_val:.2f} (Oversold<{cfg['filters']['rsi_oversold']}, Overbought>{cfg['filters']['rsi_overbought']})")
    print(f"Direction Bull: {direction_bull}, Direction Bear: {direction_bear}")
    
    # Check specific conditions (NO EMA)
    call_ok = all([
        touch_l,
        bull_eng or bull_hammer,
        rsi_val < cfg['filters']['rsi_oversold'],
        direction_bull
    ])
    
    put_ok = all([
        touch_h,
        bear_eng or bear_star,
        rsi_val > cfg['filters']['rsi_overbought'],
        direction_bear
    ])
    
    print(f"CALL conditions met: {call_ok}")
    print(f"PUT conditions met: {put_ok}")
    print("=" * 60)