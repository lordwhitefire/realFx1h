"""
Data Fetcher - Multiple API data fetching for all setups
Fetches data once and distributes to all setup modules
Supports multiple API keys with fixed pair assignments
"""

import requests
import pandas as pd
import yaml
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import os
from collections import defaultdict


class DataFetcher:
    """Handles all data fetching from external APIs with multiple keys"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = None
        self.api_keys = {}  # Dictionary of key_name: key_value
        self.pair_assignments = {}  # Dictionary of symbol: key_name
        self.key_usage = defaultdict(list)  # Track which pairs use which key
        self.data_cache = {}
        self.cache_duration = 60  # Cache data for 5 minutes
        
    def load_config(self, config_path: str = 'config.yaml') -> bool:
        """
        Load global configuration from YAML file
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            bool: True if configuration loaded successfully
        """
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            # Extract multiple API keys
            api_config = self.config.get('api', {})
            self.api_keys = api_config.get('api_keys', {})
            
            # Extract pair-to-key assignments
            self.pair_assignments = api_config.get('pair_assignments', {})
            
            if not self.api_keys:
                print("❌ WARNING: No API keys found in config")
                self.logger.warning("No API keys found in config")
                return False
            
            if not self.pair_assignments:
                print("❌ WARNING: No pair assignments found in config")
                self.logger.warning("No pair assignments found in config")
                return False
            
            # Build key usage mapping for tracking
            for pair, key_name in self.pair_assignments.items():
                if key_name in self.api_keys:
                    self.key_usage[key_name].append(pair)
            
            # Extract data settings
            self.timeframe = self.config.get('data', {}).get('timeframe', '5min')
            self.ohlc_size = self.config.get('data', {}).get('ohlc_size', 2000)
            
            print(f"✅ Configuration loaded from {config_path}")
            print(f"   Timeframe: {self.timeframe}, OHLC Size: {self.ohlc_size}")
            print(f"   API Keys loaded: {len(self.api_keys)}")
            
            # Print key assignments
            print(f"\n📋 API KEY ASSIGNMENTS:")
            for key_name, pairs in self.key_usage.items():
                print(f"   {key_name}: {len(pairs)} pairs - {', '.join(pairs[:3])}{'...' if len(pairs) > 3 else ''}")
            
            self.logger.info(f"Configuration loaded from {config_path}")
            self.logger.info(f"Timeframe: {self.timeframe}, OHLC Size: {self.ohlc_size}")
            self.logger.info(f"Loaded {len(self.api_keys)} API keys")
            
            return True
            
        except FileNotFoundError:
            print(f"❌ ERROR: Configuration file not found: {config_path}")
            self.logger.error(f"Configuration file not found: {config_path}")
            return False
        except yaml.YAMLError as e:
            print(f"❌ ERROR: YAML parsing error: {e}")
            self.logger.error(f"YAML parsing error: {e}")
            return False
        except Exception as e:
            print(f"❌ ERROR: Configuration loading error: {e}")
            self.logger.error(f"Configuration loading error: {e}")
            return False
    
    def get_api_key_for_symbol(self, symbol: str) -> Optional[str]:
        """
        Get the API key assigned to a specific symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Optional[str]: API key value or None if not found
        """
        if symbol not in self.pair_assignments:
            print(f"❌ WARNING: No API key assignment found for {symbol}")
            self.logger.warning(f"No API key assignment found for {symbol}")
            return None
        
        key_name = self.pair_assignments[symbol]
        
        if key_name not in self.api_keys:
            print(f"❌ ERROR: API key '{key_name}' not found for {symbol}")
            self.logger.error(f"API key '{key_name}' not found for {symbol}")
            return None
        
        return self.api_keys[key_name]
    
    def fetch_data(self, symbol: str, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        Fetch market data for a symbol using its assigned API key
        
        Args:
            symbol: Trading symbol (e.g., 'EUR/USD')
            force_refresh: Force fresh data fetch, ignore cache
            
        Returns:
            Optional[pd.DataFrame]: Market data or None if failed
        """
        print(f"\n🔍 DEBUG: Starting fetch_data for {symbol}")
        print(f"   force_refresh: {force_refresh}")
        
        # Check cache first (unless forced refresh)
        if not force_refresh:
            cached_data = self._get_cached_data(symbol)
            if cached_data is not None:
                print(f"✅ Using CACHED data for {symbol}")
                self.logger.debug(f"Using cached data for {symbol}")
                return cached_data
        
        try:
            # Get the API key assigned to this symbol
            api_key = self.get_api_key_for_symbol(symbol)
            if not api_key:
                print(f"❌ ERROR: No valid API key found for {symbol}")
                self.logger.error(f"No valid API key found for {symbol}")
                return None
            
            # Format symbol for API (keep slash for Twelve Data)
            api_symbol = symbol  # Keep the slash as is
            
            # Construct API URL with the specific key
            url = self._construct_api_url(api_symbol, api_key)
            
            print(f"📡 API Request for {symbol}:")
            print(f"   Using key: {self.pair_assignments[symbol]}")
            print(f"   URL: {url[:100]}...")
            
            self.logger.debug(f"Fetching data for {symbol} from API using key {self.pair_assignments[symbol]}")
            
            # Make API request
            print(f"   Making API request...")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            print(f"   API response status: {response.status_code}")
            
            # Parse response
            data = response.json()
            
            # Check API response status
            if data.get('status') != 'ok':
                error_msg = data.get('message', 'Unknown API error')
                print(f"❌ API ERROR for {symbol}: {error_msg}")
                self.logger.error(f"API error for {symbol}: {error_msg}")
                return None
            
            print(f"✅ API response OK for {symbol}")
            print(f"   Number of candles in response: {len(data.get('values', []))}")
            
            # Convert to DataFrame
            df = self._parse_api_response(data, symbol)
            
            if df is not None and not df.empty:
                # Cache the data
                self._cache_data(symbol, df)
                
                # PRINT DEBUG: Show data details
                print(f"\n✅✅✅ SUCCESS: Fetched {len(df)} candles for {symbol}")
                print(f"   Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
                print(f"   Columns: {df.columns.tolist()}")
                print(f"   First 3 candles:")
                for i in range(min(3, len(df))):
                    candle = df.iloc[i]
                    print(f"     {candle['timestamp']}: O={candle['open']:.5f}, H={candle['high']:.5f}, "
                          f"L={candle['low']:.5f}, C={candle['close']:.5f}")
                
                print(f"   Last 3 candles:")
                for i in range(max(0, len(df)-3), len(df)):
                    candle = df.iloc[i]
                    print(f"     {candle['timestamp']}: O={candle['open']:.5f}, H={candle['high']:.5f}, "
                          f"L={candle['low']:.5f}, C={candle['close']:.5f}")
                
                # Also log it
                self.logger.info(f"✅ Fetched {len(df)} candles for {symbol} using key {self.pair_assignments[symbol]}")
                self.logger.info(f"   Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
                
                return df
            else:
                print(f"❌ WARNING: No valid data returned for {symbol}")
                self.logger.warning(f"No valid data returned for {symbol}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"❌ ERROR: API timeout for {symbol}")
            self.logger.error(f"API timeout for {symbol}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR: API request failed for {symbol}: {e}")
            self.logger.error(f"API request failed for {symbol}: {e}")
            return None
        except Exception as e:
            print(f"❌ ERROR: Data fetch error for {symbol}: {e}")
            self.logger.error(f"Data fetch error for {symbol}: {e}")
            return None
    
    def _construct_api_url(self, symbol: str, api_key: str) -> str:
        """Construct API URL for Twelve Data with specific key"""
        base_url = "https://api.twelvedata.com/time_series"
        
        params = {
            'symbol': symbol,
            'interval': self.timeframe,
            'outputsize': self.ohlc_size,
            'apikey': api_key,
            'format': 'JSON'
        }
        
        # Build URL with parameters
        url = f"{base_url}?"
        url += "&".join([f"{k}={v}" for k, v in params.items()])
        
        return url
    
    def _parse_api_response(self, data: Dict[str, Any], symbol: str) -> Optional[pd.DataFrame]:
        """
        Parse API response into pandas DataFrame
        
        Args:
            data: Raw API response
            symbol: Original symbol for error messages
            
        Returns:
            Optional[pd.DataFrame]: Cleaned DataFrame
        """
        print(f"\n🔍 DEBUG: Starting _parse_api_response for {symbol}")
        
        try:
            # Extract values from response
            values = data.get('values', [])
            
            if not values:
                print(f"❌ ERROR: No values in API response for {symbol}")
                self.logger.warning(f"No values in API response for {symbol}")
                return None
            
            print(f"✅ Parsing {len(values)} candles from API response")
            
            # Create DataFrame
            df = pd.DataFrame(values)
            print(f"   Raw DataFrame shape: {df.shape}")
            
            # Reverse order (oldest first)
            df = df.iloc[::-1].reset_index(drop=True)
            print(f"   After reversing: {df.shape}")
            
            # Rename and select columns
            column_mapping = {
                'datetime': 'timestamp',
                'open': 'open',
                'high': 'high', 
                'low': 'low',
                'close': 'close'
            }
            
            # Only keep columns that exist
            available_columns = [col for col in column_mapping.keys() if col in df.columns]
            df = df[available_columns].copy()
            print(f"   Available columns: {available_columns}")
            
            # Rename columns
            df = df.rename(columns=column_mapping)
            print(f"   After renaming columns: {df.columns.tolist()}")
            
            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            print(f"   Converted timestamp column to datetime")
            
            # Convert price columns to float
            price_columns = ['open', 'high', 'low', 'close']
            for col in price_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            print(f"   Converted price columns to float")
            
            # Add volume if missing (set to 0)
            if 'volume' not in df.columns:
                df['volume'] = 0.0
                print(f"   Added volume column (0.0)")
            
            # Add symbol column
            df['symbol'] = symbol
            print(f"   Added symbol column: {symbol}")
            
            # Remove any rows with NaN values
            before_len = len(df)
            df = df.dropna()
            after_len = len(df)
            print(f"   Removed NaN values: {before_len - after_len} rows removed")
            
            # Ensure proper data types
            df = df.astype({
                'open': 'float64',
                'high': 'float64', 
                'low': 'float64',
                'close': 'float64',
                'volume': 'float64'
            })
            print(f"✅ Final DataFrame shape: {df.shape}")
            print(f"   First timestamp: {df['timestamp'].iloc[0] if not df.empty else 'N/A'}")
            print(f"   Last timestamp: {df['timestamp'].iloc[-1] if not df.empty else 'N/A'}")
            
            # DEBUG logging
            if not df.empty:
                self.logger.debug(f"Parsed {len(df)} rows for {symbol}")
                self.logger.debug(f"Columns: {df.columns.tolist()}")
            
            return df
            
        except Exception as e:
            print(f"❌ ERROR in _parse_api_response for {symbol}: {e}")
            self.logger.error(f"Error parsing API response for {symbol}: {e}")
            return None
    
    def _cache_data(self, symbol: str, data: pd.DataFrame) -> None:
        """Cache fetched data with timestamp"""
        cache_entry = {
            'data': data.copy(),
            'timestamp': datetime.now(),
            'symbol': symbol
        }
        self.data_cache[symbol] = cache_entry
        print(f"✅ Cached data for {symbol}")
    
    def _get_cached_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get data from cache if fresh enough"""
        if symbol not in self.data_cache:
            print(f"   No cached data found for {symbol}")
            return None
        
        cache_entry = self.data_cache[symbol]
        cache_age = (datetime.now() - cache_entry['timestamp']).total_seconds()
        
        if cache_age < self.cache_duration:
            print(f"✅ Using FRESH cached data for {symbol} ({cache_age:.0f}s old)")
            return cache_entry['data'].copy()
        else:
            # Remove stale cache entry
            print(f"   Removing STALE cached data for {symbol} ({cache_age:.0f}s old)")
            del self.data_cache[symbol]
            return None
    
    def clear_cache(self) -> None:
        """Clear all cached data"""
        self.data_cache.clear()
        print("✅ Cleared all cached data")
        self.logger.info("Data cache cleared")
    
    def get_cached_symbols(self) -> list:
        """Get list of symbols currently in cache"""
        return list(self.data_cache.keys())
    
    def fetch_all_pairs(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for all configured trading pairs
        
        Returns:
            Dict[str, pd.DataFrame]: Dictionary of symbol -> DataFrame
        """
        if not self.config:
            print("❌ ERROR: Configuration not loaded")
            self.logger.error("Configuration not loaded")
            return {}
        
        pairs = self.config.get('pairs', [])
        if not pairs:
            print("❌ WARNING: No trading pairs configured")
            self.logger.warning("No trading pairs configured")
            return {}
        
        print(f"\n🔍 DEBUG: Starting fetch_all_pairs")
        print(f"   Pairs to fetch: {len(pairs)} pairs")
        
        market_data = {}
        successful_fetches = 0
        failed_fetches = 0
        
        self.logger.info(f"Fetching data for {len(pairs)} trading pairs")
        
        # Group by API key to show progress
        key_groups = defaultdict(list)
        for symbol in pairs:
            if symbol in self.pair_assignments:
                key_name = self.pair_assignments[symbol]
                key_groups[key_name].append(symbol)
        
        print(f"\n📊 FETCHING BY API KEY GROUPS:")
        for key_name, key_pairs in key_groups.items():
            print(f"   {key_name}: {len(key_pairs)} pairs")
        
        for symbol in pairs:
            print(f"\n📊 Fetching data for {symbol}...")
            if symbol not in self.pair_assignments:
                print(f"   ⚠️ No API key assignment for {symbol}, skipping")
                failed_fetches += 1
                continue
                
            data = self.fetch_data(symbol, force_refresh=True)  # Force fresh data
            if data is not None and not data.empty:
                market_data[symbol] = data
                successful_fetches += 1
                print(f"✅ Successfully fetched {symbol}")
            else:
                failed_fetches += 1
                print(f"❌ Failed to fetch data for {symbol}")
                self.logger.warning(f"Failed to fetch data for {symbol}")
        
        print(f"\n📊 FETCHING SUMMARY:")
        print(f"   Successful: {successful_fetches}/{len(pairs)}")
        print(f"   Failed: {failed_fetches}/{len(pairs)}")
        
        self.logger.info(f"Successfully fetched {successful_fetches}/{len(pairs)} pairs")
        return market_data
    
    def validate_data_quality(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """
        Validate data quality and completeness
        
        Args:
            df: DataFrame to validate
            symbol: Symbol for logging
            
        Returns:
            Dict[str, Any]: Validation results
        """
        if df is None or df.empty:
            return {
                'valid': False,
                'reason': 'Empty or None DataFrame',
                'candles': 0
            }
        
        validation = {
            'valid': True,
            'candles': len(df),
            'missing_values': 0,
            'timestamp_gaps': 0,
            'price_anomalies': 0
        }
        
        # Check for missing values
        missing = df[['open', 'high', 'low', 'close']].isnull().sum().sum()
        validation['missing_values'] = int(missing)
        
        if missing > 0:
            validation['valid'] = False
            validation['reason'] = f'Missing {missing} price values'
        
        # Check timestamp continuity
        if 'timestamp' in df.columns:
            df_sorted = df.sort_values('timestamp')
            time_diffs = df_sorted['timestamp'].diff().dt.total_seconds()
            
            # Expected interval based on timeframe
            expected_interval = self._get_expected_interval_seconds()
            gaps = (time_diffs > expected_interval * 1.5).sum()
            validation['timestamp_gaps'] = int(gaps)
            
            if gaps > 0:
                validation['valid'] = False
                validation['reason'] = f'Found {gaps} timestamp gaps'
        
        # Check for price anomalies
        if all(col in df.columns for col in ['high', 'low', 'open', 'close']):
            anomalies = (
                (df['high'] < df['low']) |  # High < Low
                (df['open'] > df['high']) |  # Open > High
                (df['open'] < df['low']) |   # Open < Low
                (df['close'] > df['high']) | # Close > High
                (df['close'] < df['low'])    # Close < Low
            ).sum()
            validation['price_anomalies'] = int(anomalies)
            
            if anomalies > 0:
                validation['valid'] = False
                validation['reason'] = f'Found {anomalies} price anomalies'
        
        if not validation['valid']:
            print(f"⚠️ WARNING: Data quality issues for {symbol}: {validation['reason']}")
            self.logger.warning(f"Data quality issues for {symbol}: {validation['reason']}")
        
        return validation
    
    def _get_expected_interval_seconds(self) -> int:
        """Get expected time interval between candles in seconds"""
        interval_map = {
            '1min': 60,
            '5min': 300,
            '15min': 900,
            '30min': 1800,
            '1h': 3600,
            '4h': 14400,
            '1day': 86400
        }
        return interval_map.get(self.timeframe, 300)  # Default to 5min
    
    def save_data_to_csv(self, df: pd.DataFrame, symbol: str, directory: str = 'data_dumps') -> bool:
        """
        Save DataFrame to CSV for debugging
        
        Args:
            df: DataFrame to save
            symbol: Trading symbol
            directory: Directory to save files
            
        Returns:
            bool: True if saved successfully
        """
        try:
            os.makedirs(directory, exist_ok=True)
            
            filename = f"{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(directory, filename)
            
            df.to_csv(filepath, index=False)
            print(f"✅ Saved data to {filepath}")
            self.logger.debug(f"Saved data to {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ ERROR: Failed to save data to CSV: {e}")
            self.logger.error(f"Failed to save data to CSV: {e}")
            return False
    
    def get_key_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about API key usage
        
        Returns:
            Dict[str, Any]: Key usage statistics
        """
        stats = {
            'total_keys': len(self.api_keys),
            'total_pairs': len(self.pair_assignments),
            'key_distribution': {}
        }
        
        for key_name, pairs in self.key_usage.items():
            stats['key_distribution'][key_name] = {
                'pairs_count': len(pairs),
                'pairs': pairs
            }
        
        return stats
    
    def print_key_assignments(self) -> None:
        """Print API key assignments"""
        print("\n📋 API KEY ASSIGNMENTS:")
        print("=" * 60)
        
        for key_name, pairs in self.key_usage.items():
            key_status = "✅ ACTIVE" if key_name in self.api_keys and self.api_keys[key_name] else "❌ MISSING"
            print(f"\n{key_name}: {key_status}")
            print(f"   Pairs ({len(pairs)}):")
            for i, pair in enumerate(pairs, 1):
                print(f"     {i:2d}. {pair}")
        
        print("\n" + "=" * 60)


# Quick test function
if __name__ == "__main__":
    print("🧪 Testing DataFetcher with multiple keys...")
    fetcher = DataFetcher()
    
    # Load config
    if fetcher.load_config():
        # Print key assignments
        fetcher.print_key_assignments()
        
        # Test fetching one symbol
        test_symbol = "EUR/USD"
        if test_symbol in fetcher.pair_assignments:
            test_df = fetcher.fetch_data(test_symbol, force_refresh=True)
            if test_df is not None:
                print(f"\n🎉 TEST SUCCESSFUL! Loaded {len(test_df)} candles for {test_symbol}")
                print(f"   First row: {test_df.iloc[0]['timestamp']} - {test_df.iloc[0]['close']:.5f}")
                print(f"   Last row: {test_df.iloc[-1]['timestamp']} - {test_df.iloc[-1]['close']:.5f}")
            else:
                print(f"\n❌ TEST FAILED: Could not fetch data for {test_symbol}")
        else:
            print(f"\n❌ TEST FAILED: No API key assignment for {test_symbol}")
    else:
        print("\n❌ TEST FAILED: Could not load configuration")