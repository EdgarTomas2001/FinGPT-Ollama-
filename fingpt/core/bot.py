"""
FinGPT Core Bot
Hauptklasse für das FinGPT Trading System
"""

from typing import Optional, Dict, Any, List
import time
from datetime import datetime

from .config import get_config, FinGPTConfig
from .logger import get_logger, info, error, warning
from ..trading.executor import TradingExecutor, execute_trade
from ..trading.validator import TradeValidator
from ..data.collector import DataCollector
from ..ai.analyzer import MarketAnalyzer
from ..exceptions.trading_errors import TradingException
from ..utils.validators import validate_symbol, validate_lot_size

class FinGPTBot:
    """
    Hauptklasse für das FinGPT Trading System
    
    Diese Klasse koordiniert alle Komponenten des Trading-Systems
    und bietet eine einheitliche Schnittstelle für Trading-Operationen.
    """
    
    def __init__(self, config: Optional[FinGPTConfig] = None):
        """
        Initialisiert den FinGPT Bot
        
        Args:
            config: Optionale Konfiguration. Wenn None, wird die Standardkonfiguration verwendet.
        """
        self.config = config or get_config()
        self.logger = get_logger()
        
        # Core Komponenten
        self.trading_executor = TradingExecutor()
        self.trade_validator = TradeValidator()
        self.data_collector = DataCollector()
        self.market_analyzer = MarketAnalyzer()
        
        # Status
        self.is_initialized = False
        self.is_trading_enabled = False
        self.auto_trading_active = False
        
        # Performance-Metriken
        self.trade_count = 0
        self.successful_trades = 0
        self.failed_trades = 0
        
        self._initialize_system()
    
    def _initialize_system(self):
        """Initialisiert das System"""
        try:
            info("Initialisiere FinGPT System...", "SYSTEM")
            
            # Trading aktivieren
            self.is_trading_enabled = True
            
            # System-Health prüfen
            if not self._health_check():
                warning("System-Health Check fehlgeschlagen", "SYSTEM")
            
            self.is_initialized = True
            info("FinGPT System initialisiert", "SYSTEM")
            
        except Exception as e:
            error(f"Initialisierungsfehler: {e}", "SYSTEM")
            raise
    
    def _health_check(self) -> bool:
        """Prüft den System-Health"""
        try:
            # MT5 Verbindung prüfen
            if not self.trading_executor.is_connected:
                warning("MT5 nicht verbunden", "HEALTH")
                return False
            
            # Account-Info prüfen
            account_info = self.trading_executor.get_account_info()
            if not account_info:
                warning("Keine Account-Info verfügbar", "HEALTH")
                return False
            
            info("System-Health Check erfolgreich", "HEALTH")
            return True
            
        except Exception as e:
            error(f"Health-Check Fehler: {e}", "HEALTH")
            return False
    
    def execute_trade(self, symbol: str, action: str, lot_size: float,
                     stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None) -> Dict[str, Any]:
        """
        Führt einen Trade aus
        
        Args:
            symbol: Handelssymbol (z.B. "EURUSD")
            action: Handelsaktion ("BUY" oder "SELL")
            lot_size: Lot-Größe
            stop_loss: Stop-Loss Preis (optional)
            take_profit: Take-Profit Preis (optional)
            
        Returns:
            Dict mit Trade-Ergebnis
        """
        try:
            # Eingaben validieren
            if not self.trade_validator.validate_trade_inputs(symbol, action, lot_size):
                return {
                    "success": False,
                    "message": "Ungültige Eingaben",
                    "order_id": None
                }
            
            # Trading prüfen
            if not self.is_trading_enabled:
                return {
                    "success": False,
                    "message": "Trading nicht aktiviert",
                    "order_id": None
                }
            
            # Trade ausführen
            result = self.trading_executor.execute_trade(
                symbol, action, lot_size, stop_loss, take_profit
            )
            
            # Statistiken aktualisieren
            self.trade_count += 1
            if result.success:
                self.successful_trades += 1
            else:
                self.failed_trades += 1
            
            return {
                "success": result.success,
                "message": result.message,
                "order_id": result.order_id,
                "price": result.price,
                "lot_size": result.lot_size,
                "symbol": result.symbol,
                "action": result.action
            }
            
        except TradingException as e:
            error(f"Trading-Fehler: {e.message}", "TRADING")
            self.failed_trades += 1
            return {
                "success": False,
                "message": e.message,
                "order_id": None
            }
        except Exception as e:
            error(f"Unerwarteter Fehler: {e}", "SYSTEM")
            self.failed_trades += 1
            return {
                "success": False,
                "message": f"Unerwarteter Fehler: {e}",
                "order_id": None
            }
    
    def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Holt Marktdaten für ein Symbol
        
        Args:
            symbol: Handelssymbol
            
        Returns:
            Dict mit Marktdaten oder None bei Fehler
        """
        try:
            if not validate_symbol(symbol):
                error(f"Ungültiges Symbol: {symbol}", "DATA")
                return None
            
            return self.data_collector.get_symbol_data(symbol)
            
        except Exception as e:
            error(f"Marktdaten-Fehler: {e}", "DATA")
            return None
    
    def analyze_market(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Analysiert den Markt für ein Symbol
        
        Args:
            symbol: Handelssymbol
            
        Returns:
            Dict mit Analyse-Ergebnissen oder None bei Fehler
        """
        try:
            if not validate_symbol(symbol):
                error(f"Ungültiges Symbol: {symbol}", "AI")
                return None
            
            # Marktdaten holen
            market_data = self.get_market_data(symbol)
            if not market_data:
                return None
            
            # Analyse durchführen
            analysis = self.market_analyzer.analyze_symbol(symbol, market_data)
            return analysis
            
        except Exception as e:
            error(f"Analyse-Fehler: {e}", "AI")
            return None
    
    def get_account_status(self) -> Optional[Dict[str, Any]]:
        """
        Holt den Account-Status
        
        Returns:
            Dict mit Account-Informationen oder None bei Fehler
        """
        try:
            account_info = self.trading_executor.get_account_info()
            if not account_info:
                return None
            
            # Zusätzliche Metriken berechnen
            total_trades = self.trade_count
            success_rate = (self.successful_trades / max(1, total_trades)) * 100 if total_trades > 0 else 0
            
            account_info.update({
                "total_trades": total_trades,
                "successful_trades": self.successful_trades,
                "failed_trades": self.failed_trades,
                "success_rate": round(success_rate, 2),
                "system_uptime": time.time() - getattr(self, '_start_time', time.time())
            })
            
            return account_info
            
        except Exception as e:
            error(f"Account-Status Fehler: {e}", "ACCOUNT")
            return None
    
    def enable_trading(self) -> bool:
        """
        Aktiviert Trading
        
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            self.is_trading_enabled = True
            info("Trading aktiviert", "TRADING")
            return True
            
        except Exception as e:
            error(f"Fehler beim Aktivieren von Trading: {e}", "TRADING")
            return False
    
    def disable_trading(self) -> bool:
        """
        Deaktiviert Trading
        
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            self.is_trading_enabled = False
            info("Trading deaktiviert", "TRADING")
            return True
            
        except Exception as e:
            error(f"Fehler beim Deaktivieren von Trading: {e}", "TRADING")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Holt den System-Status
        
        Returns:
            Dict mit System-Status-Informationen
        """
        return {
            "initialized": self.is_initialized,
            "trading_enabled": self.is_trading_enabled,
            "auto_trading_active": self.auto_trading_active,
            "mt5_connected": self.trading_executor.is_connected,
            "trade_count": self.trade_count,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": (self.successful_trades / max(1, self.trade_count)) * 100 if self.trade_count > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf"""
        try:
            self.trading_executor.disconnect()
            info("System bereinigt", "SYSTEM")
        except Exception as e:
            error(f"Fehler bei System-Bereinigung: {e}", "SYSTEM")

# Globale Bot-Instanz
_global_bot: Optional[FinGPTBot] = None

def get_bot() -> FinGPTBot:
    """Gibt globale Bot-Instanz zurück"""
    global _global_bot
    if _global_bot is None:
        _global_bot = FinGPTBot()
    return _global_bot

def initialize_bot(config: Optional[FinGPTConfig] = None) -> FinGPTBot:
    """Initialisiert und gibt Bot-Instanz zurück"""
    global _global_bot
    _global_bot = FinGPTBot(config)
    return _global_bot