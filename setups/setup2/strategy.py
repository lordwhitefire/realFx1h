"""
Strategy Module for Setup2
Defines entry, exit, and risk management rules for MA Crossover Momentum setup
"""
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np


def apply_strategy(pattern_result: Dict[str, Any], 
                  data: pd.DataFrame, 
                  symbol: str,
                  global_config: Dict[str, Any], 
                  setup_config: Dict[str, Any],
                  mode: str = 'live') -> Dict[str, Any]:
    """
    Apply trading strategy rules to pattern signal
    
    Args:
        pattern_result: Pattern detection result
        data: Market data DataFrame
        symbol: Trading symbol
        global_config: Global configuration
        setup_config: Setup-specific configuration
        mode: Trading mode ('live' or 'backtest')
        
    Returns:
        Dict with strategy application results
    """
    if not pattern_result:
        return {}
    
    # Extract pattern info
    signal_type = pattern_result.get('signal_type')
    confidence = pattern_result.get('confidence', 0)
    
    # Get configuration
    trade_type = setup_config.get('trade_type', 'binary_options')
    
    strategy_result = {}
    
    if trade_type == 'binary_options':
        strategy_result = _apply_binary_options_strategy(
            pattern_result, data, symbol, global_config, setup_config, mode
        )
    else:
        strategy_result = _apply_regular_trading_strategy(
            pattern_result, data, symbol, global_config, setup_config, mode
        )
    
    # Add common strategy metrics
    strategy_result.update({
        'trade_type': trade_type,
        'strategy_applied': True,
        'strategy_name': 'MA_Crossover_Momentum_Strategy',
        'applied_at': datetime.now().isoformat()
    })
    
    return strategy_result


def _apply_binary_options_strategy(pattern_result: Dict[str, Any],
                                  data: pd.DataFrame,
                                  symbol: str,
                                  global_config: Dict[str, Any],
                                  setup_config: Dict[str, Any],
                                  mode: str) -> Dict[str, Any]:
    """
    Apply binary options specific strategy
    """
    # Get configuration
    expiry_period = setup_config.get('expiry_period', '15min')
    min_confidence = setup_config.get('min_confidence', 60)
    confidence = pattern_result.get('confidence', 0)
    
    # Check minimum confidence
    if confidence < min_confidence:
        return {
            'trade_decision': 'REJECT',
            'reason': f'Confidence too low: {confidence:.1f}% < {min_confidence}%'
        }
    
    # Calculate entry and expiry details
    entry_price = get_entry_price(data, pattern_result, mode)
    entry_time = get_entry_time(data, mode)
    expiry_time = get_expiry_time(entry_time, expiry_period)
    
    # Calculate position size
    initial_capital = global_config.get('backtest', {}).get('initial_capital', 10000)
    stake_pct = setup_config.get('binary_options', {}).get('stake_percentage', 0.5)
    
    position_size = calculate_position_size(
        pattern_result, 
        initial_capital,
        stake_pct
    )
    
    # Trade direction
    signal_type = pattern_result.get('signal_type')
    trade_direction = 'UP' if signal_type == 'CALL' else 'DOWN'
    
    # Payout details
    payout_ratio = 0.75
    stake_amount = position_size
    
    return {
        'trade_decision': 'ACCEPT',
        'trade_type': 'BINARY_OPTION',
        'direction': trade_direction,
        'entry_price': entry_price,
        'entry_time': entry_time,
        'expiry_time': expiry_time,
        'expiry_period': expiry_period,
        'position_size': position_size,
        'stake_amount': stake_amount,
        'payout_ratio': payout_ratio,
        'potential_payout': stake_amount * (1 + payout_ratio),
        'potential_loss': stake_amount,
        'risk_reward_ratio': payout_ratio
    }


