
# Legacy Compatibility Layer for FinGPT Enhanced
# This file provides backward compatibility for older versions

import warnings
from typing import Any, Optional

# Import enhanced version
from FinGPT import MT5FinGPT as EnhancedMT5FinGPT

class MT5FinGPT(EnhancedMT5FinGPT):
    """
    Backward compatible wrapper for FinGPT Enhanced
    Maintains the original API while providing enhanced features
    """
    
    def __init__(self):
        super().__init__()
        self._suppress_enhanced_warnings = False
    
    def legacy_mode(self, enabled: bool = True):
        """Enable or disable legacy mode"""
        self._suppress_enhanced_warnings = enabled
        if enabled:
            warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    def get_available_models(self):
        """Legacy method for model availability"""
        if not hasattr(self, '_legacy_models_warning'):
            warnings.warn(
                "get_available_models() is deprecated, use get_ollama_models() instead",
                DeprecationWarning,
                stacklevel=2
            )
            self._legacy_models_warning = True
        return self.get_ollama_models()
    
    def set_risk_parameters(self, max_risk: float, max_positions: int):
        """Legacy method for risk parameters"""
        if not hasattr(self, '_legacy_risk_warning'):
            warnings.warn(
                "set_risk_parameters() is deprecated, use RiskManager directly",
                DeprecationWarning,
                stacklevel=2
            )
            self._legacy_risk_warning = True
        
        if self.risk_manager:
            self.risk_manager.max_risk_per_trade = max_risk
            self.risk_manager.max_total_positions = max_positions

# Export legacy class
__all__ = ['MT5FinGPT']
