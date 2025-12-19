"""
Setup Loader - Dynamically loads trading setup modules
Discovers and imports all setup modules from the setups directory
"""

import os
import importlib
import yaml
import logging
from typing import Dict, Any, Optional, List
import sys


class SetupLoader:
    """Loads and manages trading setup modules"""
    
    def __init__(self, setups_directory: str = 'setups'):
        """
        Initialize the setup loader
        
        Args:
            setups_directory: Path to directory containing setup modules
        """
        self.logger = logging.getLogger(__name__)
        self.setups_directory = setups_directory
        self.setups = {}  # setup_name -> setup_module
        self.setup_configs = {}  # setup_name -> configuration dict
        self.setup_metadata = {}  # setup_name -> metadata dict
        
    def load_all_setups(self) -> bool:
        """
        Load all setup modules from the setups directory
        
        Returns:
            bool: True if at least one setup loaded successfully
        """
        try:
            # Check if setups directory exists
            if not os.path.exists(self.setups_directory):
                self.logger.error(f"Setups directory not found: {self.setups_directory}")
                return False
            
            # Get list of setup directories
            setup_dirs = self._discover_setup_directories()
            
            if not setup_dirs:
                self.logger.warning(f"No setup directories found in {self.setups_directory}")
                return False
            
            self.logger.info(f"Found {len(setup_dirs)} setup directories")
            
            # Load each setup
            successful_loads = 0
            for setup_dir in setup_dirs:
                if self._load_single_setup(setup_dir):
                    successful_loads += 1
            
            self.logger.info(f"Successfully loaded {successful_loads}/{len(setup_dirs)} setups")
            return successful_loads > 0
            
        except Exception as e:
            self.logger.error(f"Error loading setups: {e}")
            return False
    
    def _discover_setup_directories(self) -> List[str]:
        """
        Discover all setup directories
        
        Returns:
            List[str]: List of setup directory paths
        """
        setup_dirs = []
        
        for item in os.listdir(self.setups_directory):
            item_path = os.path.join(self.setups_directory, item)
            
            # Check if it's a directory and looks like a setup
            if os.path.isdir(item_path):
                # Check for required files
                if self._is_valid_setup_directory(item_path):
                    setup_dirs.append(item_path)
                    self.logger.debug(f"Discovered setup directory: {item}")
                else:
                    self.logger.warning(f"Invalid setup directory structure: {item}")
        
        return sorted(setup_dirs)
    
    def _is_valid_setup_directory(self, directory_path: str) -> bool:
        """
        Check if directory has valid setup structure
        
        Required files:
        - pattern_detector.py
        - setup_config.yaml
        
        Optional files:
        - strategy.py
        - __init__.py
        
        Args:
            directory_path: Path to setup directory
            
        Returns:
            bool: True if directory has valid structure
        """
        required_files = ['pattern_detector.py', 'setup_config.yaml']
        
        for required_file in required_files:
            file_path = os.path.join(directory_path, required_file)
            if not os.path.exists(file_path):
                self.logger.debug(f"Missing required file: {required_file} in {os.path.basename(directory_path)}")
                return False
        
        return True
    
    def _load_single_setup(self, setup_dir: str) -> bool:
        """
        Load a single setup module
        
        Args:
            setup_dir: Path to setup directory
            
        Returns:
            bool: True if setup loaded successfully
        """
        setup_name = os.path.basename(setup_dir)
        
        try:
            self.logger.info(f"Loading setup: {setup_name}")
            
            # 1. Load configuration
            config_loaded = self._load_setup_config(setup_dir, setup_name)
            if not config_loaded:
                self.logger.error(f"Failed to load config for {setup_name}")
                return False
            
            # 2. Import pattern detector module
            pattern_module = self._import_pattern_detector(setup_dir, setup_name)
            if pattern_module is None:
                self.logger.error(f"Failed to import pattern detector for {setup_name}")
                return False
            
            # 3. Import strategy module (optional)
            strategy_module = self._import_strategy_module(setup_dir, setup_name)
            
            # 4. Create setup module wrapper
            setup_module = self._create_setup_module_wrapper(
                setup_name, pattern_module, strategy_module
            )
            
            # 5. Validate setup module
            if not self._validate_setup_module(setup_module, setup_name):
                return False
            
            # 6. Store setup module
            self.setups[setup_name] = setup_module
            self.logger.info(f"Successfully loaded setup: {setup_name}")
            
            # 7. Extract and store metadata
            metadata = self._extract_setup_metadata(setup_module, setup_name)
            self.setup_metadata[setup_name] = metadata
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading setup {setup_name}: {e}")
            return False
    
    def _load_setup_config(self, setup_dir: str, setup_name: str) -> bool:
        """
        Load setup configuration from YAML file
        
        Args:
            setup_dir: Path to setup directory
            setup_name: Name of the setup
            
        Returns:
            bool: True if configuration loaded successfully
        """
        config_path = os.path.join(setup_dir, 'setup_config.yaml')
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate required configuration sections
            if not isinstance(config, dict):
                self.logger.error(f"Invalid config format for {setup_name}")
                return False
            
            # Check for required sections
            required_sections = ['setup_info', 'filters']
            for section in required_sections:
                if section not in config:
                    self.logger.error(f"Missing required section '{section}' in {setup_name} config")
                    return False
            
            # Store configuration
            self.setup_configs[setup_name] = config
            self.logger.debug(f"Loaded config for {setup_name}")
            
            return True
            
        except FileNotFoundError:
            self.logger.error(f"Config file not found: {config_path}")
            return False
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error in {setup_name} config: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error loading config for {setup_name}: {e}")
            return False
    
    def _import_pattern_detector(self, setup_dir: str, setup_name: str) -> Optional[Any]:
        """
        Import the pattern detector module
        
        Args:
            setup_dir: Path to setup directory
            setup_name: Name of the setup
            
        Returns:
            Optional[Any]: Imported module or None if failed
        """
        pattern_file = os.path.join(setup_dir, 'pattern_detector.py')
        
        try:
            # Add setup directory to Python path temporarily
            sys.path.insert(0, os.path.dirname(setup_dir))
            
            # Import the module
            module_name = f"{setup_name}.pattern_detector"
            
            # Use importlib to import the module
            spec = importlib.util.spec_from_file_location(
                f"{setup_name}_pattern",
                pattern_file
            )
            
            if spec is None or spec.loader is None:
                self.logger.error(f"Could not create spec for {setup_name} pattern detector")
                return None
            
            module = importlib.util.module_from_spec(spec)
            
            # Execute the module
            spec.loader.exec_module(module)
            
            # Verify required functions exist
            required_functions = ['analyze']
            for func in required_functions:
                if not hasattr(module, func):
                    self.logger.error(f"Missing required function '{func}' in {setup_name} pattern detector")
                    return None
            
            self.logger.debug(f"Imported pattern detector for {setup_name}")
            return module
            
        except ImportError as e:
            self.logger.error(f"Import error for {setup_name} pattern detector: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error importing {setup_name} pattern detector: {e}")
            return None
        finally:
            # Clean up path
            if os.path.dirname(setup_dir) in sys.path:
                sys.path.remove(os.path.dirname(setup_dir))
    
    def _import_strategy_module(self, setup_dir: str, setup_name: str) -> Optional[Any]:
        """
        Import the strategy module (optional)
        
        Args:
            setup_dir: Path to setup directory
            setup_name: Name of the setup
            
        Returns:
            Optional[Any]: Imported module or None if not present/failed
        """
        strategy_file = os.path.join(setup_dir, 'strategy.py')
        
        # Check if strategy file exists
        if not os.path.exists(strategy_file):
            self.logger.debug(f"No strategy module found for {setup_name}")
            return None
        
        try:
            # Add setup directory to Python path temporarily
            sys.path.insert(0, os.path.dirname(setup_dir))
            
            # Use importlib to import the module
            spec = importlib.util.spec_from_file_location(
                f"{setup_name}_strategy",
                strategy_file
            )
            
            if spec is None or spec.loader is None:
                self.logger.warning(f"Could not create spec for {setup_name} strategy")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            self.logger.debug(f"Imported strategy module for {setup_name}")
            return module
            
        except Exception as e:
            self.logger.warning(f"Error importing {setup_name} strategy: {e}")
            return None
        finally:
            # Clean up path
            if os.path.dirname(setup_dir) in sys.path:
                sys.path.remove(os.path.dirname(setup_dir))
    
    def _create_setup_module_wrapper(self, setup_name: str, 
                                    pattern_module: Any, 
                                    strategy_module: Optional[Any]) -> Dict[str, Any]:
        """
        Create a wrapper module that combines pattern detector and strategy
        
        Args:
            setup_name: Name of the setup
            pattern_module: Pattern detector module
            strategy_module: Strategy module (optional)
            
        Returns:
            Dict[str, Any]: Setup module wrapper dictionary
        """
        setup_module = {
            'name': setup_name,
            'pattern_detector': pattern_module,
            'strategy': strategy_module,
            'config': self.setup_configs[setup_name]
        }
        
        # Add analyze method
        setup_module['analyze'] = self._create_analyze_method(pattern_module, strategy_module)
        
        # Add helper methods
        setup_module['get_info'] = lambda: self._get_setup_info(setup_module)
        setup_module['get_required_columns'] = lambda: self._get_required_columns(pattern_module)
        
        return setup_module
    
    def _create_analyze_method(self, pattern_module: Any, strategy_module: Optional[Any]):
        """
        Create analyze method that combines pattern detection and strategy
        
        Returns:
            Callable: Analyze function
        """
        def analyze(data, symbol, global_config, setup_config, mode='live'):
            """
            Analyze market data for trading setups
            
            Args:
                data: DataFrame with market data
                symbol: Trading symbol
                global_config: Global configuration
                setup_config: Setup-specific configuration
                mode: Analysis mode ('live' or 'backtest')
                
            Returns:
                Dict: Analysis results
            """
            # Call pattern detector
            pattern_result = pattern_module.analyze(
                data=data,
                symbol=symbol,
                global_config=global_config,
                setup_config=setup_config,
                mode=mode
            )
            
            # If pattern detected and strategy module exists, apply strategy
            if pattern_result and strategy_module is not None:
                if hasattr(strategy_module, 'apply_strategy'):
                    strategy_result = strategy_module.apply_strategy(
                        pattern_result=pattern_result,
                        data=data,
                        symbol=symbol,
                        global_config=global_config,
                        setup_config=setup_config,
                        mode=mode
                    )
                    
                    # Merge results
                    if strategy_result:
                        pattern_result.update(strategy_result)
            
            return pattern_result
        
        return analyze
    
    def _validate_setup_module(self, setup_module: Dict[str, Any], setup_name: str) -> bool:
        """
        Validate that setup module has all required components
        
        Args:
            setup_module: Setup module dictionary
            setup_name: Name of the setup
            
        Returns:
            bool: True if module is valid
        """
        required_attributes = ['analyze', 'get_info', 'get_required_columns']
        
        for attr in required_attributes:
            if attr not in setup_module:
                self.logger.error(f"Missing required attribute '{attr}' in {setup_name}")
                return False
        
        # Test analyze function signature
        try:
            # Quick test to ensure analyze is callable
            if not callable(setup_module['analyze']):
                self.logger.error(f"Analyze is not callable in {setup_name}")
                return False
        except Exception as e:
            self.logger.error(f"Error validating analyze method in {setup_name}: {e}")
            return False
        
        return True
    
    def _extract_setup_metadata(self, setup_module: Dict[str, Any], setup_name: str) -> Dict[str, Any]:
        """
        Extract metadata from setup module
        
        Args:
            setup_module: Setup module dictionary
            setup_name: Name of the setup
            
        Returns:
            Dict[str, Any]: Setup metadata
        """
        config = self.setup_configs[setup_name]
        setup_info = config.get('setup_info', {})
        
        metadata = {
            'name': setup_name,
            'description': setup_info.get('description', 'No description'),
            'author': setup_info.get('author', 'Unknown'),
            'version': setup_info.get('version', '1.0.0'),
            'timeframe': setup_info.get('timeframe', '5min'),
            'patterns': setup_info.get('patterns', []),
            'created_date': setup_info.get('created_date', 'Unknown'),
            'last_modified': setup_info.get('last_modified', 'Unknown')
        }
        
        return metadata
    
    def _get_setup_info(self, setup_module: Dict[str, Any]) -> Dict[str, Any]:
        """Get setup information"""
        return {
            'name': setup_module['name'],
            'config': setup_module['config'],
            'has_strategy': setup_module['strategy'] is not None
        }
    
    def _get_required_columns(self, pattern_module: Any) -> List[str]:
        """Get required data columns for this setup"""
        # Default required columns
        default_columns = ['timestamp', 'open', 'high', 'low', 'close']
        
        # Check if pattern module has get_required_columns method
        if hasattr(pattern_module, 'get_required_columns'):
            try:
                custom_columns = pattern_module.get_required_columns()
                if isinstance(custom_columns, list):
                    return list(set(default_columns + custom_columns))
            except Exception:
                pass
        
        return default_columns
    
    def get_setup_config(self, setup_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific setup
        
        Args:
            setup_name: Name of the setup
            
        Returns:
            Optional[Dict[str, Any]]: Setup configuration or None
        """
        return self.setup_configs.get(setup_name)
    
    def get_setup_metadata(self, setup_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific setup
        
        Args:
            setup_name: Name of the setup
            
        Returns:
            Optional[Dict[str, Any]]: Setup metadata or None
        """
        return self.setup_metadata.get(setup_name)
    
    def list_setups(self) -> List[str]:
        """
        List all loaded setup names
        
        Returns:
            List[str]: List of setup names
        """
        return list(self.setups.keys())
    
    def get_setup(self, setup_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific setup module
        
        Args:
            setup_name: Name of the setup
            
        Returns:
            Optional[Dict[str, Any]]: Setup module or None
        """
        return self.setups.get(setup_name)
    
    def reload_setup(self, setup_name: str) -> bool:
        """
        Reload a specific setup module
        
        Args:
            setup_name: Name of the setup to reload
            
        Returns:
            bool: True if reloaded successfully
        """
        if setup_name not in self.setups:
            self.logger.error(f"Setup not found: {setup_name}")
            return False
        
        try:
            setup_dir = os.path.join(self.setups_directory, setup_name)
            
            # Remove old setup
            del self.setups[setup_name]
            if setup_name in self.setup_configs:
                del self.setup_configs[setup_name]
            if setup_name in self.setup_metadata:
                del self.setup_metadata[setup_name]
            
            # Reload setup
            return self._load_single_setup(setup_dir)
            
        except Exception as e:
            self.logger.error(f"Error reloading setup {setup_name}: {e}")
            return False
    
    def get_all_setup_metadata(self) -> Dict[str, Any]:
        """
        Get metadata for all loaded setups
        
        Returns:
            Dict[str, Any]: Dictionary of setup_name -> metadata
        """
        return self.setup_metadata.copy()