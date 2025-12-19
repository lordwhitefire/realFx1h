"""
Data Processor - Utility functions for data cleaning, validation, and processing
Handles all data preparation for trading setups
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta


class DataProcessor:
    """Processes and prepares market data for analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, 
                          required_columns: List[str] = None) -> Tuple[bool, str]:
        """
        Validate DataFrame structure and data quality
        
        Args:
            df: DataFrame to validate
            required_columns: List of required columns
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if df is None:
            return False, "DataFrame is None"
        
        if df.empty:
            return False, "DataFrame is empty"
        
        # Default required columns for OHLC data
        if required_columns is None:
            required_columns = ['timestamp', 'open', 'high', 'low', 'close']
        
        # Check required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, f"Missing required columns: {missing_columns}"
        
        # Check for NaN values in required columns
        nan_counts = df[required_columns].isna().sum()
        if nan_counts.any():
            return False, f"NaN values found in: {nan_counts[nan_counts > 0].to_dict()}"
        
        # Check data types
        numeric_columns = ['open', 'high', 'low', 'close']
        for col in numeric_columns:
            if col in df.columns:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    return False, f"Column '{col}' is not numeric"
        
        # Check timestamp column
        if 'timestamp' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                # Try to convert
                try:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                except:
                    return False, "Cannot convert 'timestamp' column to datetime"
        
        # Check for duplicate timestamps
        if 'timestamp' in df.columns:
            duplicates = df['timestamp'].duplicated().sum()
            if duplicates > 0:
                return False, f"Found {duplicates} duplicate timestamps"
        
        # Check price validity (high >= low, etc.)
        if all(col in df.columns for col in ['high', 'low']):
            invalid_prices = df[df['high'] < df['low']]
            if len(invalid_prices) > 0:
                return False, f"Found {len(invalid_prices)} rows with high < low"
        
        return True, "DataFrame is valid"
    
    def clean_ohlc_data(self, df: pd.DataFrame, 
                       symbol: str = None) -> pd.DataFrame:
        """
        Clean and prepare OHLC data for analysis
        
        Args:
            df: Raw OHLC DataFrame
            symbol: Trading symbol (for logging)
            
        Returns:
            pd.DataFrame: Cleaned DataFrame
        """
        if df is None or df.empty:
            self.logger.warning(f"No data to clean for {symbol or 'unknown symbol'}")
            return df
        
        # Make a copy to avoid modifying original
        df_clean = df.copy()
        
        # 1. Ensure timestamp is datetime
        if 'timestamp' in df_clean.columns:
            df_clean['timestamp'] = pd.to_datetime(df_clean['timestamp'])
        
        # 2. Sort by timestamp (oldest first)
        if 'timestamp' in df_clean.columns:
            df_clean = df_clean.sort_values('timestamp').reset_index(drop=True)
        
        # 3. Handle missing values
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        numeric_columns = [col for col in numeric_columns if col in df_clean.columns]
        
        for col in numeric_columns:
            # Forward fill then backward fill
            df_clean[col] = df_clean[col].ffill().bfill()
        
        # 4. Validate price relationships
        if all(col in df_clean.columns for col in ['open', 'high', 'low', 'close']):
            # Ensure high is the highest of OHLC
            df_clean['high'] = df_clean[['open', 'high', 'low', 'close']].max(axis=1)
            
            # Ensure low is the lowest of OHLC
            df_clean['low'] = df_clean[['open', 'high', 'low', 'close']].min(axis=1)
        
        # 5. Remove zero or negative prices
        price_columns = ['open', 'high', 'low', 'close']
        price_columns = [col for col in price_columns if col in df_clean.columns]
        
        for col in price_columns:
            mask = (df_clean[col] <= 0) | df_clean[col].isna()
            if mask.any():
                df_clean = df_clean[~mask].copy()
        
        # 6. Add calculated columns
        df_clean = self._add_calculated_columns(df_clean)
        
        # 7. Remove extreme outliers (beyond 5 standard deviations)
        df_clean = self.remove_outliers(df_clean)
        
        self.logger.debug(f"Cleaned {len(df_clean)} rows for {symbol or 'unknown symbol'}")
        return df_clean
    
    def _add_calculated_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add common calculated columns to DataFrame
        
        Args:
            df: Input DataFrame
            
        Returns:
            pd.DataFrame: DataFrame with added columns
        """
        df_calc = df.copy()
        
        # 1. Returns
        if 'close' in df_calc.columns:
            df_calc['returns'] = df_calc['close'].pct_change()
            df_calc['log_returns'] = np.log(df_calc['close'] / df_calc['close'].shift(1))
        
        # 2. Price ranges
        if all(col in df_calc.columns for col in ['high', 'low']):
            df_calc['range'] = df_calc['high'] - df_calc['low']
            df_calc['range_pct'] = df_calc['range'] / df_calc['close'] * 100
        
        # 3. Candlestick components
        if all(col in df_calc.columns for col in ['open', 'close', 'high', 'low']):
            df_calc['body'] = abs(df_calc['close'] - df_calc['open'])
            df_calc['body_pct'] = df_calc['body'] / df_calc['close'] * 100
            
            df_calc['upper_shadow'] = df_calc['high'] - df_calc[['open', 'close']].max(axis=1)
            df_calc['lower_shadow'] = df_calc[['open', 'close']].min(axis=1) - df_calc['low']
            
            df_calc['is_bullish'] = df_calc['close'] > df_calc['open']
            df_calc['is_bearish'] = df_calc['close'] < df_calc['open']
            df_calc['is_doji'] = df_calc['body_pct'] < 0.1  # Body less than 0.1%
        
        # 4. Volume analysis (if volume exists)
        if 'volume' in df_calc.columns:
            df_calc['volume_ma'] = df_calc['volume'].rolling(window=20, min_periods=1).mean()
            df_calc['volume_ratio'] = df_calc['volume'] / df_calc['volume_ma']
        
        return df_calc
    
    @staticmethod
    def remove_outliers(df: pd.DataFrame, 
                       columns: List[str] = None,
                       threshold: float = 5.0) -> pd.DataFrame:
        """
        Remove statistical outliers using Z-score
        
        Args:
            df: Input DataFrame
            columns: Columns to check for outliers
            threshold: Z-score threshold (default 5 std deviations)
            
        Returns:
            pd.DataFrame: DataFrame with outliers removed
        """
        if df.empty:
            return df
        
        df_clean = df.copy()
        
        if columns is None:
            columns = ['open', 'high', 'low', 'close', 'volume']
            columns = [col for col in columns if col in df_clean.columns]
        
        # Calculate Z-scores for specified columns
        for col in columns:
            if col in df_clean.columns:
                z_scores = np.abs((df_clean[col] - df_clean[col].mean()) / df_clean[col].std())
                df_clean = df_clean[z_scores < threshold].copy()
        
        return df_clean
    
    @staticmethod
    def calculate_returns(df: pd.DataFrame, 
                         price_column: str = 'close',
                         periods: List[int] = None) -> pd.DataFrame:
        """
        Calculate returns over multiple periods
        
        Args:
            df: Input DataFrame
            price_column: Column to calculate returns from
            periods: List of periods to calculate returns for
            
        Returns:
            pd.DataFrame: DataFrame with return columns added
        """
        if periods is None:
            periods = [1, 3, 5, 10, 20]  # Common periods
        
        df_returns = df.copy()
        
        if price_column not in df_returns.columns:
            return df_returns
        
        for period in periods:
            column_name = f'return_{period}'
            df_returns[column_name] = df_returns[price_column].pct_change(periods=period)
        
        return df_returns
    
    def detect_gaps(self, df: pd.DataFrame, 
                   timeframe_minutes: int = 5) -> pd.DataFrame:
        """
        Detect time gaps in data
        
        Args:
            df: Input DataFrame with timestamp column
            timeframe_minutes: Expected timeframe in minutes
            
        Returns:
            pd.DataFrame: DataFrame with gap information
        """
        if 'timestamp' not in df.columns:
            return df
        
        df_gaps = df.copy().sort_values('timestamp')
        
        # Calculate time differences between consecutive candles
        df_gaps['time_diff'] = df_gaps['timestamp'].diff().dt.total_seconds() / 60
        
        # Expected time difference (with 10% tolerance)
        expected_diff = timeframe_minutes
        tolerance = expected_diff * 0.1
        
        # Identify gaps
        df_gaps['is_gap'] = df_gaps['time_diff'] > (expected_diff + tolerance)
        df_gaps['gap_size_minutes'] = df_gaps['time_diff'] - expected_diff
        df_gaps['gap_size_minutes'] = df_gaps['gap_size_minutes'].where(
            df_gaps['is_gap'], 0
        )
        
        return df_gaps
    
    def resample_data(self, df: pd.DataFrame, 
                     timeframe: str = '5min',
                     aggregation: str = 'ohlc') -> pd.DataFrame:
        """
        Resample data to different timeframe
        
        Args:
            df: Input DataFrame
            timeframe: Target timeframe (e.g., '5min', '1H', '1D')
            aggregation: Aggregation method ('ohlc', 'close', 'mean')
            
        Returns:
            pd.DataFrame: Resampled DataFrame
        """
        if 'timestamp' not in df.columns:
            self.logger.warning("Cannot resample without timestamp column")
            return df
        
        # Set timestamp as index for resampling
        df_resampled = df.set_index('timestamp').copy()
        
        # Define aggregation rules based on aggregation type
        if aggregation == 'ohlc':
            agg_rules = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }
            # Add volume if present
            if 'volume' in df_resampled.columns:
                agg_rules['volume'] = 'sum'
        elif aggregation == 'close':
            agg_rules = {'close': 'last'}
        elif aggregation == 'mean':
            agg_rules = {
                'open': 'mean',
                'high': 'mean',
                'low': 'mean',
                'close': 'mean'
            }
            if 'volume' in df_resampled.columns:
                agg_rules['volume'] = 'mean'
        else:
            self.logger.warning(f"Unknown aggregation method: {aggregation}")
            return df
        
        # Only include columns that exist in DataFrame
        agg_rules = {k: v for k, v in agg_rules.items() if k in df_resampled.columns}
        
        # Perform resampling
        resampled = df_resampled.resample(timeframe).agg(agg_rules)
        
        # Remove rows where open is NaN (incomplete periods)
        if 'open' in resampled.columns:
            resampled = resampled.dropna(subset=['open'])
        
        # Reset index to get timestamp column back
        resampled = resampled.reset_index()
        
        self.logger.debug(f"Resampled from {len(df)} to {len(resampled)} rows "
                         f"({timeframe}, {aggregation})")
        
        return resampled
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate common technical indicators
        
        Args:
            df: Input DataFrame
            
        Returns:
            pd.DataFrame: DataFrame with indicators added
        """
        if df.empty:
            return df
        
        df_indicators = df.copy()
        
        # Ensure we have required columns
        if 'close' not in df_indicators.columns:
            self.logger.warning("Cannot calculate indicators without 'close' column")
            return df_indicators
        
        # 1. Simple Moving Averages
        periods = [5, 10, 20, 50, 200]
        for period in periods:
            df_indicators[f'sma_{period}'] = df_indicators['close'].rolling(
                window=period, min_periods=1
            ).mean()
        
        # 2. Exponential Moving Averages
        for period in [9, 21, 50]:
            df_indicators[f'ema_{period}'] = df_indicators['close'].ewm(
                span=period, adjust=False
            ).mean()
        
        # 3. RSI (Relative Strength Index)
        if len(df_indicators) >= 15:  # Need enough data for RSI
            delta = df_indicators['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df_indicators['rsi'] = 100 - (100 / (1 + rs))
        else:
            df_indicators['rsi'] = 50  # Neutral value
        
        # 4. MACD
        if len(df_indicators) >= 26:
            exp1 = df_indicators['close'].ewm(span=12, adjust=False).mean()
            exp2 = df_indicators['close'].ewm(span=26, adjust=False).mean()
            df_indicators['macd'] = exp1 - exp2
            df_indicators['macd_signal'] = df_indicators['macd'].ewm(
                span=9, adjust=False
            ).mean()
            df_indicators['macd_histogram'] = df_indicators['macd'] - df_indicators['macd_signal']
        
        # 5. Bollinger Bands
        if len(df_indicators) >= 20:
            df_indicators['bb_middle'] = df_indicators['close'].rolling(window=20).mean()
            bb_std = df_indicators['close'].rolling(window=20).std()
            df_indicators['bb_upper'] = df_indicators['bb_middle'] + (bb_std * 2)
            df_indicators['bb_lower'] = df_indicators['bb_middle'] - (bb_std * 2)
            df_indicators['bb_width'] = df_indicators['bb_upper'] - df_indicators['bb_lower']
            df_indicators['bb_position'] = (df_indicators['close'] - df_indicators['bb_lower']) / \
                                          (df_indicators['bb_upper'] - df_indicators['bb_lower'])
        
        # 6. ATR (Average True Range) - if we have high/low data
        if all(col in df_indicators.columns for col in ['high', 'low', 'close']):
            if len(df_indicators) >= 14:
                high_low = df_indicators['high'] - df_indicators['low']
                high_close = abs(df_indicators['high'] - df_indicators['close'].shift())
                low_close = abs(df_indicators['low'] - df_indicators['close'].shift())
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                df_indicators['atr'] = true_range.rolling(window=14).mean()
        
        # 7. Volume indicators (if volume exists)
        if 'volume' in df_indicators.columns and len(df_indicators) >= 20:
            df_indicators['volume_sma'] = df_indicators['volume'].rolling(window=20).mean()
            df_indicators['volume_ratio'] = df_indicators['volume'] / df_indicators['volume_sma']
            
            # OBV (On-Balance Volume)
            df_indicators['price_change'] = df_indicators['close'].diff()
            df_indicators['obv'] = 0
            mask_up = df_indicators['price_change'] > 0
            mask_down = df_indicators['price_change'] < 0
            
            df_indicators.loc[mask_up, 'obv'] = df_indicators.loc[mask_up, 'volume']
            df_indicators.loc[mask_down, 'obv'] = -df_indicators.loc[mask_down, 'volume']
            df_indicators['obv'] = df_indicators['obv'].cumsum()
        
        return df_indicators
    
    def prepare_for_analysis(self, df: pd.DataFrame, 
                           symbol: str = None,
                           lookback_candles: int = 100) -> pd.DataFrame:
        """
        Full data preparation pipeline
        
        Args:
            df: Raw input DataFrame
            symbol: Trading symbol for logging
            lookback_candles: Number of candles to keep
            
        Returns:
            pd.DataFrame: Fully prepared DataFrame
        """
        self.logger.info(f"Preparing data for {symbol or 'unknown symbol'}")
        
        # 1. Validate data
        is_valid, error_msg = self.validate_dataframe(df)
        if not is_valid:
            self.logger.error(f"Data validation failed for {symbol}: {error_msg}")
            return pd.DataFrame()  # Return empty DataFrame
        
        # 2. Clean data
        df_clean = self.clean_ohlc_data(df, symbol)
        
        if df_clean.empty:
            self.logger.warning(f"No data after cleaning for {symbol}")
            return df_clean
        
        # 3. Calculate technical indicators
        df_with_indicators = self.calculate_technical_indicators(df_clean)
        
        # 4. Limit to lookback period
        if lookback_candles and len(df_with_indicators) > lookback_candles:
            df_final = df_with_indicators.iloc[-lookback_candles:].copy()
            self.logger.debug(f"Limited to last {lookback_candles} candles "
                            f"({len(df_final)} rows)")
        else:
            df_final = df_with_indicators.copy()
        
        # 5. Reset index
        df_final = df_final.reset_index(drop=True)
        
        self.logger.info(f"Prepared {len(df_final)} rows for {symbol or 'unknown symbol'}")
        return df_final
    
    def get_data_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get statistics about the data
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dict[str, Any]: Data statistics
        """
        if df is None or df.empty:
            return {'error': 'Empty DataFrame'}
        
        stats = {
            'basic': {
                'rows': len(df),
                'columns': len(df.columns),
                'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
            }
        }
        
        # Date range
        if 'timestamp' in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                stats['date_range'] = {
                    'start': df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S'),
                    'end': df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S'),
                    'days': (df['timestamp'].max() - df['timestamp'].min()).days
                }
        
        # Numeric column statistics
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            stats['numeric_summary'] = df[numeric_cols].describe().to_dict()
        
        # Missing values
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        if not missing.empty:
            stats['missing_values'] = missing.to_dict()
        
        # Duplicates
        if 'timestamp' in df.columns:
            duplicates = df['timestamp'].duplicated().sum()
            if duplicates > 0:
                stats['duplicate_timestamps'] = duplicates
        
        return stats