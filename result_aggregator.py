"""
Result Aggregator - Collects, filters, and aggregates setup results
Processes results from all setups and prepares for alerts/reporting
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np


class ResultAggregator:
    """Aggregates and processes results from all trading setups"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configuration defaults
        self.min_confidence = 70  # Minimum confidence percentage
        self.max_alerts_per_cycle = 3  # Maximum alerts per scanning cycle
        self.result_history = []  # Store recent results for analysis
        self.max_history_size = 100
        
        # Performance tracking
        self.performance_stats = {}
    
    def aggregate_results(self, all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate all setup results into summary statistics
        
        Args:
            all_results: List of result dictionaries from all setups
            
        Returns:
            Dict[str, Any]: Aggregated statistics
        """
        if not all_results:
            return self._get_empty_aggregation()
        
        try:
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(all_results)
            
            # Basic statistics
            total_setups = len(all_results)
            total_signals = len([r for r in all_results if r.get('signal_type')])
            
            # Group by setup
            setup_groups = df.groupby('setup_name')
            setup_stats = {}
            
            for setup_name, group in setup_groups:
                setup_signals = len([r for r in group.to_dict('records') if r.get('signal_type')])
                avg_confidence = group['confidence'].mean() if 'confidence' in group.columns else 0
                
                setup_stats[setup_name] = {
                    'total_analyses': len(group),
                    'signals_found': int(setup_signals),
                    'signal_rate': (setup_signals / len(group) * 100) if len(group) > 0 else 0,
                    'avg_confidence': float(avg_confidence)
                }
            
            # Group by symbol
            symbol_groups = df.groupby('symbol')
            symbol_stats = {}
            
            for symbol, group in symbol_groups:
                symbol_signals = len([r for r in group.to_dict('records') if r.get('signal_type')])
                
                symbol_stats[symbol] = {
                    'total_analyses': len(group),
                    'signals_found': int(symbol_signals),
                    'signal_rate': (symbol_signals / len(group) * 100) if len(group) > 0 else 0
                }
            
            # Signal type distribution
            signal_types = {}
            for result in all_results:
                signal_type = result.get('signal_type')
                if signal_type:
                    signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
            
            # Confidence distribution
            confidences = [r.get('confidence', 0) for r in all_results if r.get('confidence')]
            confidence_stats = {
                'min': float(min(confidences)) if confidences else 0,
                'max': float(max(confidences)) if confidences else 0,
                'avg': float(np.mean(confidences)) if confidences else 0,
                'median': float(np.median(confidences)) if confidences else 0
            }
            
            # Update history
            self._update_history(all_results)
            
            # Calculate performance metrics if we have historical data
            performance_metrics = self._calculate_performance_metrics()
            
            aggregation = {
                'timestamp': datetime.now(),
                'total_setups_analyzed': total_setups,
                'total_signals_found': total_signals,
                'signal_rate': (total_signals / total_setups * 100) if total_setups > 0 else 0,
                'setup_statistics': setup_stats,
                'symbol_statistics': symbol_stats,
                'signal_distribution': signal_types,
                'confidence_statistics': confidence_stats,
                'performance_metrics': performance_metrics,
                'raw_count': len(all_results)
            }
            
            self.logger.debug(f"Aggregated {total_setups} results, found {total_signals} signals")
            return aggregation
            
        except Exception as e:
            self.logger.error(f"Error aggregating results: {e}")
            return self._get_empty_aggregation()
    
    def _get_empty_aggregation(self) -> Dict[str, Any]:
        """Return empty aggregation structure"""
        return {
            'timestamp': datetime.now(),
            'total_setups_analyzed': 0,
            'total_signals_found': 0,
            'signal_rate': 0,
            'setup_statistics': {},
            'symbol_statistics': {},
            'signal_distribution': {},
            'confidence_statistics': {'min': 0, 'max': 0, 'avg': 0, 'median': 0},
            'performance_metrics': {},
            'raw_count': 0
        }
    
    def filter_significant_results(self, all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter results to only significant signals worthy of alerts
        
        Args:
            all_results: All result dictionaries
            
        Returns:
            List[Dict[str, Any]]: Filtered significant results
        """
        if not all_results:
            return []
        
        significant_results = []
        
        for result in all_results:
            if self._is_significant_result(result):
                # Add ranking score
                result['alert_score'] = self._calculate_alert_score(result)
                significant_results.append(result)
        
        # Sort by alert score (descending)
        significant_results.sort(key=lambda x: x.get('alert_score', 0), reverse=True)
        
        # Limit number of alerts
        if len(significant_results) > self.max_alerts_per_cycle:
            significant_results = significant_results[:self.max_alerts_per_cycle]
        
        self.logger.debug(f"Filtered {len(significant_results)} significant results from {len(all_results)} total")
        return significant_results
    
    def _is_significant_result(self, result: Dict[str, Any]) -> bool:
        """
        Check if a result is significant enough to trigger an alert
        
        Args:
            result: Single result dictionary
            
        Returns:
            bool: True if significant
        """
        # Must have a signal type
        if not result.get('signal_type'):
            return False
        
        # Check minimum confidence
        confidence = result.get('confidence', 0)
        if confidence < self.min_confidence:
            return False
        
        # Check if result has required fields
        required_fields = ['symbol', 'setup_name', 'pattern_name']
        for field in required_fields:
            if not result.get(field):
                return False
        
        # Check for recent duplicate signals (based on symbol and setup)
        if self._is_duplicate_signal(result):
            return False
        
        # Additional significance checks can be added here:
        # - Volume confirmation
        # - Multiple time frame alignment
        # - Support/resistance strength
        # - News/sentiment alignment
        
        return True
    
    def _calculate_alert_score(self, result: Dict[str, Any]) -> float:
        """
        Calculate alert score for ranking results
        
        Args:
            result: Single result dictionary
            
        Returns:
            float: Alert score (higher = more significant)
        """
        score = 0.0
        
        # Base score from confidence
        confidence = result.get('confidence', 0)
        score += confidence * 0.8  # 80% weight to confidence
        
        # Bonus for high RSI extremes
        rsi = result.get('rsi', 50)
        if rsi < 30 or rsi > 70:
            score += 10
        
        # Bonus for strong support/resistance
        sr_strength = result.get('support_resistance_strength', 0)
        if sr_strength > 0:
            score += sr_strength * 5
        
        # Bonus for volume confirmation
        volume_confirmation = result.get('volume_confirmation', False)
        if volume_confirmation:
            score += 15
        
        # Bonus for multiple time frame alignment
        timeframe_alignment = result.get('timeframe_alignment', 0)
        score += timeframe_alignment * 10
        
        # Penalty for recent alerts on same symbol/setup
        if self._is_recent_alert(result):
            score -= 20
        
        # Ensure score is between 0-100
        return max(0, min(100, score))
    
    def _is_duplicate_signal(self, result: Dict[str, Any]) -> bool:
        """
        Check if this is a duplicate of a recent signal
        
        Args:
            result: Result to check
            
        Returns:
            bool: True if duplicate
        """
        symbol = result.get('symbol')
        setup_name = result.get('setup_name')
        signal_type = result.get('signal_type')
        
        if not all([symbol, setup_name, signal_type]):
            return False
        
        # Check history for similar recent signals
        for historical in self.result_history[-10:]:  # Check last 10 results
            hist_result = historical.get('result', {})
            
            if (hist_result.get('symbol') == symbol and
                hist_result.get('setup_name') == setup_name and
                hist_result.get('signal_type') == signal_type):
                
                # Check if within last 30 minutes
                hist_time = historical.get('timestamp')
                if isinstance(hist_time, datetime):
                    time_diff = (datetime.now() - hist_time).total_seconds() / 60
                    if time_diff < 30:  # 30 minutes
                        return True
        
        return False
    
    def _is_recent_alert(self, result: Dict[str, Any]) -> bool:
        """
        Check if there was a recent alert for this symbol
        
        Args:
            result: Result to check
            
        Returns:
            bool: True if recent alert exists
        """
        symbol = result.get('symbol')
        
        if not symbol:
            return False
        
        # Check last 5 alerts in history
        recent_alerts = [h for h in self.result_history[-5:] 
                        if h.get('result', {}).get('symbol') == symbol]
        
        return len(recent_alerts) > 0
    
    def _update_history(self, results: List[Dict[str, Any]]) -> None:
        """
        Update result history
        
        Args:
            results: List of results to add to history
        """
        for result in results:
            history_entry = {
                'timestamp': datetime.now(),
                'result': result.copy()
            }
            self.result_history.append(history_entry)
        
        # Trim history if too large
        if len(self.result_history) > self.max_history_size:
            self.result_history = self.result_history[-self.max_history_size:]
    
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate performance metrics from historical data
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        if len(self.result_history) < 10:  # Need minimum data
            return {}
        
        try:
            # Convert history to DataFrame
            history_data = []
            for entry in self.result_history:
                result = entry['result']
                if result.get('signal_type'):
                    history_data.append({
                        'timestamp': entry['timestamp'],
                        'symbol': result.get('symbol'),
                        'setup': result.get('setup_name'),
                        'signal': result.get('signal_type'),
                        'confidence': result.get('confidence', 0),
                        'pattern': result.get('pattern_name')
                    })
            
            if not history_data:
                return {}
            
            df = pd.DataFrame(history_data)
            
            # Calculate metrics
            total_signals = len(df)
            
            # Setup performance
            setup_perf = {}
            setup_groups = df.groupby('setup')
            for setup, group in setup_groups:
                setup_perf[setup] = {
                    'signals': len(group),
                    'avg_confidence': group['confidence'].mean(),
                    'unique_symbols': group['symbol'].nunique(),
                    'most_common_pattern': group['pattern'].mode().iloc[0] if not group['pattern'].mode().empty else 'N/A'
                }
            
            # Symbol activity
            symbol_activity = {}
            symbol_groups = df.groupby('symbol')
            for symbol, group in symbol_groups:
                symbol_activity[symbol] = {
                    'signals': len(group),
                    'avg_confidence': group['confidence'].mean(),
                    'active_setups': group['setup'].nunique()
                }
            
            # Time-based analysis
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            hourly_activity = df.groupby('hour').size().to_dict()
            
            # Signal type distribution
            signal_dist = df['signal'].value_counts().to_dict()
            
            return {
                'total_signals_tracked': total_signals,
                'setup_performance': setup_perf,
                'symbol_activity': symbol_activity,
                'hourly_activity': hourly_activity,
                'signal_distribution': signal_dist,
                'tracking_period_hours': (datetime.now() - df['timestamp'].min()).total_seconds() / 3600
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def generate_detailed_report(self, aggregated_results: Dict[str, Any]) -> str:
        """
        Generate detailed text report from aggregated results
        
        Args:
            aggregated_results: Aggregated results dictionary
            
        Returns:
            str: Formatted report text
        """
        report = []
        
        # Header
        report.append("=" * 60)
        report.append("TRADING SETUP ANALYSIS REPORT")
        report.append("=" * 60)
        
        timestamp = aggregated_results.get('timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            report.append(f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        else:
            report.append(f"Time: {timestamp}")
        
        # Summary
        total_setups = aggregated_results.get('total_setups_analyzed', 0)
        total_signals = aggregated_results.get('total_signals_found', 0)
        signal_rate = aggregated_results.get('signal_rate', 0)
        
        report.append(f"\n📊 SUMMARY:")
        report.append(f"  Total Analyses: {total_setups}")
        report.append(f"  Signals Found: {total_signals}")
        report.append(f"  Signal Rate: {signal_rate:.1f}%")
        
        # Setup Statistics
        setup_stats = aggregated_results.get('setup_statistics', {})
        if setup_stats:
            report.append(f"\n📋 SETUP PERFORMANCE:")
            for setup_name, stats in setup_stats.items():
                signals = stats.get('signals_found', 0)
                analyses = stats.get('total_analyses', 0)
                rate = stats.get('signal_rate', 0)
                confidence = stats.get('avg_confidence', 0)
                
                report.append(f"  {setup_name}:")
                report.append(f"    Analyses: {analyses}, Signals: {signals}")
                report.append(f"    Signal Rate: {rate:.1f}%, Avg Confidence: {confidence:.1f}%")
        
        # Symbol Statistics
        symbol_stats = aggregated_results.get('symbol_statistics', {})
        if symbol_stats:
            report.append(f"\n💰 SYMBOL ACTIVITY:")
            for symbol, stats in symbol_stats.items():
                signals = stats.get('signals_found', 0)
                rate = stats.get('signal_rate', 0)
                
                report.append(f"  {symbol}: {signals} signals ({rate:.1f}%)")
        
        # Signal Distribution
        signal_dist = aggregated_results.get('signal_distribution', {})
        if signal_dist:
            report.append(f"\n📈 SIGNAL DISTRIBUTION:")
            for signal_type, count in signal_dist.items():
                percentage = (count / total_signals * 100) if total_signals > 0 else 0
                report.append(f"  {signal_type}: {count} ({percentage:.1f}%)")
        
        # Confidence Statistics
        conf_stats = aggregated_results.get('confidence_statistics', {})
        if conf_stats:
            report.append(f"\n🎯 CONFIDENCE LEVELS:")
            report.append(f"  Min: {conf_stats.get('min', 0):.1f}%")
            report.append(f"  Max: {conf_stats.get('max', 0):.1f}%")
            report.append(f"  Avg: {conf_stats.get('avg', 0):.1f}%")
            report.append(f"  Median: {conf_stats.get('median', 0):.1f}%")
        
        # Performance Metrics
        perf_metrics = aggregated_results.get('performance_metrics', {})
        if perf_metrics:
            report.append(f"\n📊 HISTORICAL PERFORMANCE:")
            report.append(f"  Total Signals Tracked: {perf_metrics.get('total_signals_tracked', 0)}")
            
            tracking_hours = perf_metrics.get('tracking_period_hours', 0)
            if tracking_hours > 0:
                signals_per_hour = perf_metrics.get('total_signals_tracked', 0) / tracking_hours
                report.append(f"  Signals/Hour: {signals_per_hour:.2f}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
    
    def save_results_to_csv(self, all_results: List[Dict[str, Any]], 
                           filename: str = None) -> bool:
        """
        Save results to CSV file for analysis
        
        Args:
            all_results: List of result dictionaries
            filename: Output filename (optional)
            
        Returns:
            bool: True if saved successfully
        """
        if not all_results:
            self.logger.warning("No results to save")
            return False
        
        try:
            # Create filename if not provided
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"logs/analysis_results_{timestamp}.csv"
            
            # Flatten results
            flat_results = []
            for result in all_results:
                flat_result = {
                    'timestamp': result.get('timestamp', datetime.now()),
                    'symbol': result.get('symbol', ''),
                    'setup_name': result.get('setup_name', ''),
                    'signal_type': result.get('signal_type', ''),
                    'pattern_name': result.get('pattern_name', ''),
                    'confidence': result.get('confidence', 0),
                    'rsi': result.get('rsi', ''),
                    'current_price': result.get('current_price', 0),
                    'entry_price': result.get('entry_price', 0),
                    'support_resistance_level': result.get('support_resistance_level', ''),
                    'level_type': result.get('level_type', ''),
                    'signal_strength': result.get('signal_strength', 0),
                    'alert_score': result.get('alert_score', 0)
                }
                flat_results.append(flat_result)
            
            # Convert to DataFrame and save
            df = pd.DataFrame(flat_results)
            df.to_csv(filename, index=False)
            
            self.logger.info(f"Saved {len(all_results)} results to {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving results to CSV: {e}")
            return False
    
    def get_history_summary(self) -> Dict[str, Any]:
        """
        Get summary of historical results
        
        Returns:
            Dict[str, Any]: History summary
        """
        if not self.result_history:
            return {'total_results': 0}
        
        # Convert to DataFrame for analysis
        try:
            history_data = []
            for entry in self.result_history:
                result = entry['result']
                history_data.append({
                    'timestamp': entry['timestamp'],
                    'has_signal': bool(result.get('signal_type')),
                    'confidence': result.get('confidence', 0),
                    'symbol': result.get('symbol'),
                    'setup': result.get('setup_name')
                })
            
            df = pd.DataFrame(history_data)
            
            summary = {
                'total_results': len(df),
                'total_signals': df['has_signal'].sum(),
                'signal_percentage': (df['has_signal'].sum() / len(df) * 100) if len(df) > 0 else 0,
                'avg_confidence': df['confidence'].mean() if not df['confidence'].empty else 0,
                'unique_symbols': df['symbol'].nunique() if not df['symbol'].empty else 0,
                'unique_setups': df['setup'].nunique() if not df['setup'].empty else 0,
                'time_span_hours': (datetime.now() - df['timestamp'].min()).total_seconds() / 3600 if len(df) > 0 else 0
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating history summary: {e}")
            return {'total_results': len(self.result_history)}
    
    def clear_history(self) -> None:
        """Clear all historical data"""
        self.result_history.clear()
        self.logger.info("Cleared result history")