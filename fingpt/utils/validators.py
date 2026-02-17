"""
FinGPT Utils Validators
Validierungsfunktionen für Eingabedaten
"""

import re
from typing import Union

def validate_symbol(symbol: str) -> bool:
    """
    Validiert ein Handelssymbol
    
    Args:
        symbol: Zu validierendes Symbol (z.B. "EURUSD")
        
    Returns:
        bool: True wenn gültig, False sonst
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    # 6-stellige Währungspaare (z.B. EURUSD, GBPUSD)
    pattern = re.compile(r'^[A-Z]{6}$')
    return bool(pattern.match(symbol.upper()))

def validate_lot_size(lot_size: Union[float, int]) -> bool:
    """
    Validiert eine Lot-Größe
    
    Args:
        lot_size: Zu validierende Lot-Größe
        
    Returns:
        bool: True wenn gültig, False sonst
    """
    try:
        lot_float = float(lot_size)
        # Standard-Lot-Sizes: 0.01, 0.1, 1.0 mit maximal 2 Dezimalstellen
        return 0.01 <= lot_float <= 10.0 and round(lot_float, 2) == lot_float
    except (ValueError, TypeError):
        return False

def validate_timeframe(timeframe: str) -> bool:
    """
    Validiert einen Timeframe
    
    Args:
        timeframe: Zu validierender Timeframe (z.B. "M1", "H1")
        
    Returns:
        bool: True wenn gültig, False sonst
    """
    valid_timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
    return timeframe.upper() in valid_timeframes

def validate_percentage(percentage: Union[float, int]) -> bool:
    """
    Validiert einen Prozentwert
    
    Args:
        percentage: Zu validierender Prozentwert
        
    Returns:
        bool: True wenn gültig, False sonst
    """
    try:
        pct_float = float(percentage)
        return 0.0 <= pct_float <= 100.0
    except (ValueError, TypeError):
        return False