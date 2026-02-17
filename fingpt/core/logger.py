"""
FinGPT Core Logger
Zentrales Logging-System für das FinGPT System
"""

import logging
import logging.handlers
import sys
from typing import Optional
from pathlib import Path
from .config import get_config, LoggingConfig

class FinGPTLogger:
    """Zentrales Logging-System"""
    
    def __init__(self):
        self.logger = None
        self._setup_logger()
    
    def _setup_logger(self):
        """Richtet das Logging-System ein"""
        config = get_config().logging
        
        # Logger erstellen
        self.logger = logging.getLogger('FinGPT')
        self.logger.setLevel(getattr(logging, config.level.upper()))
        
        # Verhindere doppelte Handler
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Formatter erstellen
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console Handler
        if config.console_logging:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, config.level.upper()))
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # File Handler
        if config.file_logging:
            # Log-Verzeichnis erstellen
            log_path = Path(config.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Rotating File Handler
            file_handler = logging.handlers.RotatingFileHandler(
                config.log_file_path,
                maxBytes=config.max_log_size_mb * 1024 * 1024,
                backupCount=config.backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, config.level.upper()))
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str, category: str = "SYSTEM"):
        """Debug-Nachricht"""
        self.logger.debug(f"[{category}] {message}")
    
    def info(self, message: str, category: str = "SYSTEM"):
        """Info-Nachricht"""
        self.logger.info(f"[{category}] {message}")
    
    def warning(self, message: str, category: str = "SYSTEM"):
        """Warn-Nachricht"""
        self.logger.warning(f"[{category}] {message}")
    
    def error(self, message: str, category: str = "SYSTEM"):
        """Error-Nachricht"""
        self.logger.error(f"[{category}] {message}")
    
    def critical(self, message: str, category: str = "SYSTEM"):
        """Critical-Nachricht"""
        self.logger.critical(f"[{category}] {message}")

# Globale Logger-Instanz
_global_logger: Optional[FinGPTLogger] = None

def get_logger() -> FinGPTLogger:
    """Gibt globale Logger-Instanz zurück"""
    global _global_logger
    if _global_logger is None:
        _global_logger = FinGPTLogger()
    return _global_logger

def debug(message: str, category: str = "SYSTEM"):
    """Convenience-Funktion für Debug-Nachrichten"""
    get_logger().debug(message, category)

def info(message: str, category: str = "SYSTEM"):
    """Convenience-Funktion für Info-Nachrichten"""
    get_logger().info(message, category)

def warning(message: str, category: str = "SYSTEM"):
    """Convenience-Funktion für Warn-Nachrichten"""
    get_logger().warning(message, category)

def error(message: str, category: str = "SYSTEM"):
    """Convenience-Funktion für Error-Nachrichten"""
    get_logger().error(message, category)

def critical(message: str, category: str = "SYSTEM"):
    """Convenience-Funktion für Critical-Nachrichten"""
    get_logger().critical(message, category)