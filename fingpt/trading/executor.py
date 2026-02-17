"""
FinGPT Trading Executor
Ausführung von Trading-Operationen mit erweitertem Error Handling
"""

import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

# MT5 Import (conditional)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("MetaTrader5 nicht verfügbar")

from ..core.logger import info, error, warning
from ..core.config import get_config
from ..exceptions.trading_errors import TradingExecutionError, InvalidSymbolError
from ..utils.validators import validate_lot_size, validate_symbol

class TradeAction(Enum):
    """Handelsaktionen"""
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class TradeResult:
    """Ergebnis einer Handelsausführung"""
    success: bool
    order_id: Optional[int] = None
    message: str = ""
    price: Optional[float] = None
    lot_size: Optional[float] = None
    symbol: Optional[str] = None
    action: Optional[str] = None

class TradingExecutor:
    """Führt Trading-Operationen aus"""
    
    def __init__(self):
        self.config = get_config().trading
        self.is_connected = False
        
        # Verbindung zu MT5 herstellen
        self._connect_mt5()
    
    def _connect_mt5(self) -> bool:
        """Stellt Verbindung zu MT5 her"""
        if not MT5_AVAILABLE:
            error("MT5 nicht verfügbar", "MT5")
            return False
        
        try:
            if not mt5.initialize():
                error("MT5 Initialisierung fehlgeschlagen", "MT5")
                return False
            
            account_info = mt5.account_info()
            if account_info is None:
                error("Keine Account-Info", "MT5")
                return False
            
            info(f"MT5 verbunden: {account_info.company}", "MT5")
            self.is_connected = True
            return True
            
        except Exception as e:
            error(f"MT5 Fehler: {e}", "MT5")
            return False
    
    def execute_trade(self, symbol: str, action: str, lot_size: float,
                     stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None) -> TradeResult:
        """
        Führt einen Trade aus
        
        Args:
            symbol: Handelssymbol (z.B. "EURUSD")
            action: Handelsaktion ("BUY" oder "SELL")
            lot_size: Lot-Größe
            stop_loss: Stop-Loss Preis (optional)
            take_profit: Take-Profit Preis (optional)
            
        Returns:
            TradeResult: Ergebnis der Ausführung
        """
        try:
            # Eingaben validieren
            if not self._validate_trade_inputs(symbol, action, lot_size):
                return TradeResult(
                    success=False,
                    message="Ungültige Eingaben"
                )
            
            # MT5-Verbindung prüfen
            if not self.is_connected and not self._connect_mt5():
                return TradeResult(
                    success=False,
                    message="Keine MT5-Verbindung"
                )
            
            # Symbol-Info holen
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                error(f"Symbol {symbol} nicht verfügbar", "TRADING")
                return TradeResult(
                    success=False,
                    message=f"Symbol {symbol} nicht verfügbar"
                )
            
            # Tick-Daten holen
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                error(f"Keine Preise für {symbol}", "TRADING")
                return TradeResult(
                    success=False,
                    message=f"Keine Preise für {symbol}"
                )
            
            # Lot-Size validieren
            if not validate_lot_size(lot_size):
                error(f"Ungültige Lot Size: {lot_size}", "TRADING")
                return TradeResult(
                    success=False,
                    message=f"Ungültige Lot Size: {lot_size}"
                )
            
            # Handelsparameter vorbereiten
            order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL
            price = tick.ask if action.upper() == "BUY" else tick.bid
            
            # Trade-Request erstellen
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(lot_size),
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "FinGPT Trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            # Stop-Loss und Take-Profit hinzufügen
            if stop_loss and stop_loss > 0:
                request["sl"] = round(stop_loss, symbol_info.digits)
            
            if take_profit and take_profit > 0:
                request["tp"] = round(take_profit, symbol_info.digits)
            
            # Trade ausführen
            info(f"{action} {lot_size} {symbol} @ {price:.5f}", "TRADING")
            result = mt5.order_send(request)
            
            # Ergebnis prüfen
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                success_msg = f"✅ {action} {lot_size} {symbol} @ {price:.5f} (#{result.order})"
                info(success_msg, "TRADING")
                
                return TradeResult(
                    success=True,
                    order_id=result.order,
                    message=success_msg,
                    price=price,
                    lot_size=lot_size,
                    symbol=symbol,
                    action=action
                )
            else:
                error_msg = f"❌ Trade failed: {result.retcode} - {result.comment}"
                error(error_msg, "TRADING")
                
                return TradeResult(
                    success=False,
                    message=error_msg
                )
                
        except Exception as e:
            error_msg = f"Trade-Fehler: {e}"
            error(error_msg, "TRADING")
            
            return TradeResult(
                success=False,
                message=error_msg
            )
    
    def _validate_trade_inputs(self, symbol: str, action: str, lot_size: float) -> bool:
        """Validiert Handelseingaben"""
        try:
            # Symbol validieren
            if not validate_symbol(symbol):
                return False
            
            # Aktion validieren
            if action.upper() not in ["BUY", "SELL"]:
                return False
            
            # Lot-Size validieren
            if not validate_lot_size(lot_size):
                return False
            
            return True
            
        except Exception as e:
            error(f"Validierungsfehler: {e}", "VALIDATION")
            return False
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Holt Account-Informationen"""
        try:
            if not self.is_connected:
                return None
            
            account_info = mt5.account_info()
            if account_info is None:
                return None
            
            return {
                "balance": account_info.balance,
                "equity": account_info.equity,
                "margin": account_info.margin,
                "free_margin": account_info.margin_free,
                "margin_level": account_info.margin_level,
                "currency": account_info.currency,
                "server": account_info.server
            }
            
        except Exception as e:
            error(f"Account-Info Fehler: {e}", "MT5")
            return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Holt Symbol-Informationen"""
        try:
            if not self.is_connected:
                return None
            
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return None
            
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            
            return {
                "symbol": symbol,
                "bid": tick.bid,
                "ask": tick.ask,
                "spread": tick.ask - tick.bid,
                "point": symbol_info.point,
                "digits": symbol_info.digits,
                "trade_mode": symbol_info.trade_mode,
                "volume_min": symbol_info.volume_min,
                "volume_max": symbol_info.volume_max,
                "volume_step": symbol_info.volume_step
            }
            
        except Exception as e:
            error(f"Symbol-Info Fehler: {e}", "MT5")
            return None
    
    def disconnect(self):
        """Trennt MT5-Verbindung"""
        if MT5_AVAILABLE and self.is_connected:
            try:
                mt5.shutdown()
                self.is_connected = False
                info("MT5 getrennt", "MT5")
            except Exception as e:
                error(f"MT5 Trennungsfehler: {e}", "MT5")

# Globale TradingExecutor-Instanz
_global_executor: Optional[TradingExecutor] = None

def get_trading_executor() -> TradingExecutor:
    """Gibt globale TradingExecutor-Instanz zurück"""
    global _global_executor
    if _global_executor is None:
        _global_executor = TradingExecutor()
    return _global_executor

def execute_trade(symbol: str, action: str, lot_size: float,
                stop_loss: Optional[float] = None,
                take_profit: Optional[float] = None) -> TradeResult:
    """Convenience-Funktion für Trade-Ausführung"""
    return get_trading_executor().execute_trade(symbol, action, lot_size, stop_loss, take_profit)