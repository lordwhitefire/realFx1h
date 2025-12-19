import requests, pandas as pd, yaml, time, datetime, os, csv, logging
from telegram import Bot
from patterns import get_signal, debug_signal_conditions
from datetime import datetime as dt, timedelta

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
    url = f'https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=1000&apikey={TWELVE_KEY}'
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

# Analyze setups and determine win/loss for each
def analyze_setups(df, symbol, cfg):
    setups_found = []
    
    logging.info(f"Data length: {len(df)}")
    logging.info(f"Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    
    # Start from index 1 because we need Candle A (index-1) and Candle B (index)
    for i in range(51, len(df)):  # Start from 51 to ensure we have enough history
        # Get both signal AND conditions
        signal, conditions = get_signal(df, symbol, cfg, historical_index=i)
        
        if signal:
            result = check_setup_result(df, i, signal, cfg)
            
            setup_info = {
                'timestamp': df.iloc[i]['timestamp'],  # This is Candle B timestamp
                'symbol': symbol,
                'signal': signal,
                'result': result,
                'price_at_signal': float(df.iloc[i]['close']),  # Candle B close
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
    signal_index refers to CANDLE B (confirmation)
    - Candle A = signal_index - 1 (setup)
    - Candle B = signal_index (confirmation) 
    - Candle C = signal_index + 1 (entry at open)
    - Candle D = signal_index + 2 (expiry at open) - 10 minute trade
    """
    # We need Candle D for expiry
    if signal_index + 2 >= len(df):
        return 'UNDETERMINED'
    
    # Entry price = Candle C open
    entry_price = float(df.iloc[signal_index + 1]['open'])
    
    # Expiry price = Candle D open
    expiry_price = float(df.iloc[signal_index + 2]['open'])
    
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
        msg = f"📊 {symbol} Analysis (10min trade)\nNo setups found in the data."
    else:
        msg = f"📊 {symbol} Setup Analysis (10min trade)\n"
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

# One-shot analysis to check setups in the data
if __name__ == '__main__' and len(os.sys.argv) > 1 and os.sys.argv[1] == '--analyze-setups':
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']
    
    for sym in cfg['pairs']:
        df = fetch_5min(None, sym)
        if df is None or len(df) < 53:  # Need at least 53 for proper analysis
            logging.warning(f"Insufficient data for {sym}")
            continue

        logging.info(f"Analyzing setups for {sym}...")
        setups = analyze_setups(df, sym, cfg)
        stats = calculate_stats(setups)
        
        # Print to console
        logging.info(f"=== {sym} SETUP ANALYSIS (10min trade) ===")
        logging.info(f"Total setups: {stats['total_setups']}")
        logging.info(f"Win rate: {stats['win_rate']:.1f}%")
        logging.info(f"Wins: {stats['wins']}, Losses: {stats['losses']}")
        logging.info(f"Undetermined: {stats['undetermined']}")
        
        # Send report via Telegram
        send_analysis_report(bot, chat_id, sym, setups, stats)
        
        # Log individual setups
        for setup in setups:
            logging.info(f"Setup: {setup['timestamp']} {setup['signal']} -> {setup['result']}")
    
    logging.info("✅ Setup analysis finished.")
    exit(0)

# Live trading function for 5-minute alerts
def should_alert_5min(cfg):
    current_time = datetime.datetime.utcnow()
    # Alert in last 2 minutes of 5-minute candle (Candle B)
    return current_time.minute % 5 >= 3

def log_signal(symbol, direction):
    os.makedirs('logs', exist_ok=True)
    with open(f"logs/{symbol}_history.csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.date.today(), symbol, direction, ''])

def send_alert(bot, chat_id, msg):
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        logging.error(f"Telegram err: {e}")

# Main function for live trading
def main():
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']
    while True:
        if should_alert_5min(cfg):
            for sym in cfg['pairs']:
                df = fetch_5min(None, sym)
                if df is None or len(df) < 3:  # Need at least 3 candles
                    logging.warning(f"Insufficient data for {sym}")
                    continue

                # FIXED: Handle tuple return
                sig, conditions = get_signal(df, sym, cfg)
                if sig:
                    msg = f"🔥 {sym} → {sig} (10min binary - entry next candle!) {datetime.datetime.utcnow().strftime('%H:%M')} UTC"
                    logging.info(msg)
                    send_alert(bot, chat_id, msg)
                    log_signal(sym, sig)
                else:
                    logging.info(f"{sym}: no signal")
        time.sleep(30)

if __name__ == '__main__':
    main()