def _apply_regular_trading_strategy(pattern_result: Dict[str, Any],
                                   data: pd.DataFrame,
                                   symbol: str,
                                   global_config: Dict[str, Any],
                                   setup_config: Dict[str, Any],
                                   mode: str) -> Dict[str, Any]:
    """
    Apply regular trading strategy
    """
    # Get risk configuration
    risk_config = global_config.get('risk', {})
    risk_per_trade_pct = setup_config.get('regular_trading', {}).get('risk_per_trade_pct', 0.5)
    initial_capital = global_config.get('backtest', {}).get('initial_capital', 10000)
    
    # Calculate entry price
    entry_price = get_entry_price(data, pattern_result, mode)
    
    # Calculate stop loss and take profit
    stop_loss = get_stop_loss(entry_price, pattern_result, setup_config, data, symbol)
    take_profit = get_take_profit(entry_price, pattern_result, setup_config)
    
    # Calculate position size
    position_size = calculate_position_size(
        pattern_result,
        initial_capital,
        risk_per_trade_pct,
        entry_price,
        stop_loss
    )
    
    # Calculate risk/reward
    risk_reward = calculate_risk_reward(entry_price, stop_loss, take_profit)
    
    # Check minimum risk/reward
    min_risk_reward = setup_config.get('regular_trading', {}).get('risk_reward_ratio', 1.5)
    trade_decision = 'ACCEPT' if risk_reward >= min_risk_reward else 'REJECT'
    
    result = {
        'trade_decision': trade_decision,
        'trade_type': 'REGULAR_TRADE',
        'direction': 'BUY' if pattern_result.get('signal_type') == 'CALL' else 'SELL',
        'entry_price': entry_price,
        'current_price': pattern_result.get('current_price', entry_price),
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'position_size': position_size,
        'risk_per_trade_pct': risk_per_trade_pct,
        'risk_amount': abs(entry_price - stop_loss) * position_size,
        'potential_profit': abs(take_profit - entry_price) * position_size,
        'risk_reward_ratio': risk_reward,
        'stop_loss_distance_pips': calculate_pip_distance(entry_price, stop_loss, symbol),
        'take_profit_distance_pips': calculate_pip_distance(entry_price, take_profit, symbol)
    }
    
    if trade_decision == 'REJECT':
        result['reason'] = f'Risk/Reward too low: {risk_reward:.2f} < {min_risk_reward}'
    
    return result


def calculate_position_size(pattern_result: Dict[str, Any],
                           account_balance: float,
                           risk_percentage: float,
                           entry_price: float = None,
                           stop_loss: float = None) -> float:
    """
    Calculate position size based on risk management
    """
    confidence = pattern_result.get('confidence', 50)
    
    # Base risk amount
    risk_amount = account_balance * (risk_percentage / 100)
    
    # Adjust by confidence (80-100% of base risk)
    confidence_multiplier = 0.8 + (confidence / 100 * 0.2)
    
    # For binary options
    trade_type = pattern_result.get('trade_type', 'binary_options')
    
    if trade_type == 'binary_options' or entry_price is None or stop_loss is None:
        position_size = risk_amount * confidence_multiplier
        return round(position_size, 2)
    
    else:
        # Regular trading
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        position_units = (risk_amount * confidence_multiplier) / risk_per_unit
        return round(position_units, 4)


def get_entry_price(data: pd.DataFrame, 
                   pattern_result: Dict[str, Any], 
                   mode: str = 'live') -> float:
    """
    Get entry price for the trade
    """
    if mode == 'backtest':
        if len(data) >= 2:
            return float(data.iloc[-1]['open'])
    
    return pattern_result.get('current_price', 0)


def get_entry_time(data: pd.DataFrame, mode: str = 'live') -> datetime:
    """
    Get entry time for the trade
    """
    if mode == 'backtest':
        if 'timestamp' in data.columns and len(data) >= 2:
            return data.iloc[-1]['timestamp']
    
    return datetime.now()


def get_expiry_time(entry_time: datetime, expiry_period: str) -> datetime:
    """
    Calculate expiry time based on entry time and period
    """
    if expiry_period.endswith('min'):
        minutes = int(expiry_period[:-3])
        return entry_time + timedelta(minutes=minutes)
    elif expiry_period.endswith('H'):
        hours = int(expiry_period[:-1])
        return entry_time + timedelta(hours=hours)
    elif expiry_period.endswith('D'):
        days = int(expiry_period[:-1])
        return entry_time + timedelta(days=days)
    else:
        return entry_time + timedelta(minutes=15)


