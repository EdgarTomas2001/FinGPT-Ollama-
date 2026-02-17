"""
FinGPT Exceptions
Spezialisierte Exception-Klassen für das FinGPT System
"""

class FinGPTException(Exception):
    """Basisklasse für alle FinGPT Exceptions"""
    def __init__(self, message: str, error_code: str = "FG_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

class TradingException(FinGPTException):
    """Basisklasse für Trading-Exceptions"""
    def __init__(self, message: str, symbol: str = ""):
        super().__init__(message, "TRADING_ERROR")
        self.symbol = symbol

class TradingExecutionError(TradingException):
    """Fehler bei der Trade-Ausführung"""
    def __init__(self, message: str, symbol: str = "", order_id: str = ""):
        super().__init__(message, symbol)
        self.order_id = order_id

class InvalidSymbolError(TradingException):
    """Ungültiges Handelssymbol"""
    def __init__(self, symbol: str):
        super().__init__(f"Ungültiges Symbol: {symbol}", symbol)

class RiskManagementError(FinGPTException):
    """Fehler im Risk Management"""
    def __init__(self, message: str):
        super().__init__(message, "RISK_ERROR")

class DataCollectionError(FinGPTException):
    """Fehler bei der Datenerfassung"""
    def __init__(self, message: str, symbol: str = ""):
        super().__init__(message, "DATA_ERROR")
        self.symbol = symbol

class ApiConnectionError(FinGPTException):
    """Fehler bei API-Verbindungen"""
    def __init__(self, message: str, endpoint: str = ""):
        super().__init__(message, "API_ERROR")
        self.endpoint = endpoint

class ConfigurationError(FinGPTException):
    """Fehler in der Konfiguration"""
    def __init__(self, message: str, config_key: str = ""):
        super().__init__(message, "CONFIG_ERROR")
        self.config_key = config_key

class ValidationError(FinGPTException):
    """Validierungsfehler"""
    def __init__(self, message: str, field: str = ""):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field