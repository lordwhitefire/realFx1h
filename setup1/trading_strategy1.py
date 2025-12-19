import pandas as pd
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

def analyze_setups(df: pd.DataFrame, symbol: str, cfg: dict) -> list:
    """Analyse setups in the data and determine their results."""
    setups_found = []
    
    logging.info(f"Data length: {len(df)}")
    logging.info(f"Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    
    for i in range(51, len(df)):
        signal, conditions = get_signal(df, symbol, cfg, historical_index=i)
        if signal:
            result = check_setup_result(df, i, signal, cfg)
            
            setup_info = {
                'timestamp': df.iloc[i]['timestamp'],
                'symbol': symbol,
                'signal': signal,
                'result': result,
                'entry_price': float(df.iloc[i + 1]['open']),
                'expiry_price': float(df.iloc[i + 4]['open']),
                'conditions': conditions
            }
            setups_found.append(setup_info)
            
            logging.info(f"✅ SETUP FOUND at Candle B index {i}: {signal}")
            logging.info(f"   Candle A (setup): RSI={conditions['candle_a_rsi']:.1f}, Touch_L={conditions['candle_a_touch_l']}, Touch_H={conditions['candle_a_touch_h']}")
            
            pattern_type = conditions.get('triggered_pattern', 'Unknown')
            logging.info(f"   Triggered Pattern: {pattern_type}")
            
            available_patterns = []
            if conditions['candle_a_hammer']:
                available_patterns.append("Hammer")
            if conditions['candle_a_shooting_star']:
                available_patterns.append("Shooting Star")
            
            logging.info(f"   Available Patterns: {', '.join(available_patterns) if available_patterns else 'None'}")
            logging.info(f"   Candle B (confirm): Bullish={conditions['candle_b_bullish']}, Bearish={conditions['candle_b_bearish']}")
            logging.info(f"   Entry (Candle C open): {setup_info['entry_price']:.5f}")
            logging.info(f"   Expiry (Candle F open): {setup_info['expiry_price']:.5f}")
            logging.info(f"   Result: {result}")
            
    if len(setups_found) == 0:
        logging.info("No setups found. Running debug analysis...")
        for debug_i in range(max(51, len(df)-10), len(df)):
            debug_signal_conditions(df, symbol, cfg, historical_index=debug_i)
    
    logging.info(f"Total setups found: {len(setups_found)}")
    return setups_found

def check_setup_result(df: pd.DataFrame, signal_index: int, signal: str, cfg: dict) -> str:
    """Check the result of a setup (WIN or LOSS)."""
    if signal_index + 4 >= len(df):
        return 'UNDETERMINED'
    
    entry_price = float(df.iloc[signal_index + 1]['open'])
    expiry_price = float(df.iloc[signal_index + 4]['open'])
    
    if signal == 'CALL':
        return 'WIN' if expiry_price > entry_price else 'LOSS'
    elif signal == 'PUT':
        return 'WIN' if expiry_price < entry_price else 'LOSS'
    
    return 'UNDETERMINED'

def calculate_stats(setups: list) -> dict:
    """Calculate statistics from found setups."""
    if not setups:
        return {
            'total_setups': 0, 
            'win_rate': 0, 
            'wins': 0, 
            'losses': 0,
            'undetermined': 0
        }
    
    wins = len([s for s in setups if s['result'] == 'WIN'])
    losses = len([s for s in setups if s['result'] == 'LOSS'])
    undetermined = len([s for s in setups if s['result'] == 'UNDETERMINED'])
    total_evaluated = wins + losses

    win_rate = (wins / total_evaluated * 100) if total_evaluated > 0 else 0
    
    return {
        'total_setups': len(setups),
        'win_rate': win_rate,
        'wins': wins,
        'losses': losses,
        'undetermined': undetermined
    }

def send_analysis_report(bot, chat_id, symbol, setups, stats):
    if stats['total_setups'] == 0:
        msg = f"📊 {symbol} Analysis (15min binary)\nNo setups found in the data."
    else:
        msg = f"📊 {symbol} Setup Analysis (15min binary)\n"
        msg += f"Total Setups Found: {stats['total_setups']}\n"
        msg += f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
        msg += f"Win Rate: {stats['win_rate']:.1f}%\n"
        msg += f"Undetermined: {stats['undetermined']}\n\n"
        
        # Add recent setups
        msg += "Recent Setups:\n"
        for setup in setups[-5:]:
            msg += f"- {setup['timestamp'].strftime('%m/%d %H:%M')} {setup['signal']}: {setup['result']}\n"
    
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        logging.error(f"Telegram err: {e}")