def calculate_risk_reward(entry_price: float, 
                         stop_loss: float, 
                         take_profit: float) -> float:
    """
    Calculate risk/reward ratio
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    
    if risk == 0:
        return 0
    
    return reward / risk


def calculate_atr(data: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Average True Range
    """
    if len(data) < period + 1:
        return 0
    
    high = data['high']
    low = data['low']
    close = data['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0


def get_stop_loss(entry_price: float, 
                 pattern_result: Dict[str, Any],
                 setup_config: Dict[str, Any],
                 data: pd.DataFrame,
                 symbol: str) -> float:
    """
    Calculate stop loss price
    """
    signal_type = pattern_result.get('signal_type')
    
    # Get stop loss configuration
    stop_loss_type = setup_config.get('regular_trading', {}).get('stop_loss_type', 'atr')
    
    if stop_loss_type == 'atr':
        atr = calculate_atr(data)
        atr_multiplier = setup_config.get('regular_trading', {}).get('stop_loss_atr_multiplier', 1.5)
        
        if signal_type == 'CALL':
            return entry_price - (atr * atr_multiplier)
        else:
            return entry_price + (atr * atr_multiplier)
    
    else:
        # Percentage-based
        stop_loss_pct = setup_config.get('regular_trading', {}).get('stop_loss_pct', 0.5)
        
        if signal_type == 'CALL':
            return entry_price * (1 - stop_loss_pct / 100)
        else:
            return entry_price * (1 + stop_loss_pct / 100)


def get_take_profit(entry_price: float,
                   pattern_result: Dict[str, Any],
                   setup_config: Dict[str, Any]) -> float:
    """
    Calculate take profit price
    """
    signal_type = pattern_result.get('signal_type')
    
    # Get take profit configuration
    risk_reward_ratio = setup_config.get('regular_trading', {}).get('risk_reward_ratio', 1.5)
    
    # Calculate stop loss first to determine risk
    stop_loss_pct = setup_config.get('regular_trading', {}).get('stop_loss_pct', 0.5)
    
    risk = entry_price * (stop_loss_pct / 100)
    reward = risk * risk_reward_ratio
    
    if signal_type == 'CALL':
        return entry_price + reward
    else:
        return entry_price - reward


def calculate_pip_distance(price1: float, price2: float, symbol: str) -> float:
    """
    Calculate distance between two prices in pips
    """
    pip_size = 0.01 if 'JPY' in symbol else 0.0001
    distance = abs(price1 - price2)
    return round(distance / pip_size, 1)


def validate_trade_conditions(pattern_result: Dict[str, Any],
                             strategy_result: Dict[str, Any],
                             setup_config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate if trade conditions are met
    """
    # Check minimum confidence
    min_confidence = setup_config.get('min_confidence', 60)
    confidence = pattern_result.get('confidence', 0)
    
    if confidence < min_confidence:
        return False, f'Confidence too low: {confidence:.1f}% < {min_confidence}%'
    
    # Check secondary conditions
    conditions = pattern_result.get('conditions', {})
    secondary_met = conditions.get('secondary_conditions_met', 0)
    min_secondary = setup_config.get('signal', {}).get('min_secondary_conditions', 2)
    
    if secondary_met < min_secondary:
        return False, f'Insufficient secondary conditions: {secondary_met} < {min_secondary}'
    
    # Check if strategy accepted trade
    if strategy_result.get('trade_decision') != 'ACCEPT':
        return False, strategy_result.get('reason', 'Strategy rejected trade')
    
    return True, 'All conditions met'


def check_choppy_market(data: pd.DataFrame, symbol: str, 
                       ema_2: float, ema_5: float, ema_100: float) -> bool:
    """
    Check if market is too choppy (EMAs clustered together)
    """
    pip_size = 0.01 if 'JPY' in symbol else 0.0001
    max_clustering = pip_size * 20  # 20 pips
    
    # Check distance between EMAs
    distance_2_5 = abs(ema_2 - ema_5)
    distance_5_100 = abs(ema_5 - ema_100)
    distance_2_100 = abs(ema_2 - ema_100)
    
    # If all EMAs are within 20 pips, market is choppy
    if distance_2_100 < max_clustering:
        return True
    
    return False


# Test function
if __name__ == "__main__":
    # Test the strategy functions
    test_pattern_result = {
        'signal_type': 'CALL',
        'pattern_name': 'MA Crossover Bullish',
        'confidence': 75.0,
        'current_price': 1.0850,
        'conditions': {
            'secondary_conditions_met': 3,
            'ema_2': 1.0852,
            'ema_5': 1.0848,
            'ema_100': 1.0830
        }
    }
    
    test_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=150, freq='5min'),
        'open': np.random.randn(150).cumsum() + 1.08,
        'high': np.random.randn(150).cumsum() + 1.081,
        'low': np.random.randn(150).cumsum() + 1.079,
        'close': np.random.randn(150).cumsum() + 1.08,
        'volume': np.random.randint(1000, 10000, 150)
    })
    
    test_config = {
        'trade_type': 'binary_options',
        'expiry_period': '15min',
        'min_confidence': 60,
        'binary_options': {
            'stake_percentage': 0.5
        }
    }
    
    # Test binary options strategy
    binary_result = _apply_binary_options_strategy(
        test_pattern_result, test_data, 'EUR/USD', {}, test_config, 'test'
    )
    print("Binary Options Strategy Result:")
    for key, value in binary_result.items():
        print(f"  {key}: {value}")
    
    # Test validation
    is_valid, reason = validate_trade_conditions(
        test_pattern_result, binary_result, test_config
    )
    print(f"\nValidation: {is_valid}")
    print(f"Reason: {reason}")