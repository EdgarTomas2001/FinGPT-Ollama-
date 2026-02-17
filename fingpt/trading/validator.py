"""
FinGPT Trading Validator
Validierung von Trading-Eingaben und -Parametern
"""

from typing import Union
import re

from ..core.logger import debug, info, warning, error
from ..utils.validators import validate_symbol, validate_lot_size

class TradeValidator:
    """Validiert Trading-Eingaben und -Parameter"""
    
    def __init__(self):
        """Initialisiert den TradeValidator"""
        self.validation_rules = {
            "symbol_pattern": re.compile(r'^[A-Z]{6}$'),
            "action_values": ["BUY", "SELL"],
            "lot_size_min": 0.01,
            "lot_size_max": 10.0
        }
    
    def validate_trade_inputs(self, symbol: str, action: str, lot_size: Union[float, int]) -> bool:
        """
        Validiert alle Trading-Eingaben
        
        Args:
            symbol: Handelssymbol
            action: Handelsaktion
            lot_size: Lot-Größe
            
        Returns:
            bool: True wenn alle Eingaben gültig sind, False sonst
        """
        try:
            # Symbol validieren
            if not self.validate_symbol(symbol):
                debug(f"Symbol-Validierung fehlgeschlagen: {symbol}", "VALIDATION")
                return False
            
            # Aktion validieren
            if not self.validate_action(action):
                debug(f"Aktion-Validierung fehlgeschlagen: {action}", "VALIDATION")
                return False
            
            # Lot-Size validieren
            if not self.validate_lot_size(lot_size):
                debug(f"Lot-Size-Validierung fehlgeschlagen: {lot_size}", "VALIDATION")
                return False
            
            debug(f"Alle Validierungen erfolgreich für {symbol} {action} {lot_size}", "VALIDATION")
            return True
            
        except Exception as e:
            error(f"Validierungsfehler: {e}", "VALIDATION")
            return False
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Validiert ein Handelssymbol
        
        Args:
            symbol: Zu validierendes Symbol
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        return validate_symbol(symbol)
    
    def validate_action(self, action: str) -> bool:
        """
        Validiert eine Handelsaktion
        
        Args:
            action: Zu validierende Aktion
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        if not action or not isinstance(action, str):
            return False
        
        return action.upper() in self.validation_rules["action_values"]
    
    def validate_lot_size(self, lot_size: Union[float, int]) -> bool:
        """
        Validiert eine Lot-Größe
        
        Args:
            lot_size: Zu validierende Lot-Größe
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        return validate_lot_size(lot_size)
    
    def validate_price(self, price: Union[float, int], symbol: str = "") -> bool:
        """
        Validiert einen Preis
        
        Args:
            price: Zu validierender Preis
            symbol: Symbol für Kontext (optional)
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        try:
            price_float = float(price)
            # Preis sollte positiv und realistisch sein
            return 0 < price_float < 1000000  # Max 1 Million (für exotische Assets)
        except (ValueError, TypeError):
            return False
    
    def validate_stop_loss(self, stop_loss: Union[float, int], 
                          current_price: Union[float, int], 
                          action: str) -> bool:
        """
        Validiert einen Stop-Loss
        
        Args:
            stop_loss: Stop-Loss Preis
            current_price: Aktueller Preis
            action: Handelsaktion
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        try:
            sl_float = float(stop_loss)
            price_float = float(current_price)
            
            # Stop-Loss muss plausibel sein
            if not self.validate_price(sl_float):
                return False
            
            # Stop-Loss muss in richtiger Richtung sein
            if action.upper() == "BUY" and sl_float >= price_float:
                warning("Stop-Loss für BUY sollte unter aktuellem Preis liegen", "VALIDATION")
                return False
            elif action.upper() == "SELL" and sl_float <= price_float:
                warning("Stop-Loss für SELL sollte über aktuellem Preis liegen", "VALIDATION")
                return False
            
            return True
            
        except (ValueError, TypeError):
            return False

# Globale Validator-Instanz
_global_validator: TradeValidator = None

def get_trade_validator() -> TradeValidator:
    """Gibt globale TradeValidator-Instanz zurück"""
    global _global_validator
    if _global_validator is None:
        _global_validator = TradeValidator()
    return _global_validator