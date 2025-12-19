import requests, pandas as pd, yaml, time, datetime, os, csv, logging
from telegram import Bot
from patterns import get_signal
from datetime import datetime as dt

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

# Twelve Data API key
TWELVE_KEY = '51028f824e8e41c898d2205c4ac746dc'  # <── your real key

# Load configuration from YAML file
def load_config():
    with open('config.yaml') as f:
        return yaml.safe_load(f)

# Fetch 1-hour data from Twelve Data API (no volume)
def fetch_1h(_, symbol):
    url = f'https://api.twelvedata.com/time_series?symbol={symbol}&interval=1h&outputsize=50&apikey={TWELVE_KEY}'
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

# Backtest hit rate for the last 10 setups
def backtest_hit_rate(symbol, direction, cfg):
    hist_file = f"logs/{symbol}_history.csv"
    if not os.path.exists(hist_file):
        return 100.0
    df = pd.read_csv(hist_file, names=['date', 'symbol', 'signal', 'result'])
    df = df[df['symbol'] == symbol]
    df = df[df['signal'] == direction].tail(cfg['history']['lookback_setups'])
    if len(df) < cfg['history']['lookback_setups']:
        return 100.0
    return (df['result'] == 1).sum() / len(df) * 100

# Log the signal to a CSV file
def log_signal(symbol, direction):
    os.makedirs('logs', exist_ok=True)
    with open(f"logs/{symbol}_history.csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.date.today(), symbol, direction, ''])

# Send an alert via Telegram
def send_alert(bot, chat_id, msg):
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        logging.error(f"Telegram err: {e}")

# Check if it's time to send an alert
def should_alert(cfg):
    return datetime.datetime.utcnow().minute >= 60 - cfg['filters']['alert_window_min']

# One-shot test to check the script
if __name__ == '__main__' and len(os.sys.argv) > 1 and os.sys.argv[1] == '--test-once':
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']
    for sym in cfg['pairs']:
        df = fetch_1h(None, sym)
        if df is None or len(df) < 30:
            logging.warning(f"Insufficient data for {sym}")
            continue

        sig = get_signal(df, sym, cfg)
        if sig:
            hit_rate = backtest_hit_rate(sym, sig, cfg)
            if hit_rate >= cfg['history']['min_win_rate'] * 100:
                msg = f"🔥 {sym} → {sig} (1h binary NOW!) {datetime.datetime.utcnow().strftime('%H:%M')} UTC\nLast 10 identical: {hit_rate:.0f}% win"
                logging.info(msg)
                send_alert(bot, chat_id, msg)
            else:
                logging.info(f"Suppressed {sym} {sig} (WR {hit_rate:.0f}% < 68%)")
        else:
            logging.info(f"{sym}: no signal")
    logging.info("✅ One-shot test finished.")
    exit(0)

# Main function to run the bot
def main():
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']
    while True:
        if should_alert(cfg):
            for sym in cfg['pairs']:
                df = fetch_1h(None, sym)
                if df is None or len(df) < 30:
                    logging.warning(f"Insufficient data for {sym}")
                    continue

                sig = get_signal(df, sym, cfg)
                if sig:
                    hit_rate = backtest_hit_rate(sym, sig, cfg)
                    if hit_rate >= cfg['history']['min_win_rate'] * 100:
                        msg = f"🔥 {sym} → {sig} (1h binary NOW!) {datetime.datetime.utcnow().strftime('%H:%M')} UTC\nLast 10 identical: {hit_rate:.0f}% win"
                        logging.info(msg)
                        send_alert(bot, chat_id, msg)
                        log_signal(sym, sig)
                    else:
                        logging.info(f"Suppressed {sym} {sig} (WR {hit_rate:.0f}% < 68%)")
        time.sleep(30)

if __name__ == '__main__':
    main()