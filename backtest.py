import requests, pandas as pd, yaml, time, datetime, os, csv, logging
from telegram import Bot
from patterns import get_signal, debug_signal_conditions, detect_setup_only, get_support_resistance_price
from datetime import datetime as dt, timedelta
import sys



# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

# Twelve Data API key
TWELVE_KEY = '51028f824e8e41c898d2205c4ac746dc'

# Load configuration from YAML file
def load_config():
    with open('config.yaml') as f:
        return yaml.safe_load(f)

# Fetch 5-minute data from Twelve Data API
def fetch_5min(_, symbol):
    url = f'https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=2000&apikey={TWELVE_KEY}'
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data['status'] != 'ok':
            raise RuntimeError(data['message'])
        df = pd.DataFrame(data['values']).iloc[::-1].reset_index(drop=True)
        df = df[['datetime', 'open', 'high', 'low', 'close']].rename(columns={'datetime': 'timestamp'})
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
        df['volume'] = 0.0  # Add zero-volume column
        return df
    except Exception as e:
        logging.error(f"Twelve Data fetch fail {symbol}: {e}")
        return None

# Analyze setups and determine win/loss for each (BACKTEST MODE)
def analyze_setups(df, symbol, cfg):
    setups_found = []
    
    logging.info(f"Data length: {len(df)}")
    logging.info(f"Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    
    # Start from index 1 because we need Candle A (index-1) and Candle B (index)
    for i in range(51, len(df)):  # Start from 51 to ensure we have enough history
        # Get both signal AND conditions (checks Candle A setup + Candle B confirmation)
        signal, conditions = get_signal(df, symbol, cfg, historical_index=i)
        
        if signal:
            result = check_setup_result(df, i, signal, cfg)
            
            setup_info = {
                'timestamp': df.iloc[i]['timestamp'],  # This is Candle B timestamp
                'symbol': symbol,
                'signal': signal,
                'result': result,
                'entry_price': float(df.iloc[i + 1]['open']),  # Candle C open (entry)
                'expiry_price': float(df.iloc[i + 4]['open']),  # Candle F open (expiry)
                'conditions': conditions
            }
            setups_found.append(setup_info)
            
            # Log the conditions that triggered the setup
            logging.info(f"✅ SETUP FOUND at Candle B index {i}: {signal}")
            logging.info(f"   Candle A (setup): RSI={conditions['candle_a_rsi']:.1f}, Touch_L={conditions['candle_a_touch_l']}, Touch_H={conditions['candle_a_touch_h']}")
            
            # Show the actual pattern that triggered
            pattern_type = conditions.get('triggered_pattern', 'Unknown')
            logging.info(f"   Triggered Pattern: {pattern_type}")
            
            # Show available patterns for debugging (ONLY Hammer and Shooting Star)
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
            
        elif i % 100 == 0:
            logging.debug(f"Checked index {i}, no signal yet...")
    
    # Debug: check why no signals found
    if len(setups_found) == 0:
        logging.info("No setups found. Running debug analysis...")
        # Check last few candles to see why no signals
        for debug_i in range(max(51, len(df)-10), len(df)):
            debug_signal_conditions(df, symbol, cfg, historical_index=debug_i)
    
    logging.info(f"Total setups found: {len(setups_found)}")
    return setups_found

def check_setup_result(df, signal_index, signal, cfg):
    """
    BACKTEST MODE: Entry at Candle C open, Expiry at Candle F open (15 minutes)
    signal_index refers to CANDLE B (confirmation)
    - Candle A = signal_index - 1 (setup)
    - Candle B = signal_index (confirmation) 
    - Candle C = signal_index + 1 (entry at OPEN)
    - Candle F = signal_index + 4 (expiry at OPEN) - 15 minute trade
    """
    # We need Candle F for 15-minute expiry (4 candles after Candle B)
    if signal_index + 4 >= len(df):
        return 'UNDETERMINED'
    
    # Entry price = Candle C OPEN (when we would enter the binary option)
    entry_price = float(df.iloc[signal_index + 1]['open'])
    
    # Expiry price = Candle F OPEN (15 minutes later = 3 candles after entry)
    expiry_price = float(df.iloc[signal_index + 4]['open'])
    
    if signal == 'CALL':
        return 'WIN' if expiry_price > entry_price else 'LOSS'
    elif signal == 'PUT':
        return 'WIN' if expiry_price < entry_price else 'LOSS'
    
    return 'UNDETERMINED'

# Calculate statistics from found setups
def calculate_stats(setups):
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

# Send analysis report via Telegram
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

        
# One-shot analysis to check setups in the data (BACKTEST MODE)
if __name__ == '__main__' and len(os.sys.argv) > 1 and os.sys.argv[1] == '--analyze-setups':
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']
    
    for sym in cfg['pairs']:
        df = fetch_5min(None, sym)
        if df is None or len(df) < 58:  # Need at least 58 for proper analysis (Candle A + B + C + D + E + F)
            logging.warning(f"Insufficient data for {sym}")
            continue

        logging.info(f"Analyzing setups for {sym}...")
        setups = analyze_setups(df, sym, cfg)
        stats = calculate_stats(setups)
        
        # Print to console
        logging.info(f"=== {sym} SETUP ANALYSIS (15min binary - Entry at Candle C open) ===")
        logging.info(f"Total setups: {stats['total_setups']}")
        logging.info(f"Win rate: {stats['win_rate']:.1f}%")
        logging.info(f"Wins: {stats['wins']}, Losses: {stats['losses']}")
        logging.info(f"Undetermined: {stats['undetermined']}")
        
        # Send report via Telegram
        send_analysis_report(bot, chat_id, sym, setups, stats)
        
        # Log individual setups
        for setup in setups:
            entry_time = (setup['timestamp'] + timedelta(minutes=5)).strftime('%H:%M')
            expiry_time = (setup['timestamp'] + timedelta(minutes=20)).strftime('%H:%M')
            logging.info(f"Setup: {setup['timestamp'].strftime('%m/%d %H:%M')} {setup['signal']} -> Entry: {entry_time}, Expiry: {expiry_time}, Result: {setup['result']}")
    
    logging.info("✅ Setup analysis finished.")
    exit(0)

# LIVE TRADING FUNCTIONS
def should_check_for_setup():
    """
    Check at exact 5-minute candle close times
    Candles close at minutes ending in 4 and 9 (00:04, 00:09, 00:14, 00:19, etc.)
    """
    current_time = datetime.datetime.utcnow()
    minute = current_time.minute
    second = current_time.second
    
    # 5-minute candles close at minutes ending in 4 and 9
    # Check within first 30 seconds after candle close
    return (minute % 5 == 4) and (second <= 30)

def get_sleep_seconds():
    """Calculate seconds to sleep until next check time"""
    current = datetime.datetime.utcnow()
    minute = current.minute
    second = current.second
    
    # Next 5-minute candle closes at next minute ending in 4 or 9
    next_check_minute = ((minute // 5) * 5) + 4
    if next_check_minute <= minute:
        next_check_minute += 5
    
    # Create datetime for next check
    next_check = current.replace(minute=next_check_minute, second=0, microsecond=0)
    sleep_seconds = (next_check - current).total_seconds()
    
    # Sleep at least 5 seconds
    return max(5, sleep_seconds)


def get_support_resistance_price(df, symbol, cfg, conditions):
    """
    Extract the S/R price level that was touched
    Returns: (price_level, level_type)
    """
    # This needs to be implemented based on your triple_touch function
    # For now, return approximate level based on candle A
    if conditions['candle_a_touch_l']:
        # Support level (for CALL signals)
        return float(df.iloc[-2]['low']), 'Support'
    elif conditions['candle_a_touch_h']:
        # Resistance level (for PUT signals)
        return float(df.iloc[-2]['high']), 'Resistance'
    return None, None

def create_alert_message(symbol, signal, conditions, df):
    """
    Create detailed alert message for live trading
    """
    current_time = datetime.datetime.utcnow()
    
    # Calculate times
    entry_time = (current_time + timedelta(minutes=5)).strftime('%H:%M')
    expiry_time = (current_time + timedelta(minutes=20)).strftime('%H:%M')
    
    # Get S/R price if available
    sr_price, sr_type = get_support_resistance_price(df, symbol, cfg, conditions)
    
    # Build message
    msg = f"🔔 SETUP ALERT: {symbol}\n"
    msg += f"Signal: {signal}\n"
    msg += f"Pattern: {conditions.get('triggered_pattern', 'Unknown')}\n"
    msg += f"RSI: {conditions['candle_a_rsi']:.1f}\n"
    
    if sr_price and sr_type:
        msg += f"{sr_type}: {sr_price:.5f}\n"
    
    msg += f"Setup Candle: {df.iloc[-2]['timestamp'].strftime('%H:%M')}\n"
    msg += f"Entry: Next candle open (~{entry_time} UTC)\n"
    msg += f"Expiry: 15min later ({expiry_time} UTC)\n"
    msg += f"Alert Time: {current_time.strftime('%H:%M:%S')} UTC"
    
    return msg

def log_signal(symbol, direction, conditions):
    os.makedirs('logs', exist_ok=True)
    log_file = f"logs/{symbol}_alerts.csv"
    file_exists = os.path.isfile(log_file)
    
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Date', 'Time', 'Symbol', 'Signal', 'Pattern', 'RSI', 'Touch_H', 'Touch_L'])
        
        writer.writerow([
            datetime.date.today(),
            datetime.datetime.now().strftime('%H:%M:%S'),
            symbol,
            direction,
            conditions.get('triggered_pattern', ''),
            f"{conditions['candle_a_rsi']:.1f}",
            conditions['candle_a_touch_h'],
            conditions['candle_a_touch_l']
        ])

def send_alert(bot, chat_id, msg):
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        logging.error(f"Telegram err: {e}")

def play_alarm():
    """Play system beep sound"""
    try:
        # For Linux/Mac
        if sys.platform == 'linux' or sys.platform == 'darwin':
            os.system('echo -e "\a"')  # System beep
            os.system('play -n synth 0.5 sin 880')  # Optional: more noticeable beep
        # For Windows
        elif sys.platform == 'win32':
            import winsound
            winsound.Beep(1000, 500)  # Frequency 1000Hz, duration 500ms
    except:
        pass  # Silently fail if sound not available




# Main function for live trading (LIVE MODE)

def main():
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']
    
    # Track last alert time per symbol to avoid duplicates
    last_alert_times = {}
    
    while True:
        if should_check_for_setup():
            for sym in cfg['pairs']:
                df = fetch_5min(None, sym)
                if df is None or len(df) < 2:  # Need at least 2 candles
                    logging.warning(f"Insufficient data for {sym}")
                    continue
                
                # Check for setup on Candle A ONLY (no confirmation needed)
                signal, conditions = detect_setup_only(df, sym, cfg)
                
                if signal:
                    # Check if we already alerted for this setup (avoid duplicates)
                    current_time = datetime.datetime.utcnow()
                    last_alert = last_alert_times.get(sym)
                    
                    if last_alert and (current_time - last_alert).total_seconds() < 60:
                        # Alerted within last minute, skip
                        continue
                    
                    # Create detailed alert message
                    msg = create_alert_message(sym, signal, conditions, df)
                    logging.info(f"🔔 LIVE ALERT: {sym} → {signal}")
                    send_alert(bot, chat_id, msg)
                    log_signal(sym, signal, conditions)
                    
                    # PLAY PC ALARM
                    play_alarm()
                    # Update last alert time
                    last_alert_times[sym] = current_time
                else:
                    logging.debug(f"{sym}: no setup at {datetime.datetime.utcnow().strftime('%H:%M:%S')}")
        
        # OPTIMIZED: Sleep until next check time
        time.sleep(get_sleep_seconds())

if __name__ == '__main__':
    main()
