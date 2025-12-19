import requests
import pandas as pd
import yaml
import time
import datetime
import os
import csv
import logging
from telegram import Bot
from datetime import datetime as dt, timedelta
import sys
from custom_pattern_strategy import get_signal  # Use the fixed version

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

# ---------- helpers ----------
def load_config():
    """Load configuration from YAML file."""
    with open('config.yaml') as f:
        return yaml.safe_load(f)

def fetch_5min(_, symbol: str) -> pd.DataFrame:
    """Fetch 5-minute candlestick data from Twelve Data API."""
    TWELVE_KEY = '51028f824e8e41c898d2205c4ac746dc'
    url = f'https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=2000&apikey={TWELVE_KEY}'
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data['status'] != 'ok':
            raise RuntimeError(data['message'])
        df = (pd.DataFrame(data['values']).iloc[::-1].reset_index(drop=True)
              .rename(columns={'datetime': 'timestamp'}))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        df['volume'] = 0.0
        return df
    except Exception as e:
        logging.error(f'Twelve Data fetch fail {symbol}: {e}')
        return None

# ---------- back-test ----------
def check_setup_result(df: pd.DataFrame, idx: int, signal: str) -> str:
    """Check the result of a setup (WIN or LOSS)."""
    # idx = candle-B (confirmation), entry = candle-C open, expiry = candle-F open
    if idx + 4 >= len(df):
        return 'UNDETERMINED'
    entry = float(df.iloc[idx + 1]['open'])
    expiry = float(df.iloc[idx + 4]['open'])
    return 'WIN' if (signal == 'CALL' and expiry > entry) or (signal == 'PUT' and expiry < entry) else 'LOSS'

def analyse_setups(df: pd.DataFrame, symbol: str, cfg: dict) -> list:
    """Analyse setups in the data and determine their results."""
    setups = []
    for i in range(51, len(df)):
        signal, cond = get_signal(df, symbol, cfg, historical_index=i)
        if signal:
            result = check_setup_result(df, i, signal)
            setups.append({
                'timestamp': df.iloc[i]['timestamp'],
                'symbol': symbol,
                'signal': signal,
                'result': result,
                'entry': float(df.iloc[i+1]['open']),
                'exit': float(df.iloc[i+4]['open']),
                'conditions': cond
            })
            
            # Print conditions and result
            logging.info(f"Setup found at {df.iloc[i]['timestamp']} for {symbol}")
            logging.info(f"Signal: {signal}")
            logging.info(f"Conditions: {cond}")
            logging.info(f"Result: {result}")
            logging.info(f"Entry Price: {float(df.iloc[i+1]['open'])}")
            logging.info(f"Exit Price: {float(df.iloc[i+4]['open'])}")
            logging.info(f"Win/Loss: {'WIN' if result == 'WIN' else 'LOSS'}")
            logging.info("-" * 50)
    return setups

def calc_stats(setups: list) -> dict:
    """Calculate statistics from found setups."""
    wins = losses = 0
    for s in setups:
        if s['result'] == 'WIN': wins += 1
        elif s['result'] == 'LOSS': losses += 1
    total = wins + losses
    return {'total': len(setups), 'win_rate': (wins/total*100) if total else 0,
            'wins': wins, 'losses': losses}

def send_report(bot: Bot, chat_id: str, sym: str, setups: list, stats: dict):
    """Send analysis report via Telegram."""
    msg = (f"📊 {sym} 15-min binary back-test\n"
           f"Setups: {stats['total']}  Wins: {stats['wins']}  Losses: {stats['losses']}\n"
           f"Win-rate: {stats['win_rate']:.1f}%")
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        logging.error(f'Telegram err: {e}')

# ---------- live ----------
def should_check() -> bool:
    """Check if it's time to check for setups."""
    t = datetime.datetime.utcnow()
    return (t.minute % 5 == 4) and (t.second <= 30)

def sleep_until_next() -> int:
    """Calculate seconds to sleep until the next check time."""
    now = datetime.datetime.utcnow()
    nxt = (now + timedelta(minutes=5)).replace(second=0, microsecond=0)
    if nxt.minute % 5 != 4:
        nxt = nxt.replace(minute=(nxt.minute//5)*5 + 4)
    secs = max(5, (nxt - now).total_seconds())
    return int(secs)

def alert_msg(sym: str, signal: str, rsi: float) -> str:
    """Create an alert message for a setup."""
    now = datetime.datetime.utcnow()
    return (f"🔔 {sym}  {signal}  RSI:{rsi:.1f}  "
            f"({now.strftime('%H:%M')} UTC)")

def log_alert(sym: str, signal: str, rsi: float):
    """Log an alert to a CSV file."""
    os.makedirs('logs', exist_ok=True)
    fn = f'logs/{sym}_alerts.csv'
    hdr = not os.path.isfile(fn)
    with open(fn, 'a', newline='') as f:
        w = csv.writer(f)
        if hdr:
            w.writerow(['date','time','symbol','signal','rsi'])
        w.writerow([datetime.date.today(),
                    datetime.datetime.now().strftime('%H:%M:%S'),
                    sym, signal, f'{rsi:.1f}'])

def beep():
    """Play a system beep sound."""
    try:
        if sys.platform in ('linux','darwin'):
            os.system('printf "\a"')
        elif sys.platform == 'win32':
            import winsound
            winsound.Beep(1000, 300)
    except:
        pass

# ---------- main ----------
def main():
    """Main function to run the script."""
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']

    # --- one-shot back-test ---
    if len(sys.argv) > 1 and sys.argv[1] == '--analyse':
        for sym in cfg['pairs']:
            df = fetch_5min(None, sym)
            if df is None or len(df) < 55:
                logging.warning(f'Insufficient data for {sym}')
                continue
            setups = analyse_setups(df, sym, cfg['custom_setup'])  # Pass custom_setup
            stats  = calc_stats(setups)
            logging.info(f'{sym}  setups:{stats["total"]}  win-rate:{stats["win_rate"]:.1f}%')
            send_report(bot, chat_id, sym, setups, stats)
        logging.info('Back-test finished.')
        return

    # --- live loop ---
    last_alert = {}  # sym -> dt
    while True:
        if should_check():
            for sym in cfg['pairs']:
                df = fetch_5min(None, sym)
                if df is None or len(df) < 50:
                    continue
                signal, cond = get_signal(df, sym, cfg['custom_setup'])  # Pass custom_setup
                if signal:
                    now = datetime.datetime.utcnow()
                    if (now - last_alert.get(sym, datetime.datetime.min)).seconds < 60:
                        continue
                    last_alert[sym] = now
                    msg = alert_msg(sym, signal, cond['rsi'])
                    logging.info(msg)
                    try:
                        bot.send_message(chat_id=chat_id, text=msg)
                    except:
                        pass
                    log_alert(sym, signal, cond['rsi'])
                    beep()
        time.sleep(sleep_until_next())

if __name__ == '__main__':
    main()