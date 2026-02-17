"""
FinGPT Trading Errors
Spezialisierte Trading-Exceptions
"""

from . import TradingException, TradingExecutionError, InvalidSymbolError

# Alias für bessere Import-Kompatibilität
FinGPTTradingException = TradingException
FinGPTTradingExecutionError = TradingExecutionError
FinGPTInvalidSymbolError = InvalidSymbolError