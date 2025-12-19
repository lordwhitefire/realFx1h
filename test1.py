import requests, pandas as pd, yaml, time, datetime, os, csv, logging
from telegram import Bot
from pattern import get_signal, debug_signal_conditions
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
    
    for i in range(50, len(df)):
        historical_df = df.iloc[:i+1].copy()
        
        # Get both signal AND conditions
        signal, conditions = get_signal(historical_df, symbol, cfg, historical_index=i)
        
        if signal:
            result = check_setup_result(df, i, signal, cfg)
            
            setup_info = {
                'timestamp': df.iloc[i]['timestamp'],
                'symbol': symbol,
                'signal': signal,
                'result': result,
                'price_at_signal': float(df.iloc[i]['close']),
                'conditions': conditions  # Add conditions here
            }
            setups_found.append(setup_info)
            
            # Log the conditions that triggered the setup
            logging.info(f"✅ SETUP FOUND at index {i}: {signal}")
            logging.info(f"   Conditions: {conditions}")
            logging.info(f"   Result: {result}")
            
        elif i % 100 == 0:
            logging.debug(f"Checked index {i}, no signal yet...")
    
    # Debug: check why no signals found
    if len(setups_found) == 0:
        logging.info("No setups found. Running debug analysis...")
        # Check last few candles to see why no signals
        for debug_i in range(len(df)-10, len(df)):
            debug_signal_conditions(df, symbol, cfg, historical_index=debug_i)
    
    logging.info(f"Total setups found: {len(setups_found)}")
    return setups_found

def check_setup_result(df, signal_index, signal, cfg):
    """
    Check if a historical setup was a win or loss for binary options
    A win = price is in the correct direction at expiry (next candle close)
    A loss = price is in the wrong direction at expiry (next candle close)
    """
    # For binary options, we only look at the next candle close
    if signal_index + 1 >= len(df):
        return 'UNDETERMINED'  # No next candle available
    
    entry_price = float(df.iloc[signal_index]['close'])
    expiry_price = float(df.iloc[signal_index + 1]['close'])  # Next candle close
    
    if signal == 'CALL':
        # WIN if price went UP by expiry
        return 'WIN' if expiry_price > entry_price else 'LOSS'
    elif signal == 'PUT':
        # WIN if price went DOWN by expiry  
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
        msg = f"📊 {symbol} Analysis (5min)\nNo setups found in the data."
    else:
        msg = f"📊 {symbol} Setup Analysis (5min)\n"
        msg += f"Total Setups Found: {stats['total_setups']}\n"
        msg += f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
        msg += f"Win Rate: {stats['win_rate']:.1f}%\n"
        msg += f"Undetermined: {stats['undetermined']}\n\n"
        
        # Add recent setups
        msg += "Recent Setups:\n"
        for setup in setups[-5:]:  # Last 5 setups
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
        if df is None or len(df) < 50:
            logging.warning(f"Insufficient data for {sym}")
            continue

        logging.info(f"Analyzing setups for {sym}...")
        setups = analyze_setups(df, sym, cfg)
        stats = calculate_stats(setups)
        
        # Print to console
        logging.info(f"=== {sym} SETUP ANALYSIS (5min) ===")
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
    # Alert in last 2 minutes of 5-minute candle
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
                if df is None or len(df) < 30:
                    logging.warning(f"Insufficient data for {sym}")
                    continue

                sig = get_signal(df, sym, cfg)
                if sig:
                    msg = f"🔥 {sym} → {sig} (5min binary NOW!) {datetime.datetime.utcnow().strftime('%H:%M')} UTC"
                    logging.info(msg)
                    send_alert(bot, chat_id, msg)
                    log_signal(sym, sig)
                else:
                    logging.info(f"{sym}: no signal")
        time.sleep(30)

if __name__ == '__main__':
    main()