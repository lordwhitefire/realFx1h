import requests
import pandas as pd
import yaml
import logging
from telegram import Bot
import sys
import os
from datetime import datetime, timedelta
import time

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

# Load main configuration
def load_config():
    with open('config.yaml') as f:
        return yaml.safe_load(f)

# Fetch 5-minute data from Twelve Data API
def fetch_5min(symbol: str) -> pd.DataFrame:
    TWELVE_KEY = 'your_api_key_here'
    url = f'https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=2000&apikey={TWELVE_KEY}'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data['status'] != 'ok':
            raise RuntimeError(data['message'])
        df = pd.DataFrame(data['values']).iloc[::-1].reset_index(drop=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        df['volume'] = 0.0
        return df
    except Exception as e:
        logging.error(f'Twelve Data fetch fail {symbol}: {e}')
        return None

# Load setup-specific configuration
def load_setup_config(setup_dir: str) -> dict:
    with open(os.path.join(setup_dir, 'setup.yaml')) as f:
        return yaml.safe_load(f)

# Run a specific setup
def run_setup(df: pd.DataFrame, symbol: str, setup_dir: str) -> dict:
    setup_cfg = load_setup_config(setup_dir)
    strategy_module = __import__(f'{setup_dir}.trading_strategy', fromlist=['trading_strategy'])
    setups = strategy_module.analyze_setups(df, symbol, setup_cfg)
    stats = strategy_module.calculate_stats(setups)
    return {
        'symbol': symbol,
        'setups': setups,
        'stats': stats
    }

# Send analysis report via Telegram
def send_analysis_report(bot: Bot, chat_id: str, symbol: str, setups: list, stats: dict, setup_name: str):
    msg = (f"📊 {symbol} 15-min binary back-test ({setup_name})\n"
           f"Setups: {stats['total']}  Wins: {stats['wins']}  Losses: {stats['losses']}\n"
           f"Win-rate: {stats['win_rate']:.1f}%")
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        logging.error(f'Telegram err: {e}')

# Main function to run the script
def main():
    cfg = load_config()
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = cfg['telegram']['chat_id']

    # --- live trading ---
    last_alert = {}  # sym -> dt
    while True:
        for sym in cfg['pairs']:
            df = fetch_5min(sym)
            if df is None or len(df) < 50:
                continue
            for setup_dir in ['setup1', 'setup2']:
                strategy_module = __import__(f'{setup_dir}.trading_strategy', fromlist=['trading_strategy'])
                signal, cond = strategy_module.get_signal(df, sym, load_setup_config(setup_dir))
                if signal:
                    now = datetime.utcnow()
                    if (now - last_alert.get(sym, datetime.min)).seconds < 60:
                        continue
                    last_alert[sym] = now
                    msg = strategy_module.alert_msg(sym, signal, cond['rsi'])
                    logging.info(msg)
                    try:
                        bot.send_message(chat_id=chat_id, text=msg)
                    except:
                        pass
                    strategy_module.log_alert(sym, signal, cond['rsi'])
                    strategy_module.beep()
        time.sleep(300)  # Sleep for 5 minutes

if __name__ == '__main__':
    main()