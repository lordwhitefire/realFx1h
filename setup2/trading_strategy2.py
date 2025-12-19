import pandas as pd
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

def analyze_setups(df: pd.DataFrame, symbol: str, cfg: dict) -> list:
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

def check_setup_result(df: pd.DataFrame, idx: int, signal: str) -> str:
    """Check the result of a setup (WIN or LOSS)."""
    if idx + 4 >= len(df):
        return 'UNDETERMINED'
    entry = float(df.iloc[idx + 1]['open'])
    expiry = float(df.iloc[idx + 4]['open'])
    return 'WIN' if (signal == 'CALL' and expiry > entry) or (signal == 'PUT' and expiry < entry) else 'LOSS'

def calculate_stats(setups: list) -> dict:
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