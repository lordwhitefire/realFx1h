"""
Backtest Report - Generate and format backtest performance reports
Creates comprehensive reports from backtest results
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import os


class BacktestReport:
    """Generates comprehensive backtest performance reports"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Report configuration
        self.report_config = {
            'output_directory': 'reports',
            'include_charts': True,
            'chart_style': 'default',
            'chart_dpi': 100,
            'report_format': 'combined'  # 'combined', 'summary', 'detailed'
        }
        
        # Initialize output directory
        os.makedirs(self.report_config['output_directory'], exist_ok=True)
        os.makedirs(os.path.join(self.report_config['output_directory'], 'charts'), exist_ok=True)
        
        print(f"✅ BacktestReport initialized")
        print(f"   Chart style: {self.report_config['chart_style']}")
        print(f"   Output directory: {self.report_config['output_directory']}")
    
    def generate_comprehensive_report(self, backtest_results: Dict[str, Any], 
                                     report_name: str = None) -> Dict[str, Any]:
        """
        Generate comprehensive backtest report with charts and analysis
        
        Args:
            backtest_results: Backtest results from engine
            report_name: Custom report name
            
        Returns:
            Dict[str, Any]: Complete report data
        """
        print(f"\n📄 DEBUG: Starting generate_comprehensive_report")
        print(f"   Report name: {report_name}")
        print(f"   Backtest results keys: {list(backtest_results.keys()) if backtest_results else 'None'}")
        
        self.logger.info("Generating comprehensive backtest report")
        
        try:
            if not backtest_results:
                print("❌ ERROR: No backtest results provided")
                self.logger.error("No backtest results provided")
                return {'error': 'No backtest results'}
            
            # Create report structure
            print("   Creating report structure...")
            report = {
                'metadata': self._generate_metadata(report_name),
                'executive_summary': self._generate_executive_summary(backtest_results),
                'performance_metrics': self._generate_performance_metrics(backtest_results),
                'setup_analysis': self._generate_setup_analysis(backtest_results),
                'trade_analysis': self._generate_trade_analysis(backtest_results),
                'risk_analysis': self._generate_risk_analysis(backtest_results),
                'recommendations': backtest_results.get('recommendations', []),
                'insights': backtest_results.get('insights', []),
                'charts': {}
            }
            
            print(f"   ✅ Report structure created")
            print(f"   Setup analysis keys: {list(report['setup_analysis'].keys())}")
            
            # Generate charts if enabled
            if self.report_config['include_charts']:
                print("   Generating charts...")
                report['charts'] = self._generate_charts(backtest_results, report['metadata'])
                print(f"   Charts generated: {list(report['charts'].keys())}")
            
            # Generate text report
            print("   Generating text report...")
            report['text_report'] = self._generate_text_report(report)
            
            # Save report files
            print("   Saving report files...")
            self._save_report_files(report, backtest_results)
            
            print("✅ Backtest report generated successfully")
            self.logger.info("Backtest report generated successfully")
            return report
            
        except Exception as e:
            print(f"❌ ERROR in generate_comprehensive_report: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            self.logger.error(f"Error generating report: {e}")
            return {'error': str(e)}
    
    def _generate_metadata(self, report_name: str = None) -> Dict[str, Any]:
        """
        Generate report metadata
        
        Args:
            report_name: Custom report name
            
        Returns:
            Dict[str, Any]: Report metadata
        """
        timestamp = datetime.now()
        
        if not report_name:
            report_name = f"Backtest_Report_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        metadata = {
            'report_name': report_name,
            'generated_date': timestamp.strftime('%Y-%m-%d'),
            'generated_time': timestamp.strftime('%H:%M:%S'),
            'report_version': '1.0',
            'output_directory': self.report_config['output_directory']
        }
        
        print(f"   Generated metadata: {metadata['report_name']}")
        return metadata
    
    def _generate_executive_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate executive summary
        
        Args:
            results: Backtest results
            
        Returns:
            Dict[str, Any]: Executive summary
        """
        print("   Generating executive summary...")
        summary = results.get('summary', {})
        
        exec_summary = {
            'overview': {
                'period': results.get('period', 'Unknown'),
                'total_trades': summary.get('total_trades', 0),
                'winning_trades': summary.get('winning_trades', 0),
                'losing_trades': summary.get('losing_trades', 0),
                'win_rate': f"{summary.get('win_rate', 0):.1f}%",
                'net_profit': f"${summary.get('total_pnl', 0):.2f}",
                'net_profit_pct': f"{summary.get('total_pnl_pct', 0):.2f}%",
                'profit_factor': f"{summary.get('profit_factor', 0):.2f}",
                'initial_capital': f"${summary.get('initial_capital', 0):.2f}",
                'final_equity': f"${summary.get('final_equity', 0):.2f}"
            },
            'key_metrics': {
                'avg_trade_pnl': f"${summary.get('avg_pnl', 0):.2f}",
                'avg_trade_pct': f"{summary.get('avg_pnl_pct', 0):.2f}%",
                'largest_win': f"${summary.get('largest_win', 0):.2f}",
                'largest_loss': f"${summary.get('largest_loss', 0):.2f}",
                'sharpe_ratio': f"{summary.get('sharpe_ratio', 0):.2f}",
                'max_drawdown': f"{summary.get('max_drawdown_pct', 0):.2f}%"
            },
            'assessment': self._assess_performance(summary)
        }
        
        print(f"   Executive summary created: {summary.get('total_trades', 0)} trades, {summary.get('win_rate', 0):.1f}% win rate")
        return exec_summary
    
    def _assess_performance(self, summary: Dict[str, Any]) -> str:
        """
        Assess overall performance
        
        Args:
            summary: Performance summary
            
        Returns:
            str: Performance assessment
        """
        win_rate = summary.get('win_rate', 0)
        profit_factor = summary.get('profit_factor', 0)
        sharpe_ratio = summary.get('sharpe_ratio', 0)
        max_drawdown = abs(summary.get('max_drawdown_pct', 0))
        
        if win_rate >= 60 and profit_factor >= 2.0 and sharpe_ratio >= 1.0:
            return "EXCELLENT - Strong consistent performance"
        elif win_rate >= 55 and profit_factor >= 1.5 and sharpe_ratio >= 0.5:
            return "GOOD - Solid performance with room for improvement"
        elif win_rate >= 50 and profit_factor >= 1.2:
            return "FAIR - Barely profitable, needs optimization"
        elif win_rate < 50 or profit_factor < 1.0:
            return "POOR - Strategy is not profitable"
        else:
            return "NEEDS MORE DATA - Inconclusive results"
    
    def _generate_performance_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate detailed performance metrics
        
        Args:
            results: Backtest results
            
        Returns:
            Dict[str, Any]: Performance metrics
        """
        print("   Generating performance metrics...")
        summary = results.get('summary', {})
        
        metrics = {
            'profitability': {
                'net_profit': summary.get('total_pnl', 0),
                'net_profit_pct': summary.get('total_pnl_pct', 0),
                'gross_profit': 0,  # Would need to calculate from trades
                'gross_loss': 0,    # Would need to calculate from trades
                'profit_factor': summary.get('profit_factor', 0)
            },
            'win_loss_metrics': {
                'win_rate': summary.get('win_rate', 0),
                'avg_win': 0,  # Would need to calculate from trades
                'avg_loss': 0, # Would need to calculate from trades
                'largest_win': summary.get('largest_win', 0),
                'largest_loss': summary.get('largest_loss', 0),
                'avg_win_loss_ratio': 0  # Would need to calculate
            },
            'risk_metrics': {
                'sharpe_ratio': summary.get('sharpe_ratio', 0),
                'sortino_ratio': 0,  # Would need to calculate
                'max_drawdown': summary.get('max_drawdown_pct', 0),
                'recovery_factor': 0,  # Would need to calculate
                'ulcer_index': 0,      # Would need to calculate
                'var_95': 0           # Would need to calculate
            },
            'trade_metrics': {
                'total_trades': summary.get('total_trades', 0),
                'avg_trades_per_day': results.get('daily_analysis', {}).get('avg_trades_per_day', 0),
                'max_consecutive_wins': 0,  # Would need to calculate
                'max_consecutive_losses': 0, # Would need to calculate
                'avg_holding_period': 0,    # Would need to calculate
                'profitability_index': 0     # Would need to calculate
            }
        }
        
        # Calculate additional metrics from trades if available
        trades = results.get('trades', [])
        print(f"   Processing {len(trades)} trades for metrics...")
        
        if trades:
            trades_df = pd.DataFrame(trades)
            
            # Calculate win/loss metrics
            winning_trades = trades_df[trades_df['result'] == 'WIN']
            losing_trades = trades_df[trades_df['result'] == 'LOSS']
            
            if len(winning_trades) > 0:
                metrics['win_loss_metrics']['avg_win'] = winning_trades['pnl'].mean()
                metrics['profitability']['gross_profit'] = winning_trades['pnl'].sum()
                print(f"   Winning trades: {len(winning_trades)}, avg win: ${metrics['win_loss_metrics']['avg_win']:.2f}")
            
            if len(losing_trades) > 0:
                metrics['win_loss_metrics']['avg_loss'] = abs(losing_trades['pnl'].mean())
                metrics['profitability']['gross_loss'] = abs(losing_trades['pnl'].sum())
                print(f"   Losing trades: {len(losing_trades)}, avg loss: ${metrics['win_loss_metrics']['avg_loss']:.2f}")
            
            # Calculate win/loss ratio
            if metrics['win_loss_metrics']['avg_loss'] != 0:
                metrics['win_loss_metrics']['avg_win_loss_ratio'] = (
                    metrics['win_loss_metrics']['avg_win'] / 
                    metrics['win_loss_metrics']['avg_loss']
                )
            
            # Calculate consecutive wins/losses
            metrics['trade_metrics']['max_consecutive_wins'] = self._calculate_max_consecutive(trades_df, 'WIN')
            metrics['trade_metrics']['max_consecutive_losses'] = self._calculate_max_consecutive(trades_df, 'LOSS')
            
            # Calculate average holding period
            if 'holding_period_minutes' in trades_df.columns:
                metrics['trade_metrics']['avg_holding_period'] = trades_df['holding_period_minutes'].mean()
        
        print(f"   ✅ Performance metrics generated")
        return metrics
    
    def _calculate_max_consecutive(self, trades_df: pd.DataFrame, result_type: str) -> int:
        """
        Calculate maximum consecutive wins or losses
        
        Args:
            trades_df: Trades DataFrame
            result_type: 'WIN' or 'LOSS'
            
        Returns:
            int: Maximum consecutive count
        """
        max_count = 0
        current_count = 0
        
        for result in trades_df['result']:
            if result == result_type:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count
    
    def _generate_setup_analysis(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate setup performance analysis
        
        Args:
            results: Backtest results
            
        Returns:
            Dict[str, Any]: Setup analysis
        """
        print("   Generating setup analysis...")
        setup_perf = results.get('setup_performance', {})
        setup_ranking = results.get('setup_ranking', [])
        
        print(f"   Setup performance keys: {list(setup_perf.keys())}")
        print(f"   Setup ranking length: {len(setup_ranking)}")
        
        analysis = {
            'total_setups_tested': len(setup_perf),
            'setup_performance': {},
            'ranking': [],
            'best_performer': None,
            'worst_performer': None
        }
        
        if setup_perf:
            # Detailed performance for each setup
            for setup_name, perf in setup_perf.items():
                analysis['setup_performance'][setup_name] = {
                    'trades': perf.get('trades', 0),
                    'wins': perf.get('wins', 0),
                    'win_rate': perf.get('win_rate', 0),
                    'total_pnl': perf.get('total_pnl', 0),
                    'avg_pnl': perf.get('avg_pnl', 0),
                    'consistency_score': self._calculate_consistency_score(perf)
                }
                print(f"   Setup {setup_name}: {perf.get('trades', 0)} trades, {perf.get('win_rate', 0):.1f}% win rate")
            
            # Setup ranking
            if setup_ranking:
                analysis['ranking'] = [
                    {
                        'rank': i + 1,
                        'setup_name': item['setup_name'],
                        'score': item['score'],
                        'win_rate': item['performance'].get('win_rate', 0),
                        'trades': item['performance'].get('trades', 0)
                    }
                    for i, item in enumerate(setup_ranking[:10])  # Top 10 only
                ]
                
                # Identify best and worst performers
                analysis['best_performer'] = {
                    'setup_name': setup_ranking[0]['setup_name'],
                    'win_rate': setup_ranking[0]['performance'].get('win_rate', 0),
                    'score': setup_ranking[0]['score']
                }
                
                if len(setup_ranking) > 1:
                    analysis['worst_performer'] = {
                        'setup_name': setup_ranking[-1]['setup_name'],
                        'win_rate': setup_ranking[-1]['performance'].get('win_rate', 0),
                        'score': setup_ranking[-1]['score']
                    }
        
        print(f"   ✅ Setup analysis generated: {analysis['total_setups_tested']} setups")
        return analysis
    
    def _calculate_consistency_score(self, perf: Dict[str, Any]) -> float:
        """
        Calculate consistency score for a setup
        
        Args:
            perf: Setup performance data
            
        Returns:
            float: Consistency score (0-100)
        """
        win_rate = perf.get('win_rate', 0)
        trades = perf.get('trades', 0)
        
        if trades < 10:
            return 0  # Not enough data
        
        # Simple consistency calculation
        # Higher win rate with more trades = more consistent
        consistency = (win_rate / 100) * min(trades / 50, 1) * 100
        
        return min(consistency, 100)
    
    def _generate_trade_analysis(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate trade-level analysis
        
        Args:
            results: Backtest results
            
        Returns:
            Dict[str, Any]: Trade analysis
        """
        print("   Generating trade analysis...")
        trades = results.get('trades', [])
        
        analysis = {
            'total_trades': len(trades),
            'by_symbol': {},
            'by_time_of_day': {},
            'by_day_of_week': {},
            'best_trades': [],
            'worst_trades': [],
            'trade_distribution': {}
        }
        
        if not trades:
            print("   ⚠️ No trades for analysis")
            return analysis
        
        print(f"   Processing {len(trades)} trades...")
        trades_df = pd.DataFrame(trades)
        
        # Analyze by symbol
        if 'symbol' in trades_df.columns:
            try:
                symbol_analysis = trades_df.groupby('symbol').agg({
                    'pnl': ['count', 'sum', 'mean', 'std'],
                    'pnl_pct': ['mean', 'std'],
                    'result': lambda x: (x == 'WIN').sum() / len(x) * 100
                }).round(2)
                
                # Fix for tuple keys issue
                analysis['by_symbol'] = symbol_analysis.to_dict()
                print(f"   Symbol analysis: {list(symbol_analysis.index)}")
            except Exception as e:
                print(f"   ❌ Error in symbol analysis: {e}")
        
        # Analyze by time of day
        if 'entry_time' in trades_df.columns:
            try:
                trades_df['entry_hour'] = pd.to_datetime(trades_df['entry_time']).dt.hour
                
                hourly_analysis = trades_df.groupby('entry_hour').agg({
                    'pnl': ['count', 'sum', 'mean'],
                    'result': lambda x: (x == 'WIN').sum() / len(x) * 100
                }).round(2)
                
                # Fix for tuple keys issue
                analysis['by_time_of_day'] = hourly_analysis.to_dict()
                print(f"   Time of day analysis: {list(hourly_analysis.index)}")
            except Exception as e:
                print(f"   ❌ Error in time of day analysis: {e}")
        
        # Analyze by day of week
        if 'entry_time' in trades_df.columns:
            try:
                trades_df['day_of_week'] = pd.to_datetime(trades_df['entry_time']).dt.day_name()
                
                dow_analysis = trades_df.groupby('day_of_week').agg({
                    'pnl': ['count', 'sum', 'mean'],
                    'result': lambda x: (x == 'WIN').sum() / len(x) * 100
                }).round(2)
                
                # Fix for tuple keys issue
                analysis['by_day_of_week'] = dow_analysis.to_dict()
                print(f"   Day of week analysis: {list(dow_analysis.index)}")
            except Exception as e:
                print(f"   ❌ Error in day of week analysis: {e}")
        
        # Best and worst trades
        if 'pnl_pct' in trades_df.columns:
            try:
                best_trades = trades_df.nlargest(5, 'pnl_pct')
                worst_trades = trades_df.nsmallest(5, 'pnl_pct')
                
                analysis['best_trades'] = best_trades.to_dict('records')
                analysis['worst_trades'] = worst_trades.to_dict('records')
                print(f"   Best/worst trades: {len(best_trades)} best, {len(worst_trades)} worst")
            except Exception as e:
                print(f"   ❌ Error in best/worst trades: {e}")
        
        # Trade distribution
        if 'pnl' in trades_df.columns:
            try:
                # Bin P&L values
                bins = [-float('inf'), -10, -5, -2, -1, 0, 1, 2, 5, 10, float('inf')]
                labels = ['<-10%', '-10 to -5%', '-5 to -2%', '-2 to -1%', '-1 to 0%', 
                         '0 to 1%', '1 to 2%', '2 to 5%', '5 to 10%', '>10%']
                
                trades_df['pnl_bin'] = pd.cut(trades_df['pnl_pct'], bins=bins, labels=labels)
                distribution = trades_df['pnl_bin'].value_counts().sort_index().to_dict()
                
                analysis['trade_distribution'] = distribution
                print(f"   Trade distribution: {distribution}")
            except Exception as e:
                print(f"   ❌ Error in trade distribution: {e}")
        
        print(f"   ✅ Trade analysis generated")
        return analysis
    
    def _generate_risk_analysis(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate risk analysis
        
        Args:
            results: Backtest results
            
        Returns:
            Dict[str, Any]: Risk analysis
        """
        print("   Generating risk analysis...")
        summary = results.get('summary', {})
        equity_curve = results.get('equity_curve', [])
        
        analysis = {
            'drawdown_analysis': {
                'max_drawdown': summary.get('max_drawdown_pct', 0),
                'avg_drawdown': 0,
                'drawdown_duration': 0,
                'recovery_time': 0
            },
            'volatility_metrics': {
                'daily_volatility': 0,
                'annual_volatility': 0,
                'downside_deviation': 0
            },
            'risk_adjusted_returns': {
                'sharpe_ratio': summary.get('sharpe_ratio', 0),
                'sortino_ratio': 0,
                'calmar_ratio': 0,
                'omega_ratio': 0
            },
            'value_at_risk': {
                'var_95': 0,
                'var_99': 0,
                'cvar_95': 0,
                'cvar_99': 0
            }
        }
        
        # Calculate drawdown details if we have equity curve
        if len(equity_curve) > 1:
            try:
                equity_series = pd.Series(equity_curve)
                
                # Calculate rolling maximum
                rolling_max = equity_series.expanding().max()
                
                # Calculate drawdowns
                drawdowns = (equity_series - rolling_max) / rolling_max
                
                # Calculate average drawdown (excluding 0)
                negative_drawdowns = drawdowns[drawdowns < 0]
                if len(negative_drawdowns) > 0:
                    analysis['drawdown_analysis']['avg_drawdown'] = negative_drawdowns.mean() * 100
                
                print(f"   Drawdown analysis: max={analysis['drawdown_analysis']['max_drawdown']}%, avg={analysis['drawdown_analysis']['avg_drawdown']}%")
            except Exception as e:
                print(f"   ❌ Error in drawdown analysis: {e}")
        
        print(f"   ✅ Risk analysis generated")
        return analysis
    
    def _generate_charts(self, results: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate performance charts
        
        Args:
            results: Backtest results
            metadata: Report metadata
            
        Returns:
            Dict[str, str]: Dictionary of chart filenames
        """
        print(f"\n📊 DEBUG: Starting chart generation")
        print(f"   Available styles: {plt.style.available}")
        print(f"   Using style: {self.report_config['chart_style']}")
        
        charts = {}
        
        try:
            # Set style
            plt.style.use(self.report_config['chart_style'])
            print(f"   ✅ Style applied successfully")
            
            # Check if we have enough data for charts
            trades = results.get('trades', [])
            equity_curve = results.get('equity_curve', [])
            setup_perf = results.get('setup_performance', {})
            
            print(f"   Trades for charts: {len(trades)}")
            print(f"   Equity curve length: {len(equity_curve)}")
            print(f"   Setup performance entries: {len(setup_perf)}")
            
            # 1. Equity Curve
            if len(equity_curve) > 1:
                print("   Creating equity curve chart...")
                equity_filename = self._create_equity_curve_chart(equity_curve, metadata)
                charts['equity_curve'] = equity_filename
                print(f"   ✅ Equity curve chart: {equity_filename}")
            
            # 2. Monthly Returns
            if trades:
                print("   Creating monthly returns chart...")
                monthly_filename = self._create_monthly_returns_chart(trades, metadata)
                charts['monthly_returns'] = monthly_filename
                print(f"   ✅ Monthly returns chart: {monthly_filename}")
            
            # 3. Win Rate by Setup
            if setup_perf:
                print("   Creating setup performance chart...")
                setup_filename = self._create_setup_performance_chart(setup_perf, metadata)
                charts['setup_performance'] = setup_filename
                print(f"   ✅ Setup performance chart: {setup_filename}")
            
            # 4. P&L Distribution
            if trades:
                print("   Creating P&L distribution chart...")
                distribution_filename = self._create_pnl_distribution_chart(trades, metadata)
                charts['pnl_distribution'] = distribution_filename
                print(f"   ✅ P&L distribution chart: {distribution_filename}")
            
            # 5. Drawdown Chart
            if len(equity_curve) > 1:
                print("   Creating drawdown chart...")
                drawdown_filename = self._create_drawdown_chart(equity_curve, metadata)
                charts['drawdown'] = drawdown_filename
                print(f"   ✅ Drawdown chart: {drawdown_filename}")
            
            print(f"✅ Generated {len(charts)} charts")
            self.logger.info(f"Generated {len(charts)} charts")
            
        except Exception as e:
            print(f"❌ ERROR in chart generation: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            self.logger.error(f"Error generating charts: {e}")
        
        return charts
    
    def _create_equity_curve_chart(self, equity_curve: List[float], 
                                  metadata: Dict[str, Any]) -> str:
        """Create equity curve chart"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot equity curve
        ax.plot(equity_curve, linewidth=2, color='blue', alpha=0.7)
        
        # Add horizontal line at starting capital
        ax.axhline(y=equity_curve[0], color='red', linestyle='--', alpha=0.5, 
                  label=f'Starting: ${equity_curve[0]:,.0f}')
        
        # Add horizontal line at final equity
        ax.axhline(y=equity_curve[-1], color='green', linestyle='--', alpha=0.5,
                  label=f'Final: ${equity_curve[-1]:,.0f}')
        
        ax.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax.set_xlabel('Trade Number', fontsize=12)
        ax.set_ylabel('Account Equity ($)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Save chart
        filename = f"equity_curve_{metadata['generated_date']}.png"
        filepath = os.path.join(self.report_config['output_directory'], 'charts', filename)
        plt.tight_layout()
        plt.savefig(filepath, dpi=self.report_config['chart_dpi'])
        plt.close()
        
        return filename
    
    def _create_monthly_returns_chart(self, trades: List[Dict[str, Any]], 
                                     metadata: Dict[str, Any]) -> str:
        """Create monthly returns chart"""
        if not trades:
            return ""
        
        trades_df = pd.DataFrame(trades)
        trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
        trades_df['month'] = trades_df['entry_time'].dt.to_period('M')
        
        # Calculate monthly returns
        monthly_returns = trades_df.groupby('month')['pnl_pct'].sum()
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Create bar chart
        colors = ['red' if x < 0 else 'green' for x in monthly_returns.values]
        bars = ax.bar(range(len(monthly_returns)), monthly_returns.values, color=colors, alpha=0.7)
        
        ax.set_title('Monthly Returns (%)', fontsize=14, fontweight='bold')
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Return (%)', fontsize=12)
        ax.set_xticks(range(len(monthly_returns)))
        ax.set_xticklabels([str(period) for period in monthly_returns.index], rotation=45)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%', ha='center', va='bottom' if height >= 0 else 'top',
                   fontsize=9)
        
        # Save chart
        filename = f"monthly_returns_{metadata['generated_date']}.png"
        filepath = os.path.join(self.report_config['output_directory'], 'charts', filename)
        plt.tight_layout()
        plt.savefig(filepath, dpi=self.report_config['chart_dpi'])
        plt.close()
        
        return filename
    
    def _create_setup_performance_chart(self, setup_perf: Dict[str, Any], 
                                       metadata: Dict[str, Any]) -> str:
        """Create setup performance comparison chart"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Prepare data
        setups = list(setup_perf.keys())
        win_rates = [perf.get('win_rate', 0) for perf in setup_perf.values()]
        trades_count = [perf.get('trades', 0) for perf in setup_perf.values()]
        
        # Sort by win rate
        sorted_data = sorted(zip(setups, win_rates, trades_count), 
                            key=lambda x: x[1], reverse=True)
        setups, win_rates, trades_count = zip(*sorted_data) if sorted_data else ([], [], [])
        
        # Chart 1: Win Rates
        bars1 = ax1.barh(setups, win_rates, color='skyblue', alpha=0.7)
        ax1.set_xlabel('Win Rate (%)', fontsize=12)
        ax1.set_title('Win Rate by Setup', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='x')
        
        # Add value labels
        for bar in bars1:
            width = bar.get_width()
            ax1.text(width, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f}%', ha='left', va='center', fontsize=9)
        
        # Chart 2: Number of Trades
        bars2 = ax2.barh(setups, trades_count, color='lightgreen', alpha=0.7)
        ax2.set_xlabel('Number of Trades', fontsize=12)
        ax2.set_title('Trade Frequency by Setup', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='x')
        
        # Add value labels
        for bar in bars2:
            width = bar.get_width()
            ax2.text(width, bar.get_y() + bar.get_height()/2,
                    f'{int(width)}', ha='left', va='center', fontsize=9)
        
        # Save chart
        filename = f"setup_performance_{metadata['generated_date']}.png"
        filepath = os.path.join(self.report_config['output_directory'], 'charts', filename)
        plt.tight_layout()
        plt.savefig(filepath, dpi=self.report_config['chart_dpi'])
        plt.close()
        
        return filename
    
    def _create_pnl_distribution_chart(self, trades: List[Dict[str, Any]], 
                                      metadata: Dict[str, Any]) -> str:
        """Create P&L distribution histogram"""
        trades_df = pd.DataFrame(trades)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Create histogram
        ax.hist(trades_df['pnl_pct'], bins=30, alpha=0.7, color='steelblue', 
               edgecolor='black')
        
        # Add mean line
        mean_pnl = trades_df['pnl_pct'].mean()
        ax.axvline(mean_pnl, color='red', linestyle='--', linewidth=2,
                  label=f'Mean: {mean_pnl:.2f}%')
        
        # Add median line
        median_pnl = trades_df['pnl_pct'].median()
        ax.axvline(median_pnl, color='green', linestyle='--', linewidth=2,
                  label=f'Median: {median_pnl:.2f}%')
        
        ax.set_title('P&L Distribution', fontsize=14, fontweight='bold')
        ax.set_xlabel('P&L (%)', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Save chart
        filename = f"pnl_distribution_{metadata['generated_date']}.png"
        filepath = os.path.join(self.report_config['output_directory'], 'charts', filename)
        plt.tight_layout()
        plt.savefig(filepath, dpi=self.report_config['chart_dpi'])
        plt.close()
        
        return filename
    
    def _create_drawdown_chart(self, equity_curve: List[float], 
                              metadata: Dict[str, Any]) -> str:
        """Create drawdown chart"""
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdowns = (equity_series - rolling_max) / rolling_max * 100
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot drawdowns
        ax.fill_between(range(len(drawdowns)), drawdowns, 0, 
                       where=drawdowns < 0, color='red', alpha=0.3)
        ax.plot(drawdowns, color='darkred', linewidth=1, alpha=0.7)
        
        # Add horizontal line at max drawdown
        max_dd = drawdowns.min()
        ax.axhline(y=max_dd, color='red', linestyle='--', alpha=0.5,
                  label=f'Max Drawdown: {max_dd:.2f}%')
        
        ax.set_title('Drawdown Analysis', fontsize=14, fontweight='bold')
        ax.set_xlabel('Trade Number', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Save chart
        filename = f"drawdown_{metadata['generated_date']}.png"
        filepath = os.path.join(self.report_config['output_directory'], 'charts', filename)
        plt.tight_layout()
        plt.savefig(filepath, dpi=self.report_config['chart_dpi'])
        plt.close()
        
        return filename
    
    def _generate_text_report(self, report: Dict[str, Any]) -> str:
        """
        Generate formatted text report
        
        Args:
            report: Complete report data
            
        Returns:
            str: Formatted text report
        """
        text = []
        
        # Header
        metadata = report['metadata']
        text.append("=" * 80)
        text.append(f"BACKTEST PERFORMANCE REPORT")
        text.append("=" * 80)
        text.append(f"Report: {metadata['report_name']}")
        text.append(f"Generated: {metadata['generated_date']} {metadata['generated_time']}")
        text.append("")
        
        # Executive Summary
        exec_summary = report['executive_summary']['overview']
        text.append("EXECUTIVE SUMMARY")
        text.append("-" * 40)
        text.append(f"Period: {exec_summary['period']}")
        text.append(f"Total Trades: {exec_summary['total_trades']}")
        text.append(f"Win Rate: {exec_summary['win_rate']}")
        text.append(f"Net Profit: {exec_summary['net_profit']} ({exec_summary['net_profit_pct']})")
        text.append(f"Profit Factor: {exec_summary['profit_factor']}")
        text.append(f"Initial Capital: {exec_summary['initial_capital']}")
        text.append(f"Final Equity: {exec_summary['final_equity']}")
        text.append(f"Assessment: {report['executive_summary']['assessment']}")
        text.append("")
        
        # Setup Analysis
        setup_analysis = report['setup_analysis']
        if setup_analysis['total_setups_tested'] > 0:
            text.append("SETUP PERFORMANCE")
            text.append("-" * 40)
            
            ranking = setup_analysis['ranking']
            if ranking:
                text.append("Top Performers:")
                for item in ranking[:5]:  # Top 5 only
                    text.append(f"  {item['rank']}. {item['setup_name']}: "
                               f"{item['win_rate']:.1f}% win rate ({item['trades']} trades)")
            
            if setup_analysis['best_performer']:
                best = setup_analysis['best_performer']
                text.append(f"\nBest Performer: {best['setup_name']} "
                           f"({best['win_rate']:.1f}% win rate)")
            
            text.append("")
        
        # Key Metrics
        key_metrics = report['executive_summary']['key_metrics']
        text.append("KEY METRICS")
        text.append("-" * 40)
        text.append(f"Average Trade P&L: {key_metrics['avg_trade_pnl']} "
                   f"({key_metrics['avg_trade_pct']})")
        text.append(f"Largest Win: {key_metrics['largest_win']}")
        text.append(f"Largest Loss: {key_metrics['largest_loss']}")
        text.append(f"Sharpe Ratio: {key_metrics['sharpe_ratio']}")
        text.append(f"Maximum Drawdown: {key_metrics['max_drawdown']}")
        text.append("")
        
        # Recommendations
        recommendations = report['recommendations']
        if recommendations:
            text.append("RECOMMENDATIONS")
            text.append("-" * 40)
            for rec in recommendations:
                text.append(f"• {rec}")
            text.append("")
        
        # Insights
        insights = report['insights']
        if insights:
            text.append("INSIGHTS")
            text.append("-" * 40)
            for insight in insights:
                text.append(f"• {insight}")
            text.append("")
        
        # Footer
        text.append("=" * 80)
        text.append("End of Report")
        text.append("=" * 80)
        
        return "\n".join(text)
    
    def _save_report_files(self, report: Dict[str, Any], results: Dict[str, Any]) -> None:
        """
        Save report files to disk
        
        Args:
            report: Complete report data
            results: Raw backtest results
        """
        print(f"\n💾 DEBUG: Starting to save report files")
        metadata = report['metadata']
        base_filename = metadata['report_name']
        
        try:
            # 1. Save text report
            text_filename = os.path.join(self.report_config['output_directory'], 
                                        f"{base_filename}.txt")
            print(f"   Saving text report to: {text_filename}")
            with open(text_filename, 'w', encoding='utf-8') as f:
                f.write(report['text_report'])
            print(f"   ✅ Text report saved")
            
            # 2. Save SIMPLIFIED JSON report (skip problematic data with tuple keys)
            import json
            json_filename = os.path.join(self.report_config['output_directory'], 
                                        f"{base_filename}_summary.json")
            print(f"   Saving simplified JSON report to: {json_filename}")
            
            # Save only essential, clean data (no tuple keys)
            essential_data = {
                'metadata': report.get('metadata', {}),
                'executive_summary': report.get('executive_summary', {}),
                'performance_summary': {
                    'total_trades': report.get('executive_summary', {}).get('overview', {}).get('total_trades', 0),
                    'win_rate': report.get('executive_summary', {}).get('overview', {}).get('win_rate', '0%'),
                    'net_profit': report.get('executive_summary', {}).get('overview', {}).get('net_profit', '$0.00'),
                    'profit_factor': report.get('executive_summary', {}).get('overview', {}).get('profit_factor', '0.00'),
                    'period': report.get('executive_summary', {}).get('overview', {}).get('period', 'Unknown')
                },
                'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'chart_files': list(report.get('charts', {}).keys())
            }
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(essential_data, f, indent=2)
            print(f"   ✅ Simplified JSON report saved")
            
            # 3. Save trades to CSV
            trades = results.get('trades', [])
            if trades:
                trades_filename = os.path.join(self.report_config['output_directory'], 
                                             f"{base_filename}_trades.csv")
                print(f"   Saving trades CSV to: {trades_filename}")
                trades_df = pd.DataFrame(trades)
                trades_df.to_csv(trades_filename, index=False)
                print(f"   ✅ Trades CSV saved: {len(trades)} trades")
            
            # 4. Save summary as CSV - USING SIMPLIFIED DATA (no tuple keys)
            summary_filename = os.path.join(self.report_config['output_directory'], 
                                          f"{base_filename}_summary.csv")
            print(f"   Saving summary CSV to: {summary_filename}")
            
            # Create simple summary data (avoid tuple keys)
            summary_data = []
            
            # Add executive summary
            exec_summary = report.get('executive_summary', {}).get('overview', {})
            for key, value in exec_summary.items():
                summary_data.append({'category': 'executive_summary', 'metric': key, 'value': value})
            
            # Add key metrics
            key_metrics = report.get('executive_summary', {}).get('key_metrics', {})
            for key, value in key_metrics.items():
                summary_data.append({'category': 'key_metrics', 'metric': key, 'value': value})
            
            # Add performance assessment
            assessment = report.get('executive_summary', {}).get('assessment', '')
            summary_data.append({'category': 'assessment', 'metric': 'performance_assessment', 'value': assessment})
            
            # Add setup performance
            setup_perf = results.get('setup_performance', {})
            for setup_name, perf in setup_perf.items():
                summary_data.append({
                    'category': 'setup_performance',
                    'metric': f"{setup_name}_trades",
                    'value': perf.get('trades', 0)
                })
                summary_data.append({
                    'category': 'setup_performance', 
                    'metric': f"{setup_name}_win_rate",
                    'value': f"{perf.get('win_rate', 0):.1f}%"
                })
            
            if summary_data:
                print(f"   Creating DataFrame from {len(summary_data)} rows...")
                summary_df = pd.DataFrame(summary_data)
                print(f"   DataFrame shape: {summary_df.shape}")
                print(f"   DataFrame columns: {list(summary_df.columns)}")
                summary_df.to_csv(summary_filename, index=False)
                print(f"   ✅ Summary CSV saved")
            else:
                print("   ⚠️ No summary data to save")
            
            print(f"✅ All report files saved to {self.report_config['output_directory']}")
            print(f"📊 YOUR RESULTS: {exec_summary.get('total_trades', 0)} trades, {exec_summary.get('win_rate', '0%')} win rate, {exec_summary.get('net_profit', '$0.00')} profit")
            self.logger.info(f"Report saved to {self.report_config['output_directory']}")
            
        except Exception as e:
            print(f"❌ ERROR saving report files: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            self.logger.error(f"Error saving report files: {e}")   
    def _flatten_dict_for_csv(self, data: Dict[str, Any], prefix: str, 
                            result: List[Dict[str, Any]]) -> None:
        """
        Flatten nested dictionary for CSV export
        
        Args:
            data: Dictionary to flatten
            prefix: Key prefix
            result: List to store flattened items
        """
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            # Debug: Print key and type
            print(f"      Processing key: {full_key} (type: {type(key)})")
            
            if isinstance(value, dict):
                self._flatten_dict_for_csv(value, full_key, result)
            elif isinstance(value, (list, tuple)):
                # Convert lists to strings
                result.append({'key': full_key, 'value': str(value)})
            else:
                result.append({'key': full_key, 'value': value})
    
    def _safe_flatten_dict(self, data: Dict[str, Any], prefix: str, 
                         result: List[Dict[str, Any]]) -> None:
        """
        Safer method to flatten dictionary (handles tuple keys)
        
        Args:
            data: Dictionary to flatten
            prefix: Key prefix
            result: List to store flattened items
        """
        for key, value in data.items():
            # Convert tuple keys to strings
            if isinstance(key, tuple):
                key_str = '_'.join(str(k) for k in key if k)
                full_key = f"{prefix}.{key_str}" if prefix else key_str
            else:
                full_key = f"{prefix}.{key}" if prefix else str(key)
            
            if isinstance(value, dict):
                self._safe_flatten_dict(value, full_key, result)
            elif isinstance(value, (list, tuple)):
                # Convert lists to strings
                result.append({'key': full_key, 'value': str(value)})
            else:
                result.append({'key': full_key, 'value': value})
    
    def generate_quick_summary(self, results: Dict[str, Any]) -> str:
        """
        Generate quick summary report (for console/telegram)
        
        Args:
            results: Backtest results
            
        Returns:
            str: Quick summary text
        """
        print("   Generating quick summary...")
        
        if not results:
            return "No backtest results available"
        
        summary = results.get('summary', {})
        period = results.get('period', 'Unknown')
        
        text = []
        text.append("📊 BACKTEST SUMMARY")
        text.append(f"Period: {period}")
        text.append(f"Trades: {summary.get('total_trades', 0)}")
        text.append(f"Win Rate: {summary.get('win_rate', 0):.1f}%")
        text.append(f"Net P&L: ${summary.get('total_pnl', 0):.2f} "
                   f"({summary.get('total_pnl_pct', 0):.2f}%)")
        text.append(f"Profit Factor: {summary.get('profit_factor', 0):.2f}")
        text.append(f"Sharpe Ratio: {summary.get('sharpe_ratio', 0):.2f}")
        text.append(f"Max Drawdown: {summary.get('max_drawdown_pct', 0):.2f}%")
        
        # Add top setup if available
        setup_ranking = results.get('setup_ranking', [])
        if setup_ranking:
            top_setup = setup_ranking[0]
            text.append(f"\n🏆 Top Setup: {top_setup['setup_name']}")
            text.append(f"   Win Rate: {top_setup['performance'].get('win_rate', 0):.1f}%")
        
        print("   ✅ Quick summary generated")
        return "\n".join(text)


# Quick test
if __name__ == "__main__":
    print("🧪 Testing BacktestReport directly...")
    report = BacktestReport()
    print("✅ BacktestReport created successfully")