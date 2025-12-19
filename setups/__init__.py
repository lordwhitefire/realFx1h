"""
Setups Package - Trading setup modules for the scanner system
Contains all individual trading setups that can be loaded by the controller
"""

__version__ = "1.0.0"
__author__ = "Trading Setup Scanner"
__description__ = "Collection of trading setup modules for pattern detection"

# Export common setup components
__all__ = [
    # Setup structure components
    'BaseSetup',
    'PatternDetector',
    'TradingStrategy',
    
    # Utility functions
    'validate_setup_structure',
    'load_setup_module',
    
    # Setup categories
    'PATTERN_TYPES',
    'TIMEFRAMES',
    'SIGNAL_TYPES'
]

# Setup categories
PATTERN_TYPES = [
    'REVERSAL',
    'CONTINUATION',
    'BREAKOUT',
    'RANGE_BOUND'
]

TIMEFRAMES = [
    '1min',
    '5min',
    '15min',
    '30min',
    '1H',
    '4H',
    '1D',
    '1W'
]

SIGNAL_TYPES = [
    'CALL',      # For binary options/up direction
    'PUT',       # For binary options/down direction
    'BUY',       # For regular trading
    'SELL',      # For regular trading
    'NEUTRAL',   # No clear signal
    'EXIT'       # Exit existing position
]

class BaseSetup:
    """Base class for all trading setups"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.version = "1.0.0"
        self.author = "Unknown"
        self.created_date = ""
        self.last_modified = ""
        
        # Setup configuration
        self.timeframe = "5min"
        self.pattern_types = []
        self.required_indicators = []
        self.supported_symbols = []
        
    def analyze(self, data, symbol, config):
        """Analyze market data for trading signals"""
        raise NotImplementedError("Subclasses must implement analyze method")
    
    def get_info(self):
        """Get setup information"""
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'timeframe': self.timeframe,
            'pattern_types': self.pattern_types,
            'required_indicators': self.required_indicators,
            'supported_symbols': self.supported_symbols
        }

class PatternDetector:
    """Base class for pattern detection logic"""
    
    def detect(self, data, symbol, config):
        """Detect patterns in market data"""
        raise NotImplementedError("Subclasses must implement detect method")
    
    def get_confidence(self, pattern_data):
        """Calculate confidence level for detected pattern"""
        raise NotImplementedError("Subclasses must implement get_confidence method")

class TradingStrategy:
    """Base class for trading strategy rules"""
    
    def apply(self, pattern_signal, data, config):
        """Apply strategy rules to pattern signal"""
        raise NotImplementedError("Subclasses must implement apply method")
    
    def calculate_position_size(self, signal, account_balance, risk_percentage):
        """Calculate position size based on risk management"""
        raise NotImplementedError("Subclasses must implement calculate_position_size method")

def validate_setup_structure(setup_path: str) -> tuple:
    """
    Validate that a setup directory has the required structure
    
    Args:
        setup_path: Path to setup directory
        
    Returns:
        tuple: (is_valid, error_message)
    """
    import os
    
    required_files = ['pattern_detector.py', 'setup_config.yaml']
    optional_files = ['strategy.py', '__init__.py']
    
    if not os.path.exists(setup_path):
        return False, f"Setup directory not found: {setup_path}"
    
    if not os.path.isdir(setup_path):
        return False, f"Path is not a directory: {setup_path}"
    
    # Check required files
    for file_name in required_files:
        file_path = os.path.join(setup_path, file_name)
        if not os.path.exists(file_path):
            return False, f"Missing required file: {file_name}"
    
    return True, "Setup structure is valid"

def load_setup_module(setup_path: str):
    """
    Dynamically load a setup module from directory
    
    Args:
        setup_path: Path to setup directory
        
    Returns:
        dict: Setup module components or None if failed
    """
    import os
    import importlib.util
    
    # Validate structure first
    is_valid, error_msg = validate_setup_structure(setup_path)
    if not is_valid:
        print(f"Invalid setup structure: {error_msg}")
        return None
    
    setup_name = os.path.basename(setup_path)
    
    try:
        setup_module = {}
        
        # Load pattern detector
        pattern_file = os.path.join(setup_path, 'pattern_detector.py')
        spec = importlib.util.spec_from_file_location(f"{setup_name}_pattern", pattern_file)
        pattern_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pattern_module)
        setup_module['pattern_detector'] = pattern_module
        
        # Load strategy if exists
        strategy_file = os.path.join(setup_path, 'strategy.py')
        if os.path.exists(strategy_file):
            spec = importlib.util.spec_from_file_location(f"{setup_name}_strategy", strategy_file)
            strategy_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(strategy_module)
            setup_module['strategy'] = strategy_module
        
        # Load config
        import yaml
        config_file = os.path.join(setup_path, 'setup_config.yaml')
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        setup_module['config'] = config
        
        return setup_module
        
    except Exception as e:
        print(f"Error loading setup {setup_name}: {e}")
        return None

def list_available_setups(setups_directory: str = "setups") -> list:
    """
    List all available setups in the setups directory
    
    Args:
        setups_directory: Path to setups directory
        
    Returns:
        list: List of setup names
    """
    import os
    
    if not os.path.exists(setups_directory):
        return []
    
    setups = []
    for item in os.listdir(setups_directory):
        item_path = os.path.join(setups_directory, item)
        if os.path.isdir(item_path):
            is_valid, _ = validate_setup_structure(item_path)
            if is_valid:
                setups.append(item)
    
    return sorted(setups)

def get_setup_metadata(setup_path: str) -> dict:
    """
    Get metadata for a setup
    
    Args:
        setup_path: Path to setup directory
        
    Returns:
        dict: Setup metadata
    """
    import os
    import yaml
    
    setup_name = os.path.basename(setup_path)
    config_file = os.path.join(setup_path, 'setup_config.yaml')
    
    metadata = {
        'name': setup_name,
        'path': setup_path,
        'is_valid': False,
        'error': None
    }
    
    try:
        # Load config to get metadata
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        if config and 'setup_info' in config:
            metadata.update(config['setup_info'])
        
        metadata['is_valid'] = True
        metadata['has_strategy'] = os.path.exists(os.path.join(setup_path, 'strategy.py'))
        
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata

# Initialize package
print(f"Trading Setups Package v{__version__} loaded")
print(f"Description: {__description__}")