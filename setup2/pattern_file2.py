import pandas as pd
import numpy as np

def pip_size(symbol: str) -> float:
    """Return the pip size for a given symbol."""
    return 0.01 if 'JPY' in symbol else 0.0001

def triple_touch(df: pd.DataFrame, symbol: str, touches: int = 3, window: int = 15) -> tuple:
    """Check for triple touch on support or resistance levels."""
    pips = pip_size(symbol) * window
    highs = df['high'].rolling(50).max()
    lows = df['low'].rolling(50).min()
    touch_h = ((df['high'] >= highs - pips) & (df['high'] <= highs + pips)).rolling(30).sum()
    touch_l = ((df['low'] >= lows - pips) & (df['low'] <= lows + pips)).rolling(30).sum()
    return touch_h.iloc[-1] >= touches, touch_l.iloc[-1] >= touches

def engulfing(df: pd.DataFrame, ratio: float = 1.3) -> tuple:
    """Check for engulfing patterns."""
    if len(df) < 2:
        return False, False
    prev_body = abs(df['close'].iloc[-2] - df['open'].iloc[-2])
    curr_body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    bull = (df['close'].iloc[-1] > df['open'].iloc[-1]) and (df['close'].iloc[-2] < df['open'].iloc[-2])
    bull = bull and (curr_body > ratio * prev_body)
    bear = (df['close'].iloc[-1] < df['open'].iloc[-1]) and (df['close'].iloc[-2] > df['open'].iloc[-2])
    bear = bear and (curr_body > ratio * prev_body)
    return bull, bear

def is_pin_bar(df: pd.DataFrame, bullish: bool) -> bool:
    """Check for pin bar patterns."""
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    lower_shadow = min(df['close'].iloc[-1], df['open'].iloc[-1]) - df['low'].iloc[-1]
    upper_shadow = df['high'].iloc[-1] - max(df['close'].iloc[-1], df['open'].iloc[-1])
    if bullish:
        return (lower_shadow > 2 * body) and (upper_shadow < body) and (df['close'].iloc[-1] > df['open'].iloc[-1])
    else:
        return (upper_shadow > 2 * body) and (lower_shadow < body) and (df['close'].iloc[-1] < df['open'].iloc[-1])

def is_doji(df: pd.DataFrame, symbol: str) -> bool:
    """Check for doji patterns."""
    if len(df) < 1:
        return False
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    return body < pip_size(symbol) * 10

def rsi(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate the Relative Strength Index (RSI)."""
    if len(df) < period:
        raise ValueError("Insufficient data for RSI calculation")
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.iloc[-1]

def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> tuple:
    """Calculate Bollinger Bands."""
    if len(df) < period:
        raise ValueError("Insufficient data for Bollinger Bands calculation")
    rolling_mean = df['close'].rolling(window=period).mean()
    rolling_std = df['close'].rolling(window=period).std()
    upper_band = rolling_mean + (rolling_std * std_dev)
    lower_band = rolling_mean - (rolling_std * std_dev)
    return upper_band.iloc[-1], rolling_mean.iloc[-1], lower_band.iloc[-1]

def get_signal(df: pd.DataFrame, symbol: str, cfg: dict, historical_index: int = None) -> tuple:
    """Generate trading signals based on the provided configuration."""
    if historical_index is not None:
        current_df = df.iloc[:historical_index+1]
    else:
        current_df = df

    if len(current_df) < 50:
        return None, {}

    touch_h, touch_l = triple_touch(current_df, symbol,
                                    cfg['filters']['min_touches'],
                                    cfg['filters']['touch_window_pips'])

    bull_eng, bear_eng = engulfing(current_df,
                                   cfg['patterns']['engulfing_min_ratio'])

    bull_pin = is_pin_bar(current_df, True)
    bear_pin = is_pin_bar(current_df, False)
    bull_doji = is_doji(current_df, symbol)
    bear_doji = is_doji(current_df, symbol)

    rsi_val = rsi(current_df, cfg['technical_indicators']['rsi']['period'])
    upper_bb, mid_bb, lower_bb = bollinger_bands(
        current_df,
        cfg['technical_indicators']['bollinger_bands']['period'],
        cfg['technical_indicators']['bollinger_bands']['std_dev'])

    close = current_df['close'].iloc[-1]
    open_ = current_df['open'].iloc[-1]
    direction_bull = close > open_
    direction_bear = close < open_

    conditions_info = {
        'touch_h': touch_h,
        'touch_l': touch_l,
        'bull_eng': bull_eng,
        'bear_eng': bear_eng,
        'bull_pin': bull_pin,
        'bear_pin': bear_pin,
        'bull_doji': bull_doji,
        'bear_doji': bear_doji,
        'rsi': rsi_val,
        'upper_bb': upper_bb,
        'mid_bb': mid_bb,
        'lower_bb': lower_bb,
        'direction_bull': direction_bull,
        'direction_bear': direction_bear
    }

    call_ok = (touch_l and
               (bull_eng or bull_pin or bull_doji) and
               rsi_val < cfg['technical_indicators']['rsi']['oversold'] and
               direction_bull and
               close < lower_bb)

    put_ok = (touch_h and
              (bear_eng or bear_pin or bear_doji) and
              rsi_val > cfg['technical_indicators']['rsi']['overbought'] and
              direction_bear and
              close > upper_bb)

    if call_ok:
        return 'CALL', conditions_info
    if put_ok:
        return 'PUT', conditions_info
    return None, conditions_info