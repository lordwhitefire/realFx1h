"""
Strategy Module for Setup1
Defines entry, exit, and risk management rules for the Hammer/Shooting Star setup
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
    pattern_name = pattern_result.get('pattern_name')
    confidence = pattern_result.get('confidence', 0)
    current_price = pattern_result.get('current_price', 0)
    
    # Get risk configuration
    risk_config = global_config.get('risk', {})
    backtest_config = global_config.get('backtest', {})
    
    # Determine if this is for binary options or regular trading
    trade_type = setup_config.get('trade_type', 'binary_options')
    
    strategy_result = {}
    
    if trade_type == 'binary_options':
        # Binary options strategy
        strategy_result = _apply_binary_options_strategy(
            pattern_result, data, symbol, global_config, setup_config, mode
        )
    else:
        # Regular trading strategy
        strategy_result = _apply_regular_trading_strategy(
            pattern_result, data, symbol, global_config, setup_config, mode
        )
    
    # Add common strategy metrics
    strategy_result.update({
        'trade_type': trade_type,
        'strategy_applied': True,
        'strategy_name': 'Hammer_ShootingStar_SR_Strategy',
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
    
    Args:
        pattern_result: Pattern detection result
        data: Market data DataFrame
        symbol: Trading symbol
        global_config: Global configuration
        setup_config: Setup-specific configuration
        mode: Trading mode
        
    Returns:
        Dict with binary options strategy results
    """
    # Get configuration
    expiry_period = setup_config.get('expiry_period', '15min')
    min_confidence = setup_config.get('min_confidence', 70)
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
    
    # Calculate position size (for backtesting)
    position_size = calculate_position_size(
        pattern_result, 
        global_config.get('backtest', {}).get('initial_capital', 10000),
        global_config.get('risk', {}).get('stake_pct', 1.0)
    )
    
    # Determine trade direction based on signal
    signal_type = pattern_result.get('signal_type')
    trade_direction = 'UP' if signal_type == 'CALL' else 'DOWN'
    
    # For binary options, we have fixed payout (simplified)
    payout_ratio = 0.75  # 75% payout for win
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
        'risk_reward_ratio': payout_ratio  # For binary, risk:reward is 1:payout_ratio
    }


def _apply_regular_trading_strategy(pattern_result: Dict[str, Any],
                                   data: pd.DataFrame,
                                   symbol: str,
                                   global_config: Dict[str, Any],
                                   setup_config: Dict[str, Any],
                                   mode: str) -> Dict[str, Any]:
    """
    Apply regular trading strategy
    
    Args:
        pattern_result: Pattern detection result
        data: Market data DataFrame
        symbol: Trading symbol
        global_config: Global configuration
        setup_config: Setup-specific configuration
        mode: Trading mode
        
    Returns:
        Dict with regular trading strategy results
    """
    # Get risk configuration
    risk_config = global_config.get('risk', {})
    risk_per_trade_pct = risk_config.get('risk_per_trade_pct', 1.0)
    initial_capital = global_config.get('backtest', {}).get('initial_capital', 10000)
    
    # Calculate entry price
    entry_price = get_entry_price(data, pattern_result, mode)
    current_price = pattern_result.get('current_price', entry_price)
    
    # Calculate stop loss and take profit
    stop_loss = get_stop_loss(entry_price, pattern_result, setup_config)
    take_profit = get_take_profit(entry_price, pattern_result, setup_config)
    
    # Calculate position size
    position_size = calculate_position_size(
        pattern_result,
        initial_capital,
        risk_per_trade_pct,
        entry_price,
        stop_loss
    )
    
    # Calculate risk/reward ratio
    risk_reward = calculate_risk_reward(entry_price, stop_loss, take_profit)
    
    # Determine if trade should be taken based on risk/reward
    min_risk_reward = setup_config.get('min_risk_reward', 1.5)
    trade_decision = 'ACCEPT' if risk_reward >= min_risk_reward else 'REJECT'
    
    result = {
        'trade_decision': trade_decision,
        'trade_type': 'REGULAR_TRADE',
        'direction': 'BUY' if pattern_result.get('signal_type') == 'CALL' else 'SELL',
        'entry_price': entry_price,
        'current_price': current_price,
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
        result['reason'] = f'Risk/Reward ratio too low: {risk_reward:.2f} < {min_risk_reward}'
    
    return result


def calculate_position_size(pattern_result: Dict[str, Any],
                           account_balance: float,
                           risk_percentage: float,
                           entry_price: float = None,
                           stop_loss: float = None) -> float:
    """
    Calculate position size based on risk management
    
    Args:
        pattern_result: Pattern detection result
        account_balance: Current account balance
        risk_percentage: Percentage of account to risk per trade
        entry_price: Entry price (required for regular trading)
        stop_loss: Stop loss price (required for regular trading)
        
    Returns:
        float: Position size (units for regular, amount for binary)
    """
    signal_type = pattern_result.get('signal_type')
    confidence = pattern_result.get('confidence', 50)
    
    # Base risk amount
    risk_amount = account_balance * (risk_percentage / 100)
    
    # Adjust based on confidence
    confidence_multiplier = confidence / 100
    
    # For binary options, position size is the stake amount
    trade_type = pattern_result.get('trade_type', 'binary_options')
    
    if trade_type == 'binary_options':
        # Binary options: stake amount adjusted by confidence
        position_size = risk_amount * confidence_multiplier
        return round(position_size, 2)
    
    else:
        # Regular trading: calculate units based on stop loss
        if entry_price is None or stop_loss is None:
            return 0
        
        # Risk per unit
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        # Position size in units
        position_units = (risk_amount * confidence_multiplier) / risk_per_unit
        
        return round(position_units, 4)


def get_entry_price(data: pd.DataFrame, 
                   pattern_result: Dict[str, Any], 
                   mode: str = 'live') -> float:
    """
    Get entry price for the trade
    
    Args:
        data: Market data DataFrame
        pattern_result: Pattern detection result
        mode: Trading mode
        
    Returns:
        float: Entry price
    """
    if mode == 'backtest':
        # In backtest, entry is next candle's open
        if len(data) >= 2:
            return float(data.iloc[-1]['open'])
    
    # In live mode or default, use current price
    return pattern_result.get('current_price', 0)


def get_entry_time(data: pd.DataFrame, mode: str = 'live') -> datetime:
    """
    Get entry time for the trade
    
    Args:
        data: Market data DataFrame
        mode: Trading mode
        
    Returns:
        datetime: Entry time
    """
    if mode == 'backtest':
        # In backtest, use the timestamp of the entry candle
        if 'timestamp' in data.columns and len(data) >= 2:
            return data.iloc[-1]['timestamp']
    
    # In live mode, use current time
    return datetime.now()


def get_expiry_time(entry_time: datetime, expiry_period: str) -> datetime:
    """
    Calculate expiry time based on entry time and period
    
    Args:
        entry_time: Trade entry time
        expiry_period: Expiry period string (e.g., '15min', '1H', '4H')
        
    Returns:
        datetime: Expiry time
    """
    # Parse expiry period
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
        # Default to 15 minutes
        return entry_time + timedelta(minutes=15)


def calculate_risk_reward(entry_price: float, 
                         stop_loss: float, 
                         take_profit: float) -> float:
    """
    Calculate risk/reward ratio
    
    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price
        
    Returns:
        float: Risk/Reward ratio
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    
    if risk == 0:
        return 0
    
    return reward / risk


def get_stop_loss(entry_price: float, 
                 pattern_result: Dict[str, Any],
                 setup_config: Dict[str, Any]) -> float:
    """
    Calculate stop loss price
    
    Args:
        entry_price: Entry price
        pattern_result: Pattern detection result
        setup_config: Setup configuration
        
    Returns:
        float: Stop loss price
    """
    signal_type = pattern_result.get('signal_type')
    pattern_name = pattern_result.get('pattern_name')
    
    # Get stop loss configuration
    stop_loss_pct = setup_config.get('stop_loss_pct', 1.0)
    atr_multiplier = setup_config.get('atr_stop_multiplier', 2.0)
    
    # Use pattern-specific stop loss
    if pattern_name == 'Hammer':
        # For hammer (CALL), stop below the hammer's low
        hammer_low = pattern_result.get('conditions', {}).get('candle_a_low', entry_price * 0.99)
        return hammer_low * 0.995  # Slightly below hammer low
    
    elif pattern_name == 'Shooting Star':
        # For shooting star (PUT), stop above the shooting star's high
        star_high = pattern_result.get('conditions', {}).get('candle_a_high', entry_price * 1.01)
        return star_high * 1.005  # Slightly above star high
    
    else:
        # Default percentage-based stop loss
        if signal_type == 'CALL':
            return entry_price * (1 - stop_loss_pct / 100)
        else:  # PUT
            return entry_price * (1 + stop_loss_pct / 100)


def get_take_profit(entry_price: float,
                   pattern_result: Dict[str, Any],
                   setup_config: Dict[str, Any]) -> float:
    """
    Calculate take profit price
    
    Args:
        entry_price: Entry price
        pattern_result: Pattern detection result
        setup_config: Setup configuration
        
    Returns:
        float: Take profit price
    """
    signal_type = pattern_result.get('signal_type')
    
    # Get take profit configuration
    take_profit_pct = setup_config.get('take_profit_pct', 2.0)
    risk_reward_ratio = setup_config.get('risk_reward_ratio', 2.0)
    
    # Calculate stop loss first
    stop_loss = get_stop_loss(entry_price, pattern_result, setup_config)
    
    # Calculate risk
    risk = abs(entry_price - stop_loss)
    
    # Use risk/reward ratio to calculate take profit
    if risk_reward_ratio > 0:
        reward = risk * risk_reward_ratio
        
        if signal_type == 'CALL':
            return entry_price + reward
        else:  # PUT
            return entry_price - reward
    else:
        # Fallback to percentage-based take profit
        if signal_type == 'CALL':
            return entry_price * (1 + take_profit_pct / 100)
        else:  # PUT
            return entry_price * (1 - take_profit_pct / 100)


def calculate_pip_distance(price1: float, price2: float, symbol: str) -> float:
    """
    Calculate distance between two prices in pips
    
    Args:
        price1: First price
        price2: Second price
        symbol: Trading symbol
        
    Returns:
        float: Distance in pips
    """
    pip_size = 0.01 if 'JPY' in symbol else 0.0001
    distance = abs(price1 - price2)
    return round(distance / pip_size, 1)


def validate_trade_conditions(pattern_result: Dict[str, Any],
                             strategy_result: Dict[str, Any],
                             setup_config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate if trade conditions are met
    
    Args:
        pattern_result: Pattern detection result
        strategy_result: Strategy application result
        setup_config: Setup configuration
        
    Returns:
        Tuple of (is_valid, reason)
    """
    # Check minimum confidence
    min_confidence = setup_config.get('min_confidence', 70)
    confidence = pattern_result.get('confidence', 0)
    
    if confidence < min_confidence:
        return False, f'Confidence too low: {confidence:.1f}% < {min_confidence}%'
    
    # Check risk/reward for regular trades
    if strategy_result.get('trade_type') == 'REGULAR_TRADE':
        min_risk_reward = setup_config.get('min_risk_reward', 1.5)
        risk_reward = strategy_result.get('risk_reward_ratio', 0)
        
        if risk_reward < min_risk_reward:
            return False, f'Risk/Reward too low: {risk_reward:.2f} < {min_risk_reward}'
    
    # Check if trade was accepted by strategy
    if strategy_result.get('trade_decision') != 'ACCEPT':
        return False, strategy_result.get('reason', 'Strategy rejected trade')
    
    return True, 'All conditions met'


# Import pandas at module level for type hints
import pandas as pd


# Test function
if __name__ == "__main__":
    # Test the strategy functions
    test_pattern_result = {
        'signal_type': 'CALL',
        'pattern_name': 'Hammer',
        'confidence': 85.5,
        'current_price': 1.0850,
        'conditions': {
            'candle_a_low': 1.0830,
            'candle_a_high': 1.0860
        }
    }
    
    test_config = {
        'trade_type': 'binary_options',
        'expiry_period': '15min',
        'min_confidence': 70,
        'stop_loss_pct': 1.0,
        'take_profit_pct': 2.0,
        'risk_reward_ratio': 2.0,
        'min_risk_reward': 1.5
    }
    
    # Test binary options strategy
    binary_result = _apply_binary_options_strategy(
        test_pattern_result, None, 'EUR/USD', {}, test_config, 'test'
    )
    print("Binary Options Strategy Result:")
    print(binary_result)
    
    # Test regular trading strategy
    test_pattern_result['trade_type'] = 'regular_trading'
    regular_result = _apply_regular_trading_strategy(
        test_pattern_result, None, 'EUR/USD', {}, test_config, 'test'
    )
    print("\nRegular Trading Strategy Result:")
    print(regular_result)
    
    # Test position size calculation
    position_size = calculate_position_size(
        test_pattern_result, 10000, 1.0, 1.0850, 1.0830
    )
    print(f"\nPosition Size: {position_size}")
    
    # Test risk/reward calculation
    risk_reward = calculate_risk_reward(1.0850, 1.0830, 1.0890)
    print(f"Risk/Reward Ratio: {risk_reward:.2f}")