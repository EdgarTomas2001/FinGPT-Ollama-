"""
FinGPT Core Configuration
Zentrale Konfigurationsverwaltung für das FinGPT System
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import json
import os
from pathlib import Path

@dataclass
class TradingConfig:
    """Trading-spezifische Konfiguration"""
    default_lot_size: float = 0.5
    max_risk_percent: float = 2.0
    auto_trading_enabled: bool = False
    auto_trade_symbols: List[str] = None
    analysis_interval: int = 300
    partial_close_enabled: bool = True
    trailing_stop_enabled: bool = True
    
    def __post_init__(self):
        if self.auto_trade_symbols is None:
            self.auto_trade_symbols = ["EURUSD"]

@dataclass
class RiskConfig:
    """Risk Management Konfiguration"""
    max_daily_loss: float = -500.0
    max_weekly_loss: float = -1500.0
    max_drawdown: float = -2000.0
    max_risk_per_trade: float = 2.0
    max_positions_per_symbol: int = 1
    max_total_positions: int = 3
    trading_start_hour: int = 8
    trading_end_hour: int = 22

@dataclass
class IndicatorConfig:
    """Indikator-Konfiguration"""
    rsi_period: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    macd_fast_period: int = 12
    macd_slow_period: int = 26
    macd_signal_period: int = 9
    sr_lookback_period: int = 50
    sr_min_touches: int = 2

@dataclass
class ApiConfig:
    """API-Konfiguration"""
    ollama_url: str = "http://localhost:11434"
    mt5_enabled: bool = True
    http_timeout: int = 30
    max_retries: int = 3

@dataclass
class LoggingConfig:
    """Logging-Konfiguration"""
    level: str = "INFO"
    file_logging: bool = True
    console_logging: bool = True
    log_file_path: str = "./logs/fingpt.log"
    max_log_size_mb: int = 10
    backup_count: int = 5

@dataclass
class PerformanceConfig:
    """Performance-Konfiguration"""
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000
    async_processing: bool = True
    max_concurrent_requests: int = 5

@dataclass
class FinGPTConfig:
    """Hauptkonfiguration für FinGPT"""
    trading: TradingConfig
    risk: RiskConfig
    indicators: IndicatorConfig
    api: ApiConfig
    logging: LoggingConfig
    performance: PerformanceConfig
    
    @classmethod
    def default(cls) -> 'FinGPTConfig':
        """Erstellt Standardkonfiguration"""
        return cls(
            trading=TradingConfig(),
            risk=RiskConfig(),
            indicators=IndicatorConfig(),
            api=ApiConfig(),
            logging=LoggingConfig(),
            performance=PerformanceConfig()
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'FinGPTConfig':
        """Lädt Konfiguration aus Datei"""
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Konfiguration erstellen
            trading = TradingConfig(**config_data.get('trading', {}))
            risk = RiskConfig(**config_data.get('risk', {}))
            indicators = IndicatorConfig(**config_data.get('indicators', {}))
            api = ApiConfig(**config_data.get('api', {}))
            logging_conf = LoggingConfig(**config_data.get('logging', {}))
            performance = PerformanceConfig(**config_data.get('performance', {}))
            
            return cls(trading, risk, indicators, api, logging_conf, performance)
            
        except FileNotFoundError:
            # Standardkonfiguration zurückgeben
            return cls.default()
        except Exception as e:
            print(f"Fehler beim Laden der Konfiguration: {e}")
            return cls.default()
    
    def save_to_file(self, config_path: str):
        """Speichert Konfiguration in Datei"""
        try:
            # Konfigurationsdaten vorbereiten
            config_data = {
                'trading': asdict(self.trading),
                'risk': asdict(self.risk),
                'indicators': asdict(self.indicators),
                'api': asdict(self.api),
                'logging': asdict(self.logging),
                'performance': asdict(self.performance)
            }
            
            # Verzeichnis erstellen falls nicht vorhanden
            config_dir = Path(config_path).parent
            config_dir.mkdir(parents=True, exist_ok=True)
            
            # In Datei speichern
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

# Globale Konfigurationsinstanz
_global_config: Optional[FinGPTConfig] = None

def get_config() -> FinGPTConfig:
    """Gibt globale Konfigurationsinstanz zurück"""
    global _global_config
    if _global_config is None:
        config_path = "./config/fingpt_config.json"
        _global_config = FinGPTConfig.from_file(config_path)
    return _global_config

def set_config(config: FinGPTConfig):
    """Setzt globale Konfigurationsinstanz"""
    global _global_config
    _global_config = config

def reload_config(config_path: str = "./config/fingpt_config.json") -> FinGPTConfig:
    """Lädt Konfiguration neu"""
    global _global_config
    _global_config = FinGPTConfig.from_file(config_path)
    return _global_config