#!/usr/bin/env python3
"""
FinGPT mit Ollama + MetaTrader 5 Integration
Vollautomatisches Trading mit KI und Partial Close + RSI
"""

import logging
import requests
import json
import sys
import time
from datetime import datetime, timedelta
import subprocess
import warnings
import re
import numpy as np
import threading
import os
import signal
import queue
warnings.filterwarnings("ignore")

# MetaTrader 5 Import
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
    print("MetaTrader5 verfügbar")
except ImportError:
    MT5_AVAILABLE = False
    print("MetaTrader5 nicht installiert")

# Risk Manager Import
from risk_manager import RiskManager

# In Ihrer FinGPT.py Datei hinzufügen:
from advanced_indicators import AdvancedIndicators, IndicatorIntegration

class MT5FinGPT:
    def __init__(self):
        """Initialisiert das FinGPT System mit korrekter Reihenfolge"""
    
        # GRUNDLEGENDE EINSTELLUNGEN ZUERST
        self.ollama_url = "http://localhost:11434"
        self.available_models = []
        self.selected_model = None
        self.mt5_connected = False
        self.trading_enabled = False
        self.default_lot_size = 0.5
        self.max_risk_percent = 2.0
        self.auto_trading = False
        self.auto_trade_symbols = ["EURUSD"]
        self.analysis_interval = 300
    
        # LOGGING SETUP - MUSS ZUERST KOMMEN!
        self.setup_logging()
        self.log("INFO", "FinGPT System wird initialisiert...")
    
        # RISK MANAGER - NACH LOGGING!
        try:
            from risk_manager import RiskManager
            self.risk_manager = RiskManager(logger=self.logger)
            self.log("INFO", "Risk Manager erfolgreich initialisiert", "RISK")
        except ImportError as e:
            self.log("ERROR", f"Risk Manager Import Fehler: {e}", "RISK")
            self.risk_manager = None
        except Exception as e:
            self.log("ERROR", f"Risk Manager Initialisierung Fehler: {e}", "RISK")
            self.risk_manager = None
    
        # ERWEITERTE INDIKATOREN - NACH LOGGING!
        try:
            from advanced_indicators import AdvancedIndicators, IndicatorIntegration
            self.advanced_indicators = AdvancedIndicators(logger=self.logger)
            self.integration = IndicatorIntegration(self)
            self.log("INFO", "✅ Erweiterte Indikatoren erfolgreich initialisiert", "INDICATORS")
            self.has_extended_indicators = True
        except ImportError as e:
            self.log("WARNING", f"Erweiterte Indikatoren nicht verfügbar: {e}", "INDICATORS")
            self.advanced_indicators = None
            self.integration = None
            self.has_extended_indicators = False
        except Exception as e:
            self.log("ERROR", f"Erweiterte Indikatoren Fehler: {e}", "INDICATORS")
            self.advanced_indicators = None
            self.integration = None
            self.has_extended_indicators = False
    
        # TIMEFRAME NAMES
        self.timeframe_names = {
            mt5.TIMEFRAME_M1: "M1",
            mt5.TIMEFRAME_M5: "M5", 
            mt5.TIMEFRAME_M15: "M15",
            mt5.TIMEFRAME_M30: "M30",
            mt5.TIMEFRAME_H1: "H1",
            mt5.TIMEFRAME_H4: "H4",
            mt5.TIMEFRAME_D1: "D1"
        }
    
        # TRADING COMPANION INTEGRATION
        self.companion_process = None
        self.companion_enabled = False
        self.auto_start_companion = False
    
        # RSI SETTINGS
        self.rsi_period = 14
        self.rsi_timeframe = mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None
        self.rsi_overbought = 70
        self.rsi_oversold = 30
    
        # SUPPORT/RESISTANCE SETTINGS
        self.sr_lookback_period = 50
        self.sr_min_touches = 2
        self.sr_tolerance = 0.0002
        self.sr_strength_threshold = 3
    
        # MACD SETTINGS
        self.macd_fast_period = 12
        self.macd_slow_period = 26
        self.macd_signal_period = 9
        self.macd_timeframe = mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None
    
        # MULTI-TIMEFRAME SETTINGS
        self.mtf_enabled = True
        self.trend_timeframe = mt5.TIMEFRAME_H1 if MT5_AVAILABLE else None
        self.entry_timeframe = mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None
        self.trend_ema_period = 50
        self.trend_strength_threshold = 0.0010  # 10 Pips Mindest-Trendbewegung
        self.require_trend_confirmation = True
    
        # PARTIAL CLOSE SETTINGS
        self.partial_close_enabled = True
        self.first_target_percent = 50
        self.second_target_percent = 25
        self.profit_target_1 = 1.5
        self.profit_target_2 = 3.0
    
        # UI VERBESSERUNGEN
        self.companion_output_queue = queue.Queue()
        self.ui_lock = threading.Lock()
        self.companion_silent_mode = False
        self.last_menu_display = 0
    
        # TRAILING STOP SETTINGS
        self.trailing_stop_enabled = True
        self.trailing_stop_distance_pips = 20
        self.trailing_stop_step_pips = 5
        self.trailing_stop_start_profit_pips = 15
    
        # CURRENCY PAIRS CONFIGURATION
        self.currency_pairs = {
            "major": {
                "name": "Majors (Hauptwährungspaare)",
                "pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"],
                "description": "Die 7 wichtigsten Forex-Paare mit höchster Liquidität"
            },
            "eur_cross": {
                "name": "EUR Cross-Paare", 
                "pairs": ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD"],
                "description": "Euro-basierte Währungspaare"
            },
            "gbp_cross": {
                "name": "GBP Cross-Paare",
                "pairs": ["GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD"],
                "description": "Pfund-basierte Währungspaare"
            },
            "jpy_cross": {
                "name": "JPY Cross-Paare",
                "pairs": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"],
                "description": "Yen-basierte Währungspaare"
            },
            "commodity": {
                "name": "Rohstoff-Währungen",
                "pairs": ["AUDUSD", "NZDUSD", "USDCAD", "AUDCAD", "AUDNZD", "CADJPY", "NZDCAD"],
                "description": "Währungen von rohstoffexportierenden Ländern"
            },
            "safe_haven": {
                "name": "Safe Haven",
                "pairs": ["USDCHF", "USDJPY", "CHFJPY", "XAUUSD", "XAGUSD"],
                "description": "Sichere Häfen in unsicheren Zeiten"
            },
            "volatile": {
                "name": "Volatile Paare",
                "pairs": ["GBPJPY", "GBPAUD", "EURJPY", "AUDJPY", "GBPNZD", "EURNZD"],
                "description": "Hochvolatile Paare für erfahrene Trader"
            },
            "conservative": {
                "name": "Konservative Auswahl",
                "pairs": ["EURUSD", "GBPUSD", "USDCHF"],
                "description": "Stabile, gut vorhersagbare Paare"
            }
        }

        # BENUTZERDEFINIERTE LISTEN
        self.custom_pairs = {
            "user_favorites": {
                "name": "Meine Favoriten",
                "pairs": [],
                "description": "Ihre persönlichen Lieblings-Paare"
            },
            "high_performance": {
                "name": "High Performance",
                "pairs": [],
                "description": "Paare mit bester Performance in letzter Zeit"
            }
        }

        # RL INTEGRATION - NACH LOGGING!
        try:
            from rl_trading_agent import RLTradingManager
            self.rl_manager = RLTradingManager(self)
            self.rl_enabled = True
            self.log("INFO", "✅ RL Manager erfolgreich initialisiert", "RL")
        except ImportError as e:
            self.log("WARNING", f"RL Manager nicht verfügbar: {e}", "RL")
            self.rl_manager = None
            self.rl_enabled = False
        except Exception as e:
            self.log("ERROR", f"RL Manager Fehler: {e}", "RL")
            self.rl_manager = None
            self.rl_enabled = False

        # RL SETTINGS
        self.rl_training_mode = False
        self.rl_recommendation_weight = 0.3  # Gewichtung der RL-Empfehlung (30%)

        # ABSCHLUSS UND STATUS
        self.log("INFO", "FinGPT System mit Multi-Timeframe initialisiert")
    
        # STATUS CHECKS
        if self.risk_manager:
            self.log("INFO", "✅ Risk Manager ist verfügbar", "STATUS")
        else:
            self.log("WARNING", "❌ Risk Manager ist NICHT verfügbar", "STATUS")
    
        if self.has_extended_indicators:
            self.log("INFO", "✅ Erweiterte Indikatoren verfügbar", "STATUS")
        else:
            self.log("INFO", "📊 Basis-Indikatoren verfügbar (RSI, MACD, S/R)", "STATUS")
    
        if self.rl_enabled:
            self.log("INFO", "✅ RL Trading Agent verfügbar", "STATUS")
        else:
            self.log("INFO", "📈 Standard Trading Logik aktiv", "STATUS")
       
    def setup_logging(self):
        """Richtet das Logging-System ein"""
        try:
            # Erstelle logs Ordner falls nicht vorhanden
            if not os.path.exists("logs"):
                os.makedirs("logs")
            
            # Log-Datei mit Datum
            log_filename = f"logs/fingpt_{datetime.now().strftime('%Y%m%d')}.log"
            
            # Logging Konfiguration
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s | %(levelname)s | %(message)s',
                handlers=[
                    logging.FileHandler(log_filename, encoding='utf-8'),
                    logging.StreamHandler()  # Auch in Konsole ausgeben
                ]
            )
            
            self.logger = logging.getLogger('FinGPT')
            
        except Exception as e:
            print(f"Logging Setup Fehler: {e}")
            self.logger = None
    
    def log(self, level, message, category="SYSTEM"):
        """
        Universelle Logging-Funktion
        
        Args:
            level: INFO, WARNING, ERROR, DEBUG, TRADE
            message: Log-Nachricht
            category: Kategorie (SYSTEM, TRADE, MT5, AI, etc.)
        """
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            formatted_message = f"[{category}] {message}"
            
            # Konsolen-Output mit Icons
            icons = {
                "INFO": "ℹ️",
                "WARNING": "⚠️", 
                "ERROR": "❌",
                "DEBUG": "🔍",
                "TRADE": "💰",
                "MT5": "📊",
                "AI": "🤖",
                "COMPANION": "🔧"
            }
            
            icon = icons.get(level, "📝")
            print(f"{timestamp} {icon} {formatted_message}")
            
            # In Datei loggen
            if self.logger:
                if level == "ERROR":
                    self.logger.error(formatted_message)
                elif level == "WARNING":
                    self.logger.warning(formatted_message)
                elif level == "DEBUG":
                    self.logger.debug(formatted_message)
                else:
                    self.logger.info(formatted_message)
                    
        except Exception as e:
            print(f"Logging Fehler: {e}")
    
    def log_trade(self, symbol, action, result, reasoning=""):
        """Spezielle Logging-Funktion für Trades"""
        trade_info = f"{action} {symbol} - {result}"
        if reasoning:
            trade_info += f" | Grund: {reasoning}"
        self.log("TRADE", trade_info, "TRADE")
    
    def log_error(self, function_name, error, details=""):
        """Spezielle Logging-Funktion für Fehler"""
        error_info = f"Fehler in {function_name}: {error}"
        if details:
            error_info += f" | Details: {details}"
        self.log("ERROR", error_info, "ERROR")
    
    def log_ai_analysis(self, symbol, recommendation, confidence=""):
        """Spezielle Logging-Funktion für AI-Analysen"""
        ai_info = f"AI-Analyse {symbol}: {recommendation}"
        if confidence:
            ai_info += f" | Konfidenz: {confidence}"
        self.log("AI", ai_info, "AI")
    
    def log_debug_menu(self, choice, function_called):
        """Debug-Logging für Menü-Aufrufe"""
        self.log("DEBUG", f"Menü Option '{choice}' -> {function_called}", "MENU")

    def print_header(self, title, width=65):
        """Verbesserte Header-Darstellung mit besserer Formatierung"""
        border = "═" * width
        title_line = f"║ {title.upper()} ║"
        title_centered = title_line.center(width + 2, " ")
        
        print(f"\n╔{border}╗")
        print(f"║{title_centered}║")
        print(f"╚{border}╝")
    
    def print_status_bar_extended(self):
        """Erweiterte Status-Leiste mit allen Features"""
        with self.ui_lock:
            # Risk Manager Status
            risk_status = "❌"
            if hasattr(self, 'risk_manager') and self.risk_manager:
                try:
                    summary = self.risk_manager.get_risk_summary()
                    if summary is not None:
                        risk_status = "✅"
                        daily_pnl = summary.get('daily_pnl', 0)
                        if hasattr(self.risk_manager, 'max_daily_loss'):
                            if daily_pnl <= self.risk_manager.max_daily_loss * 0.8:
                                risk_status = "🟡"
                            elif daily_pnl <= self.risk_manager.max_daily_loss:
                                risk_status = "🔴"
                except:
                    risk_status = "⚠️"
        
            # Erweiterte Indikatoren Status
            indicators_status = "✅" if getattr(self, 'has_extended_indicators', False) else "❌"
            indicators_count = "7+" if getattr(self, 'has_extended_indicators', False) else "3"
        
            # RL Status
            rl_status = "✅" if getattr(self, 'rl_enabled', False) else "❌"
        
            # Integration Status
            integration_status = "✅" if getattr(self, 'integration', None) else "❌"
    
            status_items = [
                f"📱 MT5: {'✅' if self.mt5_connected else '❌'}",
                f"🤖 KI: {'✅' if self.selected_model else '❌'}",
                f"💰 Trading: {'✅' if self.trading_enabled else '❌'}",
                f"🔄 Auto: {'✅' if self.auto_trading else '❌'}",
                f"🛡️ Risk: {risk_status}",
                f"📊 Indicators: {indicators_status}({indicators_count})",
                f"🤖 RL: {rl_status}",
                f"🔧 Companion: {'✅' if self.companion_enabled else '❌'}"
            ]
    
            print("\n┌" + "─" * 85 + "┐")
            print(f"│ {' | '.join(status_items):<83} │")
            print("└" + "─" * 85 + "┘")
    
    def start_trading_companion(self):
        """Startet das Trading Companion Script mit verbesserter UI"""
        try:
            companion_script = "trading_companion.py"
            
            if self.companion_enabled or self.companion_process:
                print("🔧 Trading Companion läuft bereits")
                return True
                
            if not os.path.exists(companion_script):
                print(f"❌ Trading Companion Script nicht gefunden: {companion_script}")
                return False
                
            # Starte mit verbessertem Output-Handling
            try:
                self.companion_process = subprocess.Popen(
                    [sys.executable, companion_script],
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                time.sleep(0.5)
                if self.companion_process.poll() is not None:
                    print("❌ Trading Companion konnte nicht gestartet werden")
                    return False
                    
                print("✅ Trading Companion erfolgreich gestartet")
                self.companion_enabled = True
                
                # Verbesserter Monitor Thread
                def monitor_companion():
                    startup_complete = False
                    while self.companion_process and self.companion_enabled:
                        try:
                            if self.companion_process.poll() is not None:
                                break
                                
                            output = self.companion_process.stdout.readline()
                            if output:
                                output = output.strip()
                                
                                # Filtere und formatiere Output
                                if not startup_complete:
                                    if "Trading Companion gestartet" in output:
                                        startup_complete = True
                                        with self.ui_lock:
                                            print("🔧 Companion: Bereit für erweiterte Analyse")
                                    elif "Datenverbindung OK" in output:
                                        continue  # Unterdrücke redundante Meldungen
                                else:
                                    # Nach Startup nur wichtige Meldungen zeigen
                                    if not self.companion_silent_mode:
                                        if any(keyword in output for keyword in [
                                            "ANALYSE", "EMPFEHLUNG", "ERROR", "Fehler"
                                        ]):
                                            with self.ui_lock:
                                                print(f"🔧 Companion: {output}")
                                
                        except Exception as e:
                            break
                            
                    with self.ui_lock:
                        print("🔧 Trading Companion Monitor beendet")
                    self.companion_enabled = False
                    self.companion_process = None
                
                companion_thread = threading.Thread(
                    target=monitor_companion,
                    daemon=True,
                    name="CompanionMonitor"
                )
                companion_thread.start()
                
                return True
                
            except Exception as e:
                print(f"❌ Fehler beim Starten des Trading Companions: {e}")
                self.companion_process = None
                self.companion_enabled = False
                return False
                
        except Exception as e:
            print(f"❌ Trading Companion Setup Fehler: {e}")
            return False
    
    def interactive_menu(self):
        """Neu strukturiertes interaktives Menü mit klareren Gruppierungen"""
    
        # Companion automatisch starten (leise)
        if self.auto_start_companion and not self.companion_enabled:
            self.companion_silent_mode = True
            print("🔧 Starte Trading Companion...")
            self.start_trading_companion()
            self.companion_silent_mode = False
    
        while True:
            # COMPANION KOMPLETT PAUSIEREN FÜR SAUBERE EINGABE
            companion_was_active = self.companion_enabled
            if companion_was_active:
                import time
                time.sleep(0.1)  # Kurz warten bis laufende Ausgaben fertig sind
    
            # Dynamischer Header basierend auf verfügbaren Features
            header_title = "FinGPT TRADING SYSTEM"
            if getattr(self, 'has_extended_indicators', False):
                header_title += " (ERWEITERT)"
            if getattr(self, 'rl_enabled', False):
                header_title += " + RL"
        
            self.print_header(header_title)
    
            # Status-Leiste
            self.print_status_bar()
    
            # MENÜ-GRUPPIERUNG MIT KLAREN KATEGORIEN
            print("\n📋 HAUPTMENÜ - ÜBERSICHTLICH GRUPPIERT")
            print("─" * 50)
    
            # DATEN & ANALYSE
            print("\n📂 DATEN & ANALYSE:")
            print("─" * 25)
            print(" 1. 📊 Live-Daten anzeigen")
            print(" 2. 🤖 KI-Analyse")
            print(" 3. 📈 Offene Positionen")
    
            # TRADING & AUSFÜHRUNG
            print("\n💱 TRADING & AUSFÜHRUNG:")
            print("─" * 25)
            print(" 4. 💰 Trade ausführen")
            print(" 5. 🔓 Trading aktivieren/deaktivieren")
            print(" 6. 🔄 Auto-Trading")
            print(" 7. ⚙️ Position Management")
            print(" 8. 🎯 Partial Close Einstellungen")
    
            # EINSTELLUNGEN & KONFIGURATION
            print("\n⚙️ EINSTELLUNGEN & KONFIGURATION:")
            print("─" * 35)
            print(" 9. 📉 RSI Einstellungen")
            print("10. 📊 Support/Resistance Einstellungen")
            print("11. 📊 MACD Einstellungen")
            print("12. 🎯 Trailing Stop Einstellungen")
            print("13. 📈 Multi-Timeframe Einstellungen")
            print("14. 🔗 MT5 Verbindung")
            print("15. 🛡️ Risk Management")
            print("16. 💱 Währungspaar Management")
            print("17. 🔧 Trading Companion")
            print("18. 🤖 Reinforcement Learning")
    
            # ERWEITERTE INDIKATOREN SEKTION (nur wenn verfügbar)
            if getattr(self, 'has_extended_indicators', False):
                print("\n🔬 ERWEITERTE INDIKATOREN & ANALYSE:")
                print("─" * 40)
                print("20. 🔍 Einzelne erweiterte Indikatoren")
                print("21. 📊 Vollständige technische Analyse")
                print("22. 🎯 Signal-Generator (Alle Indikatoren)")
                print("23. ⚙️ Erweiterte Indikator-Einstellungen")
                print("24. 🤖 KI-Analyse (mit allen Indikatoren)")
                print("25. 📈 Multi-Indikator Scanner")
                print("26. 📊 Indikator-Vergleich & Benchmark")
                print("27. 🧪 Indikator-Test & Parameter-Optimierung")
            
            # PROGRAMM ENDE
            print("\n🚪 PROGRAMM:")
            print("─" * 15)
            if getattr(self, 'has_extended_indicators', False):
                print("28. ❌ Beenden")
                max_option = 28
            else:
                print("19. ❌ Beenden")
                max_option = 19
        
            print("─" * 50)
        
            # Feature-Status anzeigen
            if getattr(self, 'has_extended_indicators', False):
                available_indicators = [
                    "Williams %R", "CCI", "Awesome Oscillator", 
                    "Ichimoku Cloud", "VWAP", "MFI", "ADX"
                ]
                print(f"📊 Verfügbare erweiterte Indikatoren: {len(available_indicators)}")
                print(f"🎯 Basis + Erweitert = {3 + len(available_indicators)} Indikatoren total")
                print("✨ Alle erweiterten Funktionen aktiviert")
            else:
                print("📊 Basis-Indikatoren: RSI, MACD, Support/Resistance")
                print("💡 Tipp: Installieren Sie advanced_indicators.py für mehr Features!")
                print("🚀 Upgrade auf erweiterte Version möglich")

            print("─" * 50)
    
            # EINGABE MIT THREAD-SCHUTZ
            choice = ""
            try:
                choice = input(f"🎯 Ihre Wahl (1-{max_option}): ").strip()
            except KeyboardInterrupt:
                choice = str(max_option)  # Beenden bei Ctrl+C
    
            # Menü-Handler aufrufen
            if not self.handle_menu_choice(choice):
                break
    
    def print_status_bar(self):
        """Verbesserte Status-Leiste mit besserer Lesbarkeit und Übersichtlichkeit"""
        try:
            with self.ui_lock:
                # Risk Manager Status prüfen
                risk_status = "❌"
                if hasattr(self, 'risk_manager') and self.risk_manager:
                    try:
                        summary = self.risk_manager.get_risk_summary()
                        if summary is not None:
                            risk_status = "✅"
                            daily_pnl = summary.get('daily_pnl', 0)
                            # Erweiterte Risk-Checks nur wenn Risk Manager Attribute verfügbar
                            if hasattr(self.risk_manager, 'max_daily_loss'):
                                if daily_pnl <= self.risk_manager.max_daily_loss * 0.8:
                                    risk_status = "🟡"  # Warnung
                                elif daily_pnl <= self.risk_manager.max_daily_loss:
                                    risk_status = "🔴"  # Kritisch
                    except Exception:
                        risk_status = "⚠️"  # Fehler

                # Basis Status-Items (immer verfügbar)
                status_items = [
                    f"📱 MT5: {'✅' if self.mt5_connected else '❌'}",
                    f"🤖 KI: {'✅' if self.selected_model else '❌'}",
                    f"💰 Trading: {'✅' if self.trading_enabled else '❌'}",
                    f"🔄 Auto: {'✅' if self.auto_trading else '❌'}",
                    f"🛡️ Risk: {risk_status}",
                ]

                # Erweiterte Features (nur wenn verfügbar)
                if getattr(self, 'has_extended_indicators', False):
                    indicators_count = "7+"
                    indicators_status = "✅"
                else:
                    indicators_count = "3"
                    indicators_status = "📊"  # Basis-Indikatoren verfügbar
        
                status_items.append(f"📊 Indicators: {indicators_status}({indicators_count})")

                # RL Status (nur wenn verfügbar)
                if hasattr(self, 'rl_enabled'):
                    rl_status = "✅" if self.rl_enabled else "❌"
                    status_items.append(f"🤖 RL: {rl_status}")

                # Companion Status
                status_items.append(f"🔧 Companion: {'✅' if self.companion_enabled else '❌'}")

                # Dynamische Breite basierend auf Anzahl der Items
                total_width = max(85, len(' | '.join(status_items)) + 4)
        
                # Verbesserte visuelle Darstellung
                print(f"\n┌{'─' * (total_width - 2)}┐")
                print(f"│ {'STATUS ÜBERSICHT':^{total_width - 4}} │")
                print(f"├{'─' * (total_width - 2)}┤")
                
                # Status-Items in zwei Reihen anordnen für bessere Lesbarkeit
                mid_point = len(status_items) // 2
                row1_items = status_items[:mid_point]
                row2_items = status_items[mid_point:]
                
                # Erste Reihe
                row1_str = ' │ '.join(row1_items)
                print(f"│ {row1_str:<{total_width - 4}} │")
                
                # Zweite Reihe
                row2_str = ' │ '.join(row2_items)
                print(f"│ {row2_str:<{total_width - 4}} │")
                
                print(f"└{'─' * (total_width - 2)}┘")
            
        except Exception as e:
            # Fallback bei Fehlern mit verbessertem Design
            error_msg = f"Status-Bar Fehler: {str(e)[:50]}"
            print(f"\n┌{'─' * 65}┐")
            print(f"│ {error_msg:<63} │")
            print(f"└{'─' * 65}┘")

    def print_status_bar_basic(self):
        """Basis Status-Leiste (Fallback)"""
        with self.ui_lock:
            # Risk Manager Status
            risk_status = "❌"
            if hasattr(self, 'risk_manager') and self.risk_manager:
                try:
                    summary = self.risk_manager.get_risk_summary()
                    if summary is not None:
                        risk_status = "✅"
                except:
                    risk_status = "⚠️"

            status_items = [
                f"📱 MT5: {'✅' if self.mt5_connected else '❌'}",
                f"🤖 KI: {'✅' if self.selected_model else '❌'}",
                f"💰 Trading: {'✅' if self.trading_enabled else '❌'}",
                f"🔄 Auto: {'✅' if self.auto_trading else '❌'}",
                f"🛡️ Risk: {risk_status}",
                f"🔧 Companion: {'✅' if self.companion_enabled else '❌'}"
            ]

            print("\n┌" + "─" * 65 + "┐")
            print(f"│ {' | '.join(status_items):<63} │")
            print("└" + "─" * 65 + "┘")

    def print_status_bar_extended(self):
        """Erweiterte Status-Leiste mit allen Features"""
        with self.ui_lock:
            # Risk Manager Status
            risk_status = "❌"
            if hasattr(self, 'risk_manager') and self.risk_manager:
                try:
                    summary = self.risk_manager.get_risk_summary()
                    if summary is not None:
                        risk_status = "✅"
                        daily_pnl = summary.get('daily_pnl', 0)
                        if hasattr(self.risk_manager, 'max_daily_loss'):
                            if daily_pnl <= self.risk_manager.max_daily_loss * 0.8:
                                risk_status = "🟡"
                            elif daily_pnl <= self.risk_manager.max_daily_loss:
                                risk_status = "🔴"
                except:
                    risk_status = "⚠️"
        
            # Erweiterte Indikatoren Status
            indicators_status = "✅" if getattr(self, 'has_extended_indicators', False) else "❌"
            indicators_count = "7+" if getattr(self, 'has_extended_indicators', False) else "3"
        
            # RL Status
            rl_status = "✅" if getattr(self, 'rl_enabled', False) else "❌"

            status_items = [
                f"📱 MT5: {'✅' if self.mt5_connected else '❌'}",
                f"🤖 KI: {'✅' if self.selected_model else '❌'}",
                f"💰 Trading: {'✅' if self.trading_enabled else '❌'}",
                f"🔄 Auto: {'✅' if self.auto_trading else '❌'}",
                f"🛡️ Risk: {risk_status}",
                f"📊 Indicators: {indicators_status}({indicators_count})",
                f"🤖 RL: {rl_status}",
                f"🔧 Companion: {'✅' if self.companion_enabled else '❌'}"
            ]

            print("\n┌" + "─" * 85 + "┐")
            print(f"│ {' | '.join(status_items):<83} │")
            print("└" + "─" * 85 + "┘")

    def handle_menu_choice(self, choice):
        """Vollständige Menü-Behandlung mit Logging"""
        self.log_debug_menu(choice, "handle_menu_choice")
    
        if choice == "1":
            self.log("INFO", "Live-Daten Abfrage gestartet", "USER")
            self.print_header("LIVE MARKTDATEN")
            symbol = input("Symbol eingeben: ").upper()
            if symbol:
                self.log("INFO", f"Marktdaten abgerufen für {symbol}", "MT5")
                data = self.get_mt5_live_data(symbol)
                print(f"\n{data}")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "2":
            self.log("INFO", "KI-Analyse gestartet", "USER")
            self.print_header("KI-ANALYSE")
            symbol = input("Symbol für Analyse: ").upper()
            if symbol:
                print(f"\n🔄 Analysiere {symbol}...")
                print("─" * 50)
        
                try:
                    # Live-Daten holen
                    live_data = self.get_mt5_live_data(symbol)
            
                    if "Fehler" in live_data or "nicht" in live_data:
                        print(f"❌ Fehler beim Laden der Marktdaten für {symbol}")
                        print(live_data)
                    else:
                        # KI-Analyse durchführen
                        prompt = f"""Analysiere {symbol} für Trading-Entscheidung. 

        Berücksichtige besonders:
        - RSI-Wert und ob überkauft/überverkauft
        - MACD-Signale (Kreuzungen, Histogram, Nulllinie) 
        - Support/Resistance Levels und deren Stärke
        - Breakouts oder Bounces an S/R Levels
        - Trend-Richtung und Momentum

        Gib eine klare BUY/SELL/WARTEN Empfehlung mit:
        1. Hauptsignal (BUY/SELL/WARTEN)
        2. Entry-Preis Vorschlag
        3. Stop-Loss Vorschlag  
        4. Take-Profit Vorschlag
        5. Kurze technische Begründung

        Format die Antwort strukturiert und kompakt."""

                        print("🤖 KI analysiert Marktdaten...")
                
                        ai_response = self.chat_with_model(prompt, live_data)
                
                        # Log nur die Empfehlung, nicht den kompletten Text
                        recommendation = self.extract_recommendation_summary(ai_response)
                        self.log_ai_analysis(symbol, recommendation)
                
                        # Schöne Formatierung der KI-Antwort
                        self.display_formatted_analysis(symbol, ai_response, live_data)
                
                except Exception as e:
                    print(f"❌ Analysefehler: {e}")
                    self.log("ERROR", f"KI-Analyse Fehler für {symbol}: {e}", "AI")
    
            input("\n📝 Drücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "3":
            self.log("INFO", "Trade-Ausführung angefordert", "USER")
            if not self.trading_enabled:
                self.log("WARNING", "Trade abgelehnt - Trading nicht aktiviert", "TRADE")
                print("Trading nicht aktiviert!")
            else:
                symbol = input("Symbol: ").upper()
                action = input("Aktion (BUY/SELL): ").upper()
                if symbol and action in ["BUY", "SELL"]:
                    self.log("INFO", f"Trade wird ausgeführt: {action} {symbol}", "TRADE")
                    result = self.execute_trade(symbol, action)
                    self.log_trade(symbol, action, result)
                    print(result)
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "4":
            self.log("INFO", "Positionsübersicht angefordert", "USER")
            positions = self.get_open_positions()
            self.log("INFO", f"Positionsdaten abgerufen: {len(positions.split('\\n'))-1 if '\\n' in positions else 0} Positionen", "MT5")
            print(positions)
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "5":
            self.log("INFO", "Trading-Status wird geändert", "USER")
            if self.trading_enabled:
                self.trading_enabled = False
                self.log("WARNING", "Trading wurde deaktiviert", "TRADE")
                print("Trading deaktiviert")
            else:
                self.log("INFO", "Trading-Aktivierung angefordert", "TRADE")
                self.enable_trading()
                if self.trading_enabled:
                    self.log("INFO", "Trading erfolgreich aktiviert", "TRADE")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "6":
            self.log("INFO", "Auto-Trading Menü aufgerufen", "USER")
    
            if not self.trading_enabled:
                self.log("WARNING", "Auto-Trading abgelehnt - Trading nicht aktiviert", "TRADE")
                print("❌ Erst Trading aktivieren!")
            elif self.auto_trading:
                # Auto-Trading läuft bereits - Stopp-Option
                print("\n🔄 AUTO-TRADING LÄUFT")
                print("─" * 25)
                print(f"📊 Aktive Paare: {len(self.auto_trade_symbols)}")
                print(f"💱 Symbole: {', '.join(self.auto_trade_symbols[:3])}")
                if len(self.auto_trade_symbols) > 3:
                    print(f"           ... und {len(self.auto_trade_symbols) - 3} weitere")
                print(f"⏱️ Intervall: {self.analysis_interval}s")
        
                stop_choice = input("\nAuto-Trading stoppen? (ja/nein): ").lower()
                if stop_choice == "ja":
                    self.auto_trading = False
                    self.log("INFO", "Auto-Trading gestoppt", "TRADE")
                    print("✅ Auto-Trading gestoppt")
                else:
                    print("ℹ️ Auto-Trading läuft weiter...")
            else:
                # Auto-Trading Setup mit vereinfachter Logik
                self.log("INFO", "Auto-Trading Setup gestartet", "TRADE")
        
                print("\n🤖 VOLLAUTOMATISCHES TRADING SETUP")
                print("═" * 50)
                print("⚠️ WARNUNG: Automatisches Trading ist hochriskant!")
                print("💰 Nur mit Geld handeln, das Sie verlieren können!")
        
                # Sicherheitsabfragen
                confirm1 = input("\nAuto-Trading aktivieren? (GEFÄHRLICH/nein): ")
                if confirm1 != "GEFÄHRLICH":
                    print("❌ Auto-Trading abgebrochen")
                else:
                    confirm2 = input("Risiko verstanden? (ICH_VERSTEHE): ")
                    if confirm2 != "ICH_VERSTEHE":
                        print("❌ Auto-Trading abgebrochen")
                    else:
                        # Währungspaar-Auswahl
                        print(f"\n📋 WÄHRUNGSPAAR AUSWAHL")
                        print("─" * 30)
                        print("1. Aktuelle Paare verwenden")
                        print("2. Neue Paare auswählen")
                
                        pair_choice = input("Wählen (1-2): ").strip()
                
                        if pair_choice == "2":
                            # Vereinfachte Auswahl
                            print("\n📋 SCHNELLAUSWAHL:")
                            print("1. Majors (EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD)")
                            print("2. Konservativ (EURUSD, GBPUSD, USDCHF)")
                            print("3. EUR-Cross (EURUSD, EURGBP, EURJPY, EURCHF)")
                            print("4. Manuell eingeben")
                    
                            quick_choice = input("Wählen (1-4): ").strip()
                    
                            if quick_choice == "1":
                                self.auto_trade_symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
                                print("✅ Majors ausgewählt")
                            elif quick_choice == "2":
                                self.auto_trade_symbols = ["EURUSD", "GBPUSD", "USDCHF"]
                                print("✅ Konservative Auswahl")
                            elif quick_choice == "3":
                                self.auto_trade_symbols = ["EURUSD", "EURGBP", "EURJPY", "EURCHF"]
                                print("✅ EUR-Cross ausgewählt")
                            elif quick_choice == "4":
                                pairs_input = input("Paare eingeben (kommagetrennt): ").upper()
                                if pairs_input:
                                    self.auto_trade_symbols = [p.strip() for p in pairs_input.split(',')]
                                    print(f"✅ {len(self.auto_trade_symbols)} Paare eingegeben")
                                else:
                                    print("❌ Keine Eingabe - verwende aktuelle Paare")
                            else:
                                print("❌ Ungültige Auswahl - verwende aktuelle Paare")
                
                        # Stelle sicher, dass Paare vorhanden sind
                        if not hasattr(self, 'auto_trade_symbols') or not self.auto_trade_symbols:
                            self.auto_trade_symbols = ["EURUSD"]  # Fallback
                            print("⚠️ Fallback: EURUSD wird verwendet")
                
                        # Intervall-Einstellung
                        print(f"\n⏱️ TRADING INTERVALL")
                        print("─" * 25)
                        print(f"Aktuell: {self.analysis_interval}s")
                        print("💡 Empfohlen: 120-300s für konservatives Trading")
                
                        new_interval = input(f"Neues Intervall in Sekunden (Enter für {self.analysis_interval}): ")
                        if new_interval:
                            try:
                                self.analysis_interval = int(new_interval)
                                print(f"✅ Intervall auf {self.analysis_interval}s gesetzt")
                            except ValueError:
                                print("❌ Ungültiges Intervall - verwende Standard")
                
                        # Auto-Trading aktivieren
                        self.auto_trading = True
                
                        print(f"\n✅ AUTO-TRADING KONFIGURIERT")
                        print("─" * 35)
                        print(f"📊 Symbole: {len(self.auto_trade_symbols)}")
                        print(f"💱 Paare: {', '.join(self.auto_trade_symbols[:5])}")
                        if len(self.auto_trade_symbols) > 5:
                            print(f"      ... und {len(self.auto_trade_symbols) - 5} weitere")
                        print(f"⏱️ Intervall: {self.analysis_interval}s")
                        print(f"🛡️ Risk Management: {'✅' if hasattr(self, 'risk_manager') and self.risk_manager else '❌'}")
                
                        self.log("INFO", f"Auto-Trading aktiviert mit {len(self.auto_trade_symbols)} Paaren", "TRADE")
                        print(f"\n🚀 Starte Auto-Trading...")
                        self.run_auto_trading()
    
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "7":
            self.log("INFO", "Position Management gestartet", "USER")
            self.print_header("POSITION MANAGEMENT")
            self.manage_open_positions()
            self.log("INFO", "Position Management abgeschlossen", "TRADE")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "8":
            self.log("INFO", "Partial Close Einstellungen aufgerufen", "USER")
            self.print_header("PARTIAL CLOSE EINSTELLUNGEN")
            print(f"Status: {'✅' if self.partial_close_enabled else '❌'}")
            print(f"Target 1: {self.profit_target_1}% ({self.first_target_percent}% close)")
            print(f"Target 2: {self.profit_target_2}% ({self.second_target_percent}% close)")

            print("\n1. Ein/Ausschalten")
            print("2. Targets anpassen")

            pc_choice = input("Wählen (1-2): ").strip()

            if pc_choice == "1":
                old_status = self.partial_close_enabled
                self.partial_close_enabled = not self.partial_close_enabled
                self.log("INFO", f"Partial Close: {old_status} -> {self.partial_close_enabled}", "SETTINGS")
                print(f"Partial Close: {'✅' if self.partial_close_enabled else '❌'}")

            elif pc_choice == "2":
                try:
                    old_target1 = self.profit_target_1
                    old_target2 = self.profit_target_2
                    self.profit_target_1 = float(input(f"Target 1 % (aktuell {self.profit_target_1}): "))
                    self.profit_target_2 = float(input(f"Target 2 % (aktuell {self.profit_target_2}): "))
                    self.log("INFO", f"Partial Close Targets: {old_target1}%/{old_target2}% -> {self.profit_target_1}%/{self.profit_target_2}%", "SETTINGS")
                    print("Targets aktualisiert")
                except:
                    self.log("ERROR", "Ungültige Eingabe bei Partial Close Target-Änderung", "SETTINGS")
                    print("Ungültige Eingabe")

            input("\nDrücken Sie Enter zum Fortfahren...")
            return True
    
        elif choice == "9":
            self.log("INFO", "RSI Einstellungen aufgerufen", "USER")
            self.print_header("RSI EINSTELLUNGEN")
            print(f"RSI Periode: {self.rsi_period}")
            print(f"Zeitrahmen: {self.rsi_timeframe}")
            print(f"Überkauft Level: {self.rsi_overbought}")
            print(f"Überverkauft Level: {self.rsi_oversold}")

            print("\n1. RSI Periode ändern")
            print("2. Überkauft/Überverkauft Levels")
            print("3. Zeitrahmen ändern")
            print("4. RSI Test")

            rsi_choice = input("Wählen (1-4): ").strip()

            if rsi_choice == "1":
                try:
                    old_period = self.rsi_period
                    new_period = int(input(f"RSI Periode (aktuell {self.rsi_period}): "))
                    if 5 <= new_period <= 50:
                        self.rsi_period = new_period
                        self.log("INFO", f"RSI Periode geändert: {old_period} -> {new_period}", "SETTINGS")
                        print(f"RSI Periode auf {new_period} gesetzt")
                    else:
                        self.log("WARNING", f"RSI Periode ungültig: {new_period} (erlaubt: 5-50)", "SETTINGS")
                        print("Periode muss zwischen 5 und 50 liegen")
                except:
                    self.log("ERROR", "Ungültige Eingabe bei RSI Periode-Änderung", "SETTINGS")
                    print("Ungültige Eingabe")

            elif rsi_choice == "2":
                try:
                    old_overbought = self.rsi_overbought
                    old_oversold = self.rsi_oversold
                    new_overbought = float(input(f"Überkauft Level (aktuell {self.rsi_overbought}): "))
                    new_oversold = float(input(f"Überverkauft Level (aktuell {self.rsi_oversold}): "))
        
                    if 50 <= new_overbought <= 90 and 10 <= new_oversold <= 50:
                        self.rsi_overbought = new_overbought
                        self.rsi_oversold = new_oversold
                        self.log("INFO", f"RSI Levels geändert: {old_overbought}/{old_oversold} -> {new_overbought}/{new_oversold}", "SETTINGS")
                        print("RSI Levels aktualisiert")
                    else:
                        self.log("WARNING", f"RSI Levels ungültig: {new_overbought}/{new_oversold}", "SETTINGS")
                        print("Ungültige Levels (Überkauft: 50-90, Überverkauft: 10-50)")
                except:
                    self.log("ERROR", "Ungültige Eingabe bei RSI Level-Änderung", "SETTINGS")
                    print("Ungültige Eingabe")

            elif rsi_choice == "3":
                self.log("INFO", "RSI Zeitrahmen-Änderung gestartet", "SETTINGS")
                print("\nZeitrahmen:")
                print("1. M1 (1 Minute)")
                print("2. M5 (5 Minuten)")
                print("3. M15 (15 Minuten)")
                print("4. M30 (30 Minuten)")
                print("5. H1 (1 Stunde)")
    
                tf_choice = input("Wählen (1-5): ").strip()
    
                timeframes = {
                    "1": mt5.TIMEFRAME_M1,
                    "2": mt5.TIMEFRAME_M5,
                    "3": mt5.TIMEFRAME_M15,
                    "4": mt5.TIMEFRAME_M30,
                    "5": mt5.TIMEFRAME_H1
                }
    
                if tf_choice in timeframes:
                    old_tf = self.rsi_timeframe
                    self.rsi_timeframe = timeframes[tf_choice]
                    tf_names = {"1": "M1", "2": "M5", "3": "M15", "4": "M30", "5": "H1"}
                    self.log("INFO", f"RSI Zeitrahmen geändert: {old_tf} -> {tf_names[tf_choice]}", "SETTINGS")
                    print(f"Zeitrahmen auf {tf_names[tf_choice]} gesetzt")
                else:
                    self.log("WARNING", f"Ungültige Zeitrahmen-Auswahl: {tf_choice}", "SETTINGS")
                    print("Ungültige Auswahl")

            elif rsi_choice == "4":
                symbol = input("Symbol für RSI Test: ").upper()
                if symbol:
                    self.log("INFO", f"RSI Test gestartet für {symbol}", "ANALYSIS")
                    rsi_value = self.calculate_rsi(symbol)
                    if rsi_value:
                        signal, desc = self.get_rsi_signal(rsi_value)
                        self.log("INFO", f"RSI Test {symbol}: {rsi_value} ({signal})", "ANALYSIS")
                        print(f"\n{symbol} RSI Test:")
                        print(f"RSI Wert: {rsi_value}")
                        print(f"Signal: {signal}")
                        print(f"Beschreibung: {desc}")
                    else:
                        self.log("ERROR", f"RSI Berechnung fehlgeschlagen für {symbol}", "ANALYSIS")
                        print("RSI Berechnung fehlgeschlagen")

            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "10":
            self.log("INFO", "Support/Resistance Einstellungen aufgerufen", "USER")
            self.sr_settings_menu()
            self.log("INFO", "Support/Resistance Einstellungen beendet", "SETTINGS")
            return True

        elif choice == "11":
            self.log("INFO", "Trading Companion Menü aufgerufen", "USER")
            self.companion_menu()
            self.log("INFO", "Trading Companion Menü beendet", "COMPANION")
            return True

        elif choice == "12":
            self.log("INFO", "MT5 Verbindungsmenü aufgerufen", "USER")
            self.print_header("MT5 VERBINDUNG")
            if self.mt5_connected:
                print("MT5 ist verbunden")
                disconnect_choice = input("MT5 trennen? (ja/nein): ")
                if disconnect_choice.lower() == "ja":
                    self.log("INFO", "MT5 Trennung durch Benutzer initiiert", "MT5")
                    self.disconnect_mt5()
            else:
                print("MT5 ist nicht verbunden")
                connect_choice = input("MT5 verbinden? (ja/nein): ")
                if connect_choice.lower() == "ja":
                    self.log("INFO", "MT5 Verbindung durch Benutzer initiiert", "MT5")
                    success = self.connect_mt5()
                    if success:
                        self.log("INFO", "MT5 erfolgreich verbunden", "MT5")
                    else:
                        self.log("ERROR", "MT5 Verbindung fehlgeschlagen", "MT5")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "13":
            self.log("INFO", "MACD Einstellungen aufgerufen", "USER")
            self.print_header("MACD EINSTELLUNGEN")
            self.macd_settings_menu()
            self.log("INFO", "MACD Einstellungen beendet", "SETTINGS")
            return True
    
        elif choice == "14":
            self.log("INFO", "Trailing Stop Einstellungen aufgerufen", "USER")
            self.print_header("TRAILING STOP EINSTELLUNGEN")
            self.trailing_stop_settings_menu()
            self.log("INFO", "Trailing Stop Einstellungen beendet", "SETTINGS")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "15":
            self.log("INFO", "Multi-Timeframe Einstellungen aufgerufen", "USER")
            self.print_header("MULTI-TIMEFRAME EINSTELLUNGEN")
            self.mtf_settings_menu()
            self.log("INFO", "Multi-Timeframe Einstellungen beendet", "SETTINGS")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "16":
            self.log("INFO", "Risk Management Menü aufgerufen", "USER")
            if hasattr(self, 'risk_manager') and self.risk_manager:
                self.risk_management_menu()
            else:
                print("❌ Risk Manager nicht verfügbar")
                print("💡 Tipp: Stellen Sie sicher dass risk_manager.py existiert")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "17":
            self.log("INFO", "Währungspaar Management aufgerufen", "USER")
            self.currency_pair_management_menu()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "18":
            self.log("INFO", "RL Menü aufgerufen", "USER")
            if self.rl_enabled:
                self.rl_menu_enhanced()  # ← Ändere das hier!
            else:
                print("❌ Reinforcement Learning nicht verfügbar")
                print("💡 Installieren Sie TensorFlow: pip install tensorflow")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "19":
            self.log("INFO", "System-Shutdown durch Benutzer eingeleitet", "SYSTEM")
            self.print_header("SYSTEM BEENDEN")
            print("Stoppe alle Prozesse...")

            if self.companion_enabled:
                self.log("INFO", "Trading Companion wird gestoppt", "COMPANION")
                print("Stoppe Trading Companion...")
                self.stop_trading_companion()

            if self.auto_trading:
                self.log("INFO", "Auto-Trading wird gestoppt", "TRADE")
                print("Stoppe Auto-Trading...")
                self.auto_trading = False

            # Risk Manager Abschlussbericht
            if hasattr(self, 'risk_manager') and self.risk_manager:
                try:
                    print("\n🛡️ Session Abschlussbericht:")
                    summary = self.risk_manager.get_risk_summary()
                    if summary:
                        print(f"📊 Tages P&L: {summary.get('daily_pnl', 0):.2f}€")
                        print(f"💼 Trades heute: {summary.get('trades_today', 0)}")
                        print(f"📈 Offene Positionen: {summary.get('open_positions', 0)}")
                except Exception as e:
                    print(f"⚠️ Risk Manager Abschlussbericht Fehler: {e}")

            if self.mt5_connected:
                self.log("INFO", "MT5 Verbindung wird getrennt", "MT5")
                print("Trenne MT5...")
                self.disconnect_mt5()

            self.log("INFO", "System erfolgreich heruntergefahren", "SYSTEM")
            print("Alle Prozesse beendet. Auf Wiedersehen!")
            return False


        # NEUE ERWEITERTE OPTIONEN (20-27)
        if choice == "20" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "Einzelne erweiterte Indikatoren", "USER")
            self.show_individual_advanced_indicators()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "21" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "Vollständige technische Analyse mit allen Indikatoren", "USER")
            self.comprehensive_technical_analysis()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "22" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "Signal-Generator mit allen Indikatoren", "USER")
            self.advanced_signal_generator()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "23" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "Erweiterte Indikator-Einstellungen", "USER")
            self.advanced_indicator_settings_menu()
            return True

        elif choice == "24" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "KI-Analyse mit allen Indikatoren", "USER")
            self.enhanced_ai_analysis()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "25" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "Multi-Indikator Scanner", "USER")
            self.multi_indicator_scanner()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "26" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "Indikator-Vergleich", "USER")
            self.indicator_comparison_analysis()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        elif choice == "27" and getattr(self, 'has_extended_indicators', False):
            self.log("INFO", "Indikator-Test & Optimierung", "USER")
            self.indicator_testing_suite()
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

            # BEENDEN (dynamisch)

        elif choice == "19" and not getattr(self, 'has_extended_indicators', False):
            return self.shutdown_system()
        elif choice == "28" and getattr(self, 'has_extended_indicators', False):
            return self.shutdown_system()

            # FEATURE NICHT VERFÜGBAR
        elif choice in ["20", "21", "22", "23", "24", "25", "26", "27"] and not getattr(self, 'has_extended_indicators', False):
            print("❌ Erweiterte Indikatoren nicht verfügbar")
            print("💡 Installieren Sie advanced_indicators.py für diese Features")
            print("📝 Datei muss im gleichen Ordner wie FinGPT.py liegen")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

        else:
            print("❌ Ungültige Option")
            input("\nDrücken Sie Enter zum Fortfahren...")
            return True

    def advanced_signal_generator(self):
        """Signal-Generator mit allen verfügbaren Indikatoren"""
        self.print_header("SIGNAL-GENERATOR (ALLE INDIKATOREN)")
    
        if not self.advanced_indicators:
            print("❌ Erweiterte Indikatoren nicht verfügbar")
            return
    
        print("📊 Erstelle Trading-Signale mit allen verfügbaren Indikatoren")
        print("─" * 60)
    
        # Single Symbol oder Multiple
        mode = input("Modus wählen:\n1. Einzelnes Symbol\n2. Multiple Symbole\nWahl (1-2): ").strip()
    
        if mode == "1":
            symbol = input("💱 Symbol eingeben: ").upper()
            if symbol:
                self.generate_single_signal(symbol)
    
        elif mode == "2":
            symbols_input = input("💱 Symbole (kommagetrennt, z.B. EURUSD,GBPUSD): ").upper()
            if symbols_input:
                symbols = [s.strip() for s in symbols_input.split(',')]
                self.generate_multiple_signals(symbols)
    
        else:
            print("❌ Ungültige Auswahl")

    def generate_single_signal(self, symbol):
        """Generiert detailliertes Signal für einzelnes Symbol"""
        try:
            print(f"\n🔄 Generiere umfassendes Signal für {symbol}...")
        
            if not self.integration:
                print("❌ Integration nicht verfügbar")
                return
        
            # Erstelle Trading-Signal mit allen Indikatoren
            trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
        
            print(f"\n{'='*60}")
            print(f"🎯 TRADING-SIGNAL: {symbol}")
            print(f"{'='*60}")
        
            # Haupt-Signal mit Icon
            signal_icon = "🚀" if trading_signal['signal'] == "STRONG_BUY" else \
                         "🟢" if trading_signal['signal'] == "BUY" else \
                         "💥" if trading_signal['signal'] == "STRONG_SELL" else \
                         "🔴" if trading_signal['signal'] == "SELL" else "🟡"
        
            print(f"{signal_icon} HAUPTSIGNAL: {trading_signal['signal']}")
            print(f"🎯 KONFIDENZ: {trading_signal['confidence']}")
            print(f"📊 ANALYSIERTE INDIKATOREN: {trading_signal['total_indicators']}")
            print(f"⏰ ZEITSTEMPEL: {trading_signal['timestamp']}")
        
            # Signal-Verhältnis
            if trading_signal.get('buy_ratio', 0) > 0 or trading_signal.get('sell_ratio', 0) > 0:
                print(f"\n📈 SIGNAL-VERTEILUNG:")
                print(f"🟢 Bullisch: {trading_signal.get('buy_ratio', 0):.1%}")
                print(f"🔴 Bearisch: {trading_signal.get('sell_ratio', 0):.1%}")
        
            # Unterstützende Signale
            if trading_signal.get('supporting_signals'):
                print(f"\n✅ UNTERSTÜTZENDE SIGNALE:")
                for i, signal in enumerate(trading_signal['supporting_signals'], 1):
                    print(f"{i:2d}. {signal}")
        
            # Neutrale/Konflikt Signale
            if trading_signal.get('conflicting_signals'):
                print(f"\n⚠️ NEUTRALE SIGNALE:")
                for i, signal in enumerate(trading_signal['conflicting_signals'], 1):
                    print(f"{i:2d}. {signal}")
        
            # Trading-Empfehlung
            print(f"\n💡 TRADING-EMPFEHLUNG:")
            if trading_signal['signal'] in ['STRONG_BUY', 'BUY']:
                print(f"📈 Kaufgelegenheit erkannt")
                print(f"🎯 Empfohlene Aktion: Long-Position eröffnen")
            
                # Berechne Einstiegs-Levels
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    current_price = tick.ask
                    print(f"💰 Aktueller Einstiegspreis: {current_price:.5f}")
                
                    # Support/Resistance für Stop-Loss
                    sr_data = self.calculate_support_resistance(symbol)
                    if sr_data and sr_data['nearest_support']:
                        sup_level, _ = sr_data['nearest_support']
                        suggested_sl = sup_level * 0.999  # 0.1% unter Support
                        print(f"🛑 Empfohlener Stop-Loss: {suggested_sl:.5f}")
                
                    if sr_data and sr_data['nearest_resistance']:
                        res_level, _ = sr_data['nearest_resistance']
                        suggested_tp = res_level * 1.001  # 0.1% vor Resistance
                        print(f"🎯 Empfohlenes Take-Profit: {suggested_tp:.5f}")
        
            elif trading_signal['signal'] in ['STRONG_SELL', 'SELL']:
                print(f"📉 Verkaufsgelegenheit erkannt")
                print(f"🎯 Empfohlene Aktion: Short-Position oder bestehende Position schließen")
            
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    current_price = tick.bid
                    print(f"💰 Aktueller Verkaufspreis: {current_price:.5f}")
        
            else:
                print(f"⏸️ Abwarten empfohlen")
                print(f"🎯 Empfohlene Aktion: Weitere Bestätigung abwarten")
                print(f"📊 Grund: Gemischte oder neutrale Signale")
        
            print(f"{'='*60}")
        
        except Exception as e:
            print(f"❌ Signal-Generierung Fehler: {e}")

    def generate_multiple_signals(self, symbols):
        """Generiert Signale für mehrere Symbole"""
        try:
            print(f"\n🔄 Generiere Signale für {len(symbols)} Symbole...")
        
            if not self.integration:
                print("❌ Integration nicht verfügbar")
                return
        
            all_signals = []
        
            for symbol in symbols:
                print(f"📊 Analysiere {symbol}...")
                try:
                    trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
                
                    # Bewerte Signal-Qualität
                    score = 0
                    if trading_signal['signal'] in ['STRONG_BUY', 'STRONG_SELL']:
                        score = 5
                    elif trading_signal['signal'] in ['BUY', 'SELL']:
                        score = 3
                    elif trading_signal['signal'] == 'NEUTRAL':
                        score = 1
                
                    # Konfidenz-Bonus
                    if trading_signal['confidence'] == 'HOCH':
                        score += 2
                    elif trading_signal['confidence'] == 'MITTEL':
                        score += 1
                
                    trading_signal['score'] = score
                    all_signals.append(trading_signal)
                
                    time.sleep(0.5)  # Kurze Pause zwischen Analysen
                
                except Exception as e:
                    print(f"⚠️ Fehler bei {symbol}: {e}")
        
            # Sortiere nach Score
            all_signals.sort(key=lambda x: x['score'], reverse=True)
        
            # Zeige Zusammenfassung
            print(f"\n{'='*70}")
            print(f"📊 MULTI-SYMBOL SIGNAL-ÜBERSICHT")
            print(f"{'='*70}")
        
            print(f"{'Symbol':<8} {'Signal':<12} {'Konfidenz':<10} {'Score':<6} {'Indikatoren':<12}")
            print("─" * 70)
        
            for signal in all_signals:
                symbol = signal['symbol']
                main_signal = signal['signal']
                confidence = signal['confidence']
                score = signal['score']
                indicators = signal.get('total_indicators', 0)
            
                signal_icon = "🚀" if main_signal == "STRONG_BUY" else \
                             "🟢" if main_signal == "BUY" else \
                             "💥" if main_signal == "STRONG_SELL" else \
                             "🔴" if main_signal == "SELL" else "🟡"
            
                print(f"{symbol:<8} {signal_icon}{main_signal:<11} {confidence:<10} {score:<6} {indicators:<12}")
        
            # Top-Gelegenheiten hervorheben
            strong_signals = [s for s in all_signals if s['score'] >= 5]
        
            if strong_signals:
                print(f"\n🎯 TOP TRADING-GELEGENHEITEN (Score ≥ 5):")
                print("─" * 50)
            
                for i, signal in enumerate(strong_signals[:5], 1):  # Top 5
                    symbol = signal['symbol']
                    main_signal = signal['signal']
                    buy_ratio = signal.get('buy_ratio', 0)
                    sell_ratio = signal.get('sell_ratio', 0)
                
                    ratio = buy_ratio if main_signal in ['STRONG_BUY', 'BUY'] else sell_ratio
                
                    print(f"🏆 {i}. {symbol}: {main_signal} ({ratio:.1%} Übereinstimmung)")
                
                    # Zeige Top-2 unterstützende Signale
                    if signal.get('supporting_signals'):
                        top_signals = signal['supporting_signals'][:2]
                        for supporting in top_signals:
                            print(f"   ✅ {supporting}")
            else:
                print(f"\n⏸️ Keine starken Trading-Gelegenheiten gefunden")
                print(f"💡 Alle Signale sind neutral oder widersprüchlich")
        
            print(f"{'='*70}")
        
        except Exception as e:
            print(f"❌ Multi-Signal Fehler: {e}")

    def show_individual_advanced_indicators(self):
        """Zeigt einzelne erweiterte Indikatoren zur Auswahl"""
        while True:
            self.print_header("EINZELNE ERWEITERTE INDIKATOREN")
        
            print("📊 Verfügbare Indikatoren:")
            print("─" * 35)
        
            indicator_menu = [
                ("1", "📈", "Williams %R"),
                ("2", "📊", "Commodity Channel Index (CCI)"),
                ("3", "🌊", "Awesome Oscillator"),
                ("4", "☁️", "Ichimoku Cloud"),
                ("5", "📊", "VWAP (Volume Weighted Average Price)"),
                ("6", "💰", "Money Flow Index (MFI)"),
                ("7", "📈", "Average Directional Index (ADX)"),
                ("8", "📊", "Alle Indikatoren anzeigen"),
                ("9", "⬅️", "Zurück")
            ]
        
            for num, icon, desc in indicator_menu:
                print(f" {num}. {icon} {desc}")
        
            print("─" * 35)
        
            choice = input("🎯 Indikator wählen (1-9): ").strip()
        
            if choice == "9":
                break
            elif choice in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                symbol = input("💱 Symbol eingeben: ").upper()
                if symbol:
                    self.display_selected_indicator(choice, symbol)
            else:
                print("❌ Ungültige Auswahl")
        
            if choice != "9":
                input("\nDrücken Sie Enter zum Fortfahren...")

    def display_selected_indicator(self, indicator_choice, symbol):
        """Zeigt einen spezifischen Indikator an"""
        if not self.advanced_indicators:
            print("❌ Erweiterte Indikatoren nicht verfügbar")
            return
    
        try:
            print(f"\n📊 Berechne Indikator für {symbol}...")
        
            if indicator_choice == "1":
                # Williams %R
                wr_data = self.advanced_indicators.calculate_williams_r(symbol)
                if wr_data:
                    print(f"\n📈 WILLIAMS %R ANALYSE:")
                    print(f"Wert: {wr_data['value']}%")
                    print(f"Signal: {wr_data['signal']}")
                    print(f"Beschreibung: {wr_data['description']}")
                    print(f"Überkauft Level: {wr_data['overbought_level']}")
                    print(f"Überverkauft Level: {wr_data['oversold_level']}")
                else:
                    print("❌ Williams %R Daten nicht verfügbar")
        
            elif indicator_choice == "2":
                # CCI
                cci_data = self.advanced_indicators.calculate_cci(symbol)
                if cci_data:
                    print(f"\n📊 COMMODITY CHANNEL INDEX:")
                    print(f"Wert: {cci_data['value']}")
                    print(f"Signal: {cci_data['signal']}")
                    print(f"Beschreibung: {cci_data['description']}")
                    print(f"Überkauft Level: {cci_data['overbought_level']}")
                    print(f"Überverkauft Level: {cci_data['oversold_level']}")
                else:
                    print("❌ CCI Daten nicht verfügbar")
        
            elif indicator_choice == "3":
                # Awesome Oscillator
                ao_data = self.advanced_indicators.calculate_awesome_oscillator(symbol)
                if ao_data:
                    print(f"\n🌊 AWESOME OSCILLATOR:")
                    print(f"Wert: {ao_data['value']}")
                    print(f"Signal: {ao_data['signal']}")
                    print(f"Beschreibung: {ao_data['description']}")
                    print(f"Über Nulllinie: {ao_data['above_zero']}")
                    print(f"Momentum: {ao_data['momentum']}")
                else:
                    print("❌ Awesome Oscillator Daten nicht verfügbar")
        
            elif indicator_choice == "4":
                # Ichimoku
                ichimoku_data = self.advanced_indicators.calculate_ichimoku(symbol)
                if ichimoku_data:
                    print(f"\n☁️ ICHIMOKU CLOUD ANALYSE:")
                    print(f"Tenkan-sen: {ichimoku_data['tenkan_sen']}")
                    print(f"Kijun-sen: {ichimoku_data['kijun_sen']}")
                    print(f"Cloud Top: {ichimoku_data['cloud_top']}")
                    print(f"Cloud Bottom: {ichimoku_data['cloud_bottom']}")
                    print(f"Preis vs Cloud: {ichimoku_data['price_vs_cloud']}")
                    print(f"Cloud Signal: {ichimoku_data['cloud_signal']}")
                    print(f"TK Signal: {ichimoku_data['tk_signal']}")
                    print(f"Gesamtsignal: {ichimoku_data['overall_signal']}")
                    print(f"Beschreibung: {ichimoku_data['description']}")
                else:
                    print("❌ Ichimoku Daten nicht verfügbar")
        
            elif indicator_choice == "5":
                # VWAP
                vwap_data = self.advanced_indicators.calculate_vwap(symbol)
                if vwap_data:
                    print(f"\n📊 VWAP ANALYSE:")
                    print(f"VWAP: {vwap_data['vwap']}")
                    print(f"Aktueller Preis: {vwap_data['current_price']}")
                    print(f"Abstand: {vwap_data['distance_pct']}%")
                    print(f"Signal: {vwap_data['signal']}")
                    print(f"Beschreibung: {vwap_data['description']}")
                    print(f"Preis über VWAP: {vwap_data['above_vwap']}")
                else:
                    print("❌ VWAP Daten nicht verfügbar")
        
            elif indicator_choice == "6":
                # MFI
                mfi_data = self.advanced_indicators.calculate_mfi(symbol)
                if mfi_data:
                    print(f"\n💰 MONEY FLOW INDEX:")
                    print(f"Wert: {mfi_data['value']}")
                    print(f"Signal: {mfi_data['signal']}")
                    print(f"Beschreibung: {mfi_data['description']}")
                    print(f"Überkauft Level: {mfi_data['overbought_level']}")
                    print(f"Überverkauft Level: {mfi_data['oversold_level']}")
                else:
                    print("❌ MFI Daten nicht verfügbar")
        
            elif indicator_choice == "7":
                # ADX
                adx_data = self.advanced_indicators.calculate_adx(symbol)
                if adx_data:
                    print(f"\n📈 AVERAGE DIRECTIONAL INDEX:")
                    print(f"ADX: {adx_data['adx']}")
                    print(f"DI+: {adx_data['di_plus']}")
                    print(f"DI-: {adx_data['di_minus']}")
                    print(f"Trend-Stärke: {adx_data['trend_strength']}")
                    print(f"Trend-Richtung: {adx_data['trend_direction']}")
                    print(f"Signal: {adx_data['signal']}")
                    print(f"Starker Trend: {adx_data['strong_trend']}")
                    print(f"Beschreibung: {adx_data['description']}")
                else:
                    print("❌ ADX Daten nicht verfügbar")
        
            elif indicator_choice == "8":
                # Alle Indikatoren
                analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
                if analysis:
                    self.advanced_indicators.print_analysis_report(symbol, analysis)
                else:
                    print("❌ Umfassende Analyse nicht verfügbar")
        
        except Exception as e:
            print(f"❌ Fehler bei Indikator-Berechnung: {e}")

    def comprehensive_technical_analysis(self):
        """Vollständige technische Analyse mit allen verfügbaren Indikatoren"""
        self.print_header("VOLLSTÄNDIGE TECHNISCHE ANALYSE")
    
        symbol = input("💱 Symbol für vollständige Analyse: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
    
        print(f"\n🔄 Führe vollständige Analyse für {symbol} durch...")
        print("─" * 60)
    
        try:
            # 1. Basis-Indikatoren
            print("📊 BASIS-INDIKATOREN:")
            print("─" * 30)
        
            # RSI
            rsi_value = self.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, rsi_desc = self.get_rsi_signal(rsi_value)
                icon = "🟢" if rsi_signal == "BUY" else "🔴" if rsi_signal == "SELL" else "🟡"
                print(f"{icon} RSI: {rsi_value} - {rsi_desc}")
        
            # MACD
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, macd_desc = self.get_macd_signal(macd_data)
                icon = "🟢" if macd_signal == "BUY" else "🔴" if macd_signal == "SELL" else "🟡"
                print(f"{icon} MACD: {macd_desc}")
        
            # Support/Resistance
            sr_data = self.calculate_support_resistance(symbol)
            if sr_data:
                current_price = sr_data['current_price']
                sr_signal, sr_desc = self.get_sr_signal(sr_data, current_price)
                icon = "🟢" if sr_signal == "BUY" else "🔴" if sr_signal == "SELL" else "🟡"
                print(f"{icon} S/R: {sr_desc}")
        
            # 2. Erweiterte Indikatoren
            if self.advanced_indicators:
                print("\n📈 ERWEITERTE INDIKATOREN:")
                print("─" * 30)
            
                advanced_analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
                if advanced_analysis:
                    self.advanced_indicators.print_analysis_report(symbol, advanced_analysis)
        
            # 3. Gesamtbewertung
            if self.integration:
                print("\n🎯 GESAMTBEWERTUNG:")
                print("─" * 30)
            
                trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
            
                signal_icon = "🚀" if trading_signal['signal'] == "STRONG_BUY" else \
                             "🟢" if trading_signal['signal'] == "BUY" else \
                             "💥" if trading_signal['signal'] == "STRONG_SELL" else \
                             "🔴" if trading_signal['signal'] == "SELL" else "🟡"
            
                print(f"{signal_icon} SIGNAL: {trading_signal['signal']}")
                print(f"🎯 KONFIDENZ: {trading_signal['confidence']}")
                print(f"📊 ANALYSIERTE INDIKATOREN: {trading_signal['total_indicators']}")
            
                if trading_signal.get('buy_ratio', 0) > 0 or trading_signal.get('sell_ratio', 0) > 0:
                    print(f"📈 Bullisch: {trading_signal.get('buy_ratio', 0):.1%}")
                    print(f"📉 Bearisch: {trading_signal.get('sell_ratio', 0):.1%}")
            
                # Top-Signale anzeigen
                if trading_signal.get('supporting_signals'):
                    print(f"\n✅ TOP UNTERSTÜTZENDE SIGNALE:")
                    for i, signal in enumerate(trading_signal['supporting_signals'][:5], 1):
                        print(f"{i}. {signal}")
        
            print("─" * 60)
        
        except Exception as e:
            print(f"❌ Vollständige Analyse Fehler: {e}")

    def advanced_indicator_settings_menu(self):
        """Einstellungsmenü für erweiterte Indikatoren"""
        if not self.advanced_indicators:
            print("❌ Erweiterte Indikatoren nicht verfügbar")
            return
    
        while True:
            self.print_header("ERWEITERTE INDIKATOR-EINSTELLUNGEN")
        
            print("📊 Verfügbare Einstellungen:")
            print("─" * 35)
            print(" 1. Williams %R Parameter")
            print(" 2. CCI Parameter") 
            print(" 3. Awesome Oscillator Parameter")
            print(" 4. Ichimoku Parameter")
            print(" 5. VWAP Parameter")
            print(" 6. Money Flow Index Parameter")
            print(" 7. ADX Parameter")
            print(" 8. Alle auf Standard zurücksetzen")
            print(" 9. Zurück")
        
            setting_choice = input("\n🎯 Ihre Wahl (1-9): ").strip()
        
            if setting_choice == "1":
                self.configure_williams_r_settings()
            elif setting_choice == "8":
                confirm = input("Alle auf Standard zurücksetzen? (ja/nein): ")
                if confirm.lower() == "ja":
                    self.reset_advanced_indicator_settings()
                    print("✅ Alle Einstellungen zurückgesetzt")
            elif setting_choice == "9":
                break
            else:
                print("❌ Funktion noch nicht implementiert oder ungültige Auswahl")
        
            if setting_choice != "9":
                input("\nDrücken Sie Enter zum Fortfahren...")

    def configure_williams_r_settings(self):
        """Konfiguration für Williams %R"""
        if not self.advanced_indicators:
            return
    
        print("\n📊 WILLIAMS %R EINSTELLUNGEN")
        print("─" * 30)
        print(f"Aktuelle Periode: {self.advanced_indicators.williams_r_period}")
        print(f"Überkauft Level: {self.advanced_indicators.williams_r_overbought}")
        print(f"Überverkauft Level: {self.advanced_indicators.williams_r_oversold}")
    
        try:
            period = input(f"Neue Periode (5-50, aktuell {self.advanced_indicators.williams_r_period}): ")
            if period:
                period = int(period)
                if 5 <= period <= 50:
                    self.advanced_indicators.williams_r_period = period
                    print(f"✅ Williams %R Periode auf {period} gesetzt")
                else:
                    print("❌ Periode muss zwischen 5 und 50 liegen")
        except ValueError:
            print("❌ Ungültige Eingabe")

    def reset_advanced_indicator_settings(self):
        """Setzt erweiterte Indikator-Einstellungen zurück"""
        if self.advanced_indicators:
            # Standard-Werte setzen
            self.advanced_indicators.williams_r_period = 14
            self.advanced_indicators.williams_r_overbought = -20
            self.advanced_indicators.williams_r_oversold = -80
            self.advanced_indicators.cci_period = 20
            self.advanced_indicators.cci_overbought = 100
            self.advanced_indicators.cci_oversold = -100
            self.advanced_indicators.ao_fast_period = 5
            self.advanced_indicators.ao_slow_period = 34
            # ... weitere Standard-Werte nach Bedarf

    def enhanced_ai_analysis(self):
        """Erweiterte KI-Analyse mit allen Indikatoren"""
        self.print_header("ERWEITERTE KI-ANALYSE")
    
        symbol = input("💱 Symbol für erweiterte KI-Analyse: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
    
        if not self.integration:
            print("❌ Integration nicht verfügbar")
            return
    
        print(f"\n🔄 Führe erweiterte KI-Analyse für {symbol} durch...")
    
        try:
            ai_response = self.integration.enhanced_ai_analysis(symbol, include_advanced=True)
            print("\n🤖 ERWEITERTE KI-ANALYSE:")
            print("─" * 40)
            print(ai_response)
        except Exception as e:
            print(f"❌ Erweiterte KI-Analyse Fehler: {e}")

    def multi_indicator_scanner(self):
        """Scanner für multiple Symbole mit allen Indikatoren"""
        self.print_header("MULTI-INDIKATOR SCANNER")
    
        symbols_input = input("💱 Symbole (kommagetrennt, leer für Standard): ").upper()
    
        if symbols_input:
            symbols = [s.strip() for s in symbols_input.split(',')]
        else:
            symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]
    
        print(f"\n🔄 Scanne {len(symbols)} Symbole...")
    
        if not self.integration:
            print("❌ Integration nicht verfügbar")
            return
    
        try:
            opportunities = []
        
            for symbol in symbols:
                print(f"📊 Scanne {symbol}...")
                try:
                    trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
                
                    score = 0
                    if trading_signal['signal'] in ['STRONG_BUY', 'STRONG_SELL']:
                        score = 5
                    elif trading_signal['signal'] in ['BUY', 'SELL']:
                        score = 3
                
                    if trading_signal['confidence'] == 'HOCH':
                        score += 2
                
                    trading_signal['score'] = score
                    opportunities.append(trading_signal)
                
                except Exception as e:
                    print(f"⚠️ {symbol}: {e}")
        
            # Sortiere nach Score
            opportunities.sort(key=lambda x: x['score'], reverse=True)
        
            print(f"\n{'='*60}")
            print("📊 SCANNER ERGEBNISSE")
            print(f"{'='*60}")
        
            for opp in opportunities:
                signal_icon = "🚀" if opp['signal'] == "STRONG_BUY" else \
                             "🟢" if opp['signal'] == "BUY" else \
                             "💥" if opp['signal'] == "STRONG_SELL" else \
                             "🔴" if opp['signal'] == "SELL" else "🟡"
            
                print(f"{signal_icon} {opp['symbol']:8} | {opp['signal']:12} | Score: {opp['score']} | Konfidenz: {opp['confidence']}")
        
        except Exception as e:
            print(f"❌ Scanner Fehler: {e}")
            #

    def indicator_comparison_analysis(self):
        """Vergleicht verschiedene Indikatoren für ein Symbol"""
        self.print_header("INDIKATOR-VERGLEICH")
    
        symbol = input("💱 Symbol für Vergleich: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
    
        print(f"\n🔄 Vergleiche Indikatoren für {symbol}...")
    
        try:
            # Basis-Indikatoren sammeln
            indicators_data = {}
        
            # RSI
            rsi_value = self.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, rsi_desc = self.get_rsi_signal(rsi_value)
                indicators_data['RSI'] = {
                    'signal': rsi_signal,
                    'value': rsi_value,
                    'description': rsi_desc,
                    'type': 'Momentum'
                }
        
            # MACD
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, macd_desc = self.get_macd_signal(macd_data)
                indicators_data['MACD'] = {
                    'signal': macd_signal,
                    'value': f"{macd_data['macd']:.6f}",
                    'description': macd_desc,
                    'type': 'Trend/Momentum'
                }
        
            # Support/Resistance
            sr_data = self.calculate_support_resistance(symbol)
            if sr_data:
                current_price = sr_data['current_price']
                sr_signal, sr_desc = self.get_sr_signal(sr_data, current_price)
                indicators_data['Support/Resistance'] = {
                    'signal': sr_signal,
                    'value': f"{current_price:.5f}",
                    'description': sr_desc,
                    'type': 'Price Action'
                }
        
            # Erweiterte Indikatoren hinzufügen
            if self.advanced_indicators:
                advanced_analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
            
                for indicator, data in advanced_analysis.items():
                    if 'signal' in data and 'description' in data:
                        indicator_name = indicator.replace('_', ' ').title()
                    
                        # Typ bestimmen
                        if indicator in ['williams_r', 'cci', 'awesome_oscillator']:
                            ind_type = 'Momentum'
                        elif indicator in ['ichimoku', 'adx']:
                            ind_type = 'Trend'
                        elif indicator in ['vwap', 'mfi']:
                            ind_type = 'Volume'
                        else:
                            ind_type = 'Other'
                    
                        indicators_data[indicator_name] = {
                            'signal': data['signal'],
                            'value': str(data.get('value', 'N/A')),
                            'description': data['description'],
                            'type': ind_type
                        }
        
            # Gruppiere nach Typ
            indicator_types = {}
            for name, data in indicators_data.items():
                indicator_type = data['type']
                if indicator_type not in indicator_types:
                    indicator_types[indicator_type] = []
                indicator_types[indicator_type].append((name, data))
        
            # Zeige Vergleich
            print(f"\n{'='*80}")
            print(f"📊 INDIKATOR-VERGLEICH: {symbol}")
            print(f"{'='*80}")
        
            for indicator_type, indicators in indicator_types.items():
                print(f"\n📈 {indicator_type.upper()}:")
                print("─" * 60)
                print(f"{'Indikator':<20} {'Signal':<12} {'Wert':<15} {'Beschreibung'}")
                print("─" * 60)
            
                for name, data in indicators:
                    signal = data['signal']
                    value = data['value']
                    description = data['description'][:30] + "..." if len(data['description']) > 30 else data['description']
                
                    signal_icon = "🟢" if signal in ['BUY', 'STRONG_BUY'] else \
                                 "🔴" if signal in ['SELL', 'STRONG_SELL'] else "🟡"
                
                    print(f"{name:<20} {signal_icon}{signal:<11} {value:<15} {description}")
        
            # Signal-Konsens Analyse
            print(f"\n🎯 SIGNAL-KONSENS ANALYSE:")
            print("─" * 40)
        
            signal_counts = {}
            for name, data in indicators_data.items():
                signal = data['signal']
                if signal not in signal_counts:
                    signal_counts[signal] = []
                signal_counts[signal].append(name)
        
            for signal, indicators in signal_counts.items():
                count = len(indicators)
                percentage = (count / len(indicators_data)) * 100
            
                signal_icon = "🟢" if signal in ['BUY', 'STRONG_BUY'] else \
                             "🔴" if signal in ['SELL', 'STRONG_SELL'] else "🟡"
            
                print(f"{signal_icon} {signal}: {count} Indikatoren ({percentage:.1f}%)")
                for indicator in indicators[:3]:  # Zeige max 3
                    print(f"   • {indicator}")
                if len(indicators) > 3:
                    print(f"   • ... und {len(indicators) - 3} weitere")
        
            # Konflikt-Analyse
            bullish_signals = signal_counts.get('BUY', []) + signal_counts.get('STRONG_BUY', [])
            bearish_signals = signal_counts.get('SELL', []) + signal_counts.get('STRONG_SELL', [])
            neutral_signals = signal_counts.get('NEUTRAL', [])
        
            print(f"\n⚖️ SIGNAL-VERTEILUNG:")
            print("─" * 30)
            print(f"🟢 Bullisch: {len(bullish_signals)} ({len(bullish_signals)/len(indicators_data)*100:.1f}%)")
            print(f"🔴 Bearisch: {len(bearish_signals)} ({len(bearish_signals)/len(indicators_data)*100:.1f}%)")
            print(f"🟡 Neutral: {len(neutral_signals)} ({len(neutral_signals)/len(indicators_data)*100:.1f}%)")
        
            # Empfehlung
            print(f"\n💡 VERGLEICHS-FAZIT:")
            print("─" * 25)
        
            if len(bullish_signals) >= len(indicators_data) * 0.6:
                print("🚀 STARKER BULLISCHER KONSENS")
                print("   Empfehlung: Kaufgelegenheit prüfen")
            elif len(bearish_signals) >= len(indicators_data) * 0.6:
                print("💥 STARKER BEARISCHER KONSENS")
                print("   Empfehlung: Verkaufsgelegenheit prüfen")
            elif len(bullish_signals) > len(bearish_signals):
                print("🟢 MODERATER BULLISCHER TREND")
                print("   Empfehlung: Vorsichtige Kaufposition möglich")
            elif len(bearish_signals) > len(bullish_signals):
                print("🔴 MODERATER BEARISCHER TREND")
                print("   Empfehlung: Vorsichtige Verkaufsposition möglich")
            else:
                print("🟡 GEMISCHTE SIGNALE")
                print("   Empfehlung: Abwarten oder weitere Bestätigung suchen")
        
            print(f"{'='*80}")
        
        except Exception as e:
            print(f"❌ Indikator-Vergleich Fehler: {e}")

    def indicator_testing_suite(self):
        """Test-Suite für Indikator-Optimierung"""
        self.print_header("INDIKATOR-TEST & OPTIMIERUNG")
    
        print("🧪 Indikator Test-Suite")
        print("─" * 30)
        print("1. Indikator-Performance Test")
        print("2. Parameter-Optimierung")
        print("3. Backtest-Simulation")
        print("4. Korrelations-Analyse")
        print("5. Zurück")
    
        choice = input("\n🎯 Test wählen (1-5): ").strip()
    
        if choice == "1":
            self.indicator_performance_test()
        elif choice == "2":
            self.parameter_optimization()
        elif choice == "3":
            self.backtest_simulation()
        elif choice == "4":
            self.correlation_analysis()
        elif choice == "5":
            return
        else:
            print("❌ Ungültige Auswahl")

    def indicator_performance_test(self):
        """Testet die Performance verschiedener Indikatoren"""
        symbol = input("💱 Symbol für Performance-Test: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
    
        print(f"\n🔄 Teste Indikator-Performance für {symbol}...")
    
        try:
            # Teste verschiedene Indikatoren
            indicators_tested = []
        
            # RSI Test
            rsi_start = time.time()
            rsi_value = self.calculate_rsi(symbol)
            rsi_time = time.time() - rsi_start
            if rsi_value:
                indicators_tested.append(('RSI', rsi_time, 'Erfolgreich'))
            else:
                indicators_tested.append(('RSI', rsi_time, 'Fehlgeschlagen'))
        
            # MACD Test
            macd_start = time.time()
            macd_data = self.calculate_macd(symbol)
            macd_time = time.time() - macd_start
            if macd_data:
                indicators_tested.append(('MACD', macd_time, 'Erfolgreich'))
            else:
                indicators_tested.append(('MACD', macd_time, 'Fehlgeschlagen'))
        
            # Erweiterte Indikatoren Test
            if self.advanced_indicators:
                adv_start = time.time()
                adv_analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
                adv_time = time.time() - adv_start
                if adv_analysis:
                    indicators_tested.append(('Erweiterte Indikatoren', adv_time, 'Erfolgreich'))
                else:
                    indicators_tested.append(('Erweiterte Indikatoren', adv_time, 'Fehlgeschlagen'))
        
            # Ergebnisse anzeigen
            print(f"\n📊 PERFORMANCE-TEST ERGEBNISSE:")
            print("─" * 50)
            print(f"{'Indikator':<25} {'Zeit (s)':<10} {'Status'}")
            print("─" * 50)
        
            for name, exec_time, status in indicators_tested:
                status_icon = "✅" if status == 'Erfolgreich' else "❌"
                print(f"{name:<25} {exec_time:<10.3f} {status_icon} {status}")
        
            total_time = sum(t[1] for t in indicators_tested)
            success_rate = len([t for t in indicators_tested if t[2] == 'Erfolgreich']) / len(indicators_tested) * 100
        
            print("─" * 50)
            print(f"Gesamtzeit: {total_time:.3f}s")
            print(f"Erfolgsrate: {success_rate:.1f}%")
        
        except Exception as e:
            print(f"❌ Performance-Test Fehler: {e}")

    def parameter_optimization(self):
        """Optimiert Parameter für Indikatoren"""
        print("\n⚙️ PARAMETER-OPTIMIERUNG")
        print("─" * 30)
        print("Verfügbare Optimierungen:")
        print("1. RSI Periode optimieren")
        print("2. MACD Parameter optimieren")
        print("3. Williams %R optimieren")
        print("4. Zurück")
    
        choice = input("\nOptimierung wählen (1-4): ").strip()
    
        if choice == "1":
            self.optimize_rsi_period()
        elif choice == "2":
            print("MACD Optimierung - In Entwicklung")
        elif choice == "3":
            print("Williams %R Optimierung - In Entwicklung")
        elif choice == "4":
            return
        else:
            print("❌ Ungültige Auswahl")

    def optimize_rsi_period(self):
        """Optimiert RSI-Periode"""
        symbol = input("Symbol für RSI-Optimierung: ").upper()
        if not symbol:
            return
    
        print(f"\n🔄 Optimiere RSI-Periode für {symbol}...")
    
        try:
            periods_to_test = [10, 12, 14, 16, 18, 20]
            results = []
        
            original_period = self.rsi_period
        
            for period in periods_to_test:
                self.rsi_period = period
                rsi_value = self.calculate_rsi(symbol)
                if rsi_value:
                    signal, desc = self.get_rsi_signal(rsi_value)
                    results.append((period, rsi_value, signal))
                    print(f"Periode {period}: RSI={rsi_value:.1f}, Signal={signal}")
        
            # Setze ursprüngliche Periode zurück
            self.rsi_period = original_period
        
            print(f"\n📊 RSI-OPTIMIERUNG ERGEBNISSE:")
            print("─" * 40)
            for period, rsi, signal in results:
                print(f"Periode {period:2d}: RSI={rsi:5.1f} - {signal}")
        
        except Exception as e:
            print(f"❌ RSI-Optimierung Fehler: {e}")

    def backtest_simulation(self):
        """Einfache Backtest-Simulation"""
        print("\n📈 BACKTEST-SIMULATION")
        print("─" * 25)
        print("Diese Funktion ist in Entwicklung.")
        print("Geplante Features:")
        print("• Historische Daten-Analyse")
        print("• Signal-Performance über Zeit")
        print("• Win/Loss Ratio Berechnung")
        print("• Profit Factor Analyse")

    def correlation_analysis(self):
        """Analysiert Korrelationen zwischen Indikatoren"""
        symbol = input("💱 Symbol für Korrelations-Analyse: ").upper()
        if not symbol:
            return
    
        print(f"\n🔄 Analysiere Indikator-Korrelationen für {symbol}...")
    
        try:
            # Sammle alle Indikator-Signale
            signals = {}
        
            # Basis-Indikatoren
            rsi_value = self.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, _ = self.get_rsi_signal(rsi_value)
                signals['RSI'] = 1 if rsi_signal == 'BUY' else -1 if rsi_signal == 'SELL' else 0
        
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, _ = self.get_macd_signal(macd_data)
                signals['MACD'] = 1 if macd_signal == 'BUY' else -1 if macd_signal == 'SELL' else 0
        
            # Erweiterte Indikatoren
            if self.advanced_indicators:
                advanced_analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
                for indicator, data in advanced_analysis.items():
                    if 'signal' in data:
                        signal = data['signal']
                        signals[indicator.upper()] = 1 if signal in ['BUY', 'STRONG_BUY'] else -1 if signal in ['SELL', 'STRONG_SELL'] else 0
        
            # Zeige Korrelation
            print(f"\n📊 INDIKATOR-KORRELATIONS-MATRIX:")
            print("─" * 50)
        
            indicator_names = list(signals.keys())
            for i, ind1 in enumerate(indicator_names):
                for j, ind2 in enumerate(indicator_names):
                    if i <= j:
                        if i == j:
                            correlation = 1.0
                        else:
                            # Einfache Korrelation (gleiche Richtung = positive Korrelation)
                            sig1, sig2 = signals[ind1], signals[ind2]
                            if sig1 == sig2:
                                correlation = 1.0 if sig1 != 0 else 0.0
                            elif sig1 == -sig2:
                                correlation = -1.0
                            else:
                                correlation = 0.0
                    
                        print(f"{ind1} <-> {ind2}: {correlation:+.2f}")
        
            # Konsens-Bewertung
            bullish_count = sum(1 for sig in signals.values() if sig > 0)
            bearish_count = sum(1 for sig in signals.values() if sig < 0)
            neutral_count = sum(1 for sig in signals.values() if sig == 0)
        
            print(f"\n🎯 SIGNAL-KONSENS:")
            print("─" * 20)
            print(f"Bullisch: {bullish_count}")
            print(f"Bearisch: {bearish_count}")
            print(f"Neutral: {neutral_count}")
        
            if bullish_count > bearish_count + neutral_count:
                print("📈 Starker bullischer Konsens")
            elif bearish_count > bullish_count + neutral_count:
                print("📉 Starker bearischer Konsens")
            else:
                print("🟡 Gemischte Signale")
        
        except Exception as e:
            print(f"❌ Korrelations-Analyse Fehler: {e}")

    def rl_menu_enhanced(self):
        """Erweiterte RL Menü mit Smart Training"""
    
        while True:
            self.print_header("REINFORCEMENT LEARNING")
        
            # Auto-Detection
            auto_symbols = self.auto_detect_trading_symbols()
            untrained_count = sum(1 for s in auto_symbols if s not in self.rl_manager.agents or 
                                 getattr(self.rl_manager.agents.get(s, None), 'training_step', 0) < 400)
        
            print("🤖 RL STATUS:")
            print("─" * 20)
            if self.rl_manager:
                print(f"✅ RL Manager aktiv")
                print(f"📊 Trainierte Agents: {len(self.rl_manager.agents)}")
                print(f"🎯 Training Modus: {'✅' if self.rl_training_mode else '❌'}")
                print(f"💱 Auto-Trading Symbole: {', '.join(auto_symbols[:3])}")
                if len(auto_symbols) > 3:
                    print(f"                        + {len(auto_symbols)-3} weitere")
                print(f"🎯 Benötigt Training: {untrained_count}")
            
                # Agent Status
                for symbol, agent in self.rl_manager.agents.items():
                    training_steps = getattr(agent, 'training_step', 0)
                    epsilon = getattr(agent, 'epsilon', 1.0)
                    status = "✅" if training_steps >= 400 and epsilon < 0.1 else "🔄"
                    print(f"   {status} {symbol}: {training_steps} Steps, ε={epsilon:.3f}")
            else:
                print("❌ RL Manager nicht verfügbar")
        
            print(f"\n📋 SMART TRAINING:")
            print("─" * 20)
        
            if untrained_count > 0:
                print(f" 🚀 ALLE {untrained_count} FEHLENDEN AGENTS TRAINIEREN")
                print(f"    💱 Symbole: {', '.join([s for s in auto_symbols if s not in self.rl_manager.agents or getattr(self.rl_manager.agents.get(s, None), 'training_step', 0) < 400])}")
            else:
                print(f" ✅ ALLE AUTO-TRADING AGENTS SIND BEREIT")
        
            print(f"\n📋 STANDARD OPTIONEN:")
            print("─" * 20)
            print(" 1. 🚀 Smart Agent Training (Auto-Detect)")
            print(" 2. 🧠 RL-Empfehlung testen")
            print(" 3. 📊 Training-Statistiken")
            print(" 4. 💾 Modell speichern/laden")
            print(" 5. ⚙️ RL-Einstellungen")
            print(" 6. 🔄 RL Auto-Trading aktivieren")
            print(" 7. 📈 Performance Vergleich")
            print(" 8. 🎯 Batch Training für alle Symbole")
            print(" 9. ⬅️ Zurück")
        
            if untrained_count > 0:
                print(f"\n💡 QUICK ACTION:")
                print(f"Drücken Sie 'Q' für schnelles Training aller {untrained_count} fehlenden Agents!")
        
            choice = input(f"\n🎯 Ihre Wahl (1-9{', Q' if untrained_count > 0 else ''}): ").strip().upper()
        
            if choice == "Q" and untrained_count > 0:
                # Quick Training
                untrained_symbols = [s for s in auto_symbols if s not in self.rl_manager.agents or 
                                   getattr(self.rl_manager.agents.get(s, None), 'training_step', 0) < 400]
            
                print(f"\n⚡ QUICK TRAINING")
                print(f"Symbole: {', '.join(untrained_symbols)}")
            
                confirm = input("Alle fehlenden Agents trainieren? (ja/nein): ").lower()
                if confirm == "ja":
                    self.batch_train_sequential(untrained_symbols, 300)  # 300 Episodes default
        
            elif choice == "1":
                self.train_rl_agent_enhanced()
            elif choice == "2":
                self.test_rl_recommendation()
            elif choice == "3":
                self.show_rl_statistics()
            elif choice == "4":
                self.manage_rl_models()
            elif choice == "5":
                self.rl_settings()
            elif choice == "6":
                self.toggle_rl_auto_trading()
            elif choice == "7":
                self.compare_rl_performance()
            elif choice == "8":
                # Batch Training für ALLE
                print(f"\n🔄 BATCH TRAINING FÜR ALLE SYMBOLE")
                print(f"Auto-Trading Symbole: {', '.join(auto_symbols)}")
            
                episodes = int(input("Episodes pro Symbol (Enter für 250): ") or "250")
                mode = input("Modus (sequential/parallel, Enter für sequential): ").lower() or "sequential"
            
                if mode == "parallel":
                    self.batch_train_parallel(auto_symbols, episodes)
                else:
                    self.batch_train_sequential(auto_symbols, episodes)
                
            elif choice == "9":
                break
            else:
                print("❌ Ungültige Auswahl")
        
            input("\nDrücken Sie Enter zum Fortfahren...")

    def train_rl_agent_enhanced(self):
        """Erweiterte RL Agent Training mit automatischer Symbol-Auswahl"""
    
        print("\n🚀 RL AGENT TRAINING")
        print("─" * 25)
    
        # AUTO-SYMBOL DETECTION
        available_symbols = []
    
        # 1. Nutze aktuelle Auto-Trading Symbole
        if hasattr(self, 'auto_trade_symbols') and self.auto_trade_symbols:
            available_symbols.extend(self.auto_trade_symbols)
            print(f"📊 Auto-Trading Symbole gefunden: {', '.join(self.auto_trade_symbols)}")
    
        # 2. Ergänze um Standard-Majors falls leer
        if not available_symbols:
            available_symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]
            print(f"📊 Standard Majors werden verwendet: {', '.join(available_symbols)}")
    
        # 3. Filtere bereits trainierte Agents
        untrained_symbols = []
        trained_symbols = []
    
        for symbol in available_symbols:
            if symbol in self.rl_manager.agents:
                agent = self.rl_manager.agents[symbol]
                training_steps = getattr(agent, 'training_step', 0)
                epsilon = getattr(agent, 'epsilon', 1.0)
            
                if training_steps < 400 or epsilon > 0.1:  # Noch nicht gut trainiert
                    untrained_symbols.append(symbol)
                else:
                    trained_symbols.append(symbol)
            else:
                untrained_symbols.append(symbol)
    
        print(f"\n📈 TRAINING STATUS:")
        if trained_symbols:
            print(f"✅ Gut trainiert: {', '.join(trained_symbols)}")
        if untrained_symbols:
            print(f"🎯 Benötigt Training: {', '.join(untrained_symbols)}")
    
        # AUSWAHL-OPTIONEN
        print(f"\n📋 TRAINING OPTIONEN:")
        print("─" * 25)
        print("1. 🤖 Alle untrainierten Symbole automatisch trainieren")
        print("2. 🎯 Spezifisches Symbol wählen")
        print("3. 📊 Nur die besten 3 Symbole trainieren")
        print("4. 🔄 Alle neu trainieren (überschreiben)")
        print("5. ⬅️ Zurück")
    
        choice = input("\nWählen (1-5): ").strip()
    
        if choice == "1":
            # Automatisches Training aller untrainierten
            if not untrained_symbols:
                print("✅ Alle Symbole sind bereits gut trainiert!")
                return
        
            print(f"\n🚀 BATCH TRAINING")
            print(f"Symbole: {', '.join(untrained_symbols)}")
        
            episodes = int(input("Episodes pro Symbol (Enter für 300): ") or "300")
            parallel = input("Parallel trainieren? (ja/nein): ").lower() == "ja"
        
            if parallel:
                self.batch_train_parallel(untrained_symbols, episodes)
            else:
                self.batch_train_sequential(untrained_symbols, episodes)
    
        elif choice == "2":
            # Manuelle Symbol-Auswahl mit Auto-Complete
            print(f"\n💱 VERFÜGBARE SYMBOLE:")
            for i, symbol in enumerate(available_symbols, 1):
                status = "✅" if symbol in trained_symbols else "🎯"
                agent_info = ""
                if symbol in self.rl_manager.agents:
                    agent = self.rl_manager.agents[symbol]
                    steps = getattr(agent, 'training_step', 0)
                    epsilon = getattr(agent, 'epsilon', 1.0)
                    agent_info = f"(Steps: {steps}, ε: {epsilon:.3f})"
            
                print(f"   {i}. {status} {symbol} {agent_info}")
        
            print("   0. ✍️ Manuell eingeben")
        
            try:
                symbol_choice = input(f"\nSymbol wählen (0-{len(available_symbols)}): ").strip()
            
                if symbol_choice == "0":
                    symbol = input("Symbol eingeben: ").upper().strip()
                else:
                    symbol_idx = int(symbol_choice) - 1
                    if 0 <= symbol_idx < len(available_symbols):
                        symbol = available_symbols[symbol_idx]
                    else:
                        print("❌ Ungültige Auswahl")
                        return
            
                if symbol:
                    episodes = int(input("Anzahl Episodes (Enter für 500): ") or "500")
                    self.train_single_agent(symbol, episodes)
                
            except ValueError:
                print("❌ Ungültige Eingabe")
    
        elif choice == "3":
            # Top 3 Symbole automatisch
            top_symbols = ["EURUSD", "GBPUSD", "USDJPY"]
            top_untrained = [s for s in top_symbols if s in untrained_symbols]
        
            if top_untrained:
                print(f"\n🏆 TOP 3 TRAINING: {', '.join(top_untrained)}")
                episodes = int(input("Episodes pro Symbol (Enter für 400): ") or "400")
                self.batch_train_sequential(top_untrained, episodes)
            else:
                print("✅ Top 3 Symbole sind bereits trainiert!")
    
        elif choice == "4":
            # Alle neu trainieren
            confirm = input(f"\n⚠️ ALLE {len(available_symbols)} Symbole neu trainieren? (JA/nein): ")
            if confirm == "JA":
                episodes = int(input("Episodes pro Symbol (Enter für 200): ") or "200")
                self.batch_train_sequential(available_symbols, episodes)
    
        elif choice == "5":
            return
    
    def batch_train_sequential(self, symbols, episodes):
        """Trainiert mehrere Symbole nacheinander"""
    
        print(f"\n🔄 SEQUENZIELLES BATCH TRAINING")
        print(f"Symbole: {len(symbols)} | Episodes: {episodes} pro Symbol")
        print(f"Geschätzte Gesamtdauer: {len(symbols) * episodes // 50} Minuten")
    
        confirm = input("\nStarten? (ja/nein): ").lower()
        if confirm != "ja":
            return
    
        def batch_worker():
            try:
                for i, symbol in enumerate(symbols, 1):
                    print(f"\n🎯 [{i}/{len(symbols)}] Training {symbol}...")
                    success = self.rl_manager.train_agent(symbol, episodes)
                
                    if success:
                        # Automatisch speichern
                        model_path = f"{self.rl_manager.model_directory}/{symbol}_batch_{episodes}.h5"
                        self.rl_manager.agents[symbol].save_model(model_path)
                        print(f"✅ {symbol} abgeschlossen und gespeichert")
                    else:
                        print(f"❌ {symbol} fehlgeschlagen")
                
                    # Kurze Pause zwischen Trainings
                    if i < len(symbols):
                        print("⏸️ Kurze Pause...")
                        time.sleep(2)
            
                print(f"\n🎉 BATCH TRAINING ABGESCHLOSSEN!")
                print(f"✅ {len(symbols)} Symbole trainiert")
            
            except Exception as e:
                print(f"💥 Batch Training Fehler: {e}")
    
        # Training in separatem Thread
        training_thread = threading.Thread(target=batch_worker, daemon=True)
        training_thread.start()
    
        print("🔄 Batch Training läuft im Hintergrund...")
        print("💡 Sie können andere Menüs verwenden")

    def batch_train_parallel(self, symbols, episodes):
        """Trainiert mehrere Symbole parallel (experimentell)"""
    
        print(f"\n⚡ PARALLELES TRAINING (EXPERIMENTELL)")
        print(f"⚠️ Warnung: Sehr ressourcenintensiv!")
    
        max_parallel = min(3, len(symbols))  # Maximal 3 parallel
        print(f"📊 Parallel: {max_parallel} Symbole gleichzeitig")
    
        confirm = input("Wirklich parallel trainieren? (ja/nein): ").lower()
        if confirm != "ja":
            self.batch_train_sequential(symbols, episodes)
            return
    
        import concurrent.futures
    
        def train_worker(symbol):
            try:
                return self.rl_manager.train_agent(symbol, episodes)
            except Exception as e:
                print(f"❌ {symbol} Parallel-Training Fehler: {e}")
                return False
    
        def parallel_worker():
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
                    # Starte alle Trainings
                    futures = {executor.submit(train_worker, symbol): symbol for symbol in symbols}
                
                    # Warte auf Ergebnisse
                    for future in concurrent.futures.as_completed(futures):
                        symbol = futures[future]
                        try:
                            success = future.result()
                            if success:
                                print(f"✅ {symbol} parallel Training abgeschlossen")
                            else:
                                print(f"❌ {symbol} parallel Training fehlgeschlagen")
                        except Exception as e:
                            print(f"❌ {symbol} parallel Fehler: {e}")
            
                print(f"🎉 PARALLEL TRAINING ABGESCHLOSSEN!")
            
            except Exception as e:
                print(f"💥 Parallel Training Fehler: {e}")
    
        # Parallel Training starten
        parallel_thread = threading.Thread(target=parallel_worker, daemon=True)
        parallel_thread.start()
    
        print("⚡ Parallel Training läuft im Hintergrund...")

    def train_single_agent(self, symbol, episodes):
        """Trainiert einen einzelnen Agent mit verbesserter UI"""
    
        print(f"\n🎯 EINZELTRAINING: {symbol}")
        print("─" * 30)
    
        # Status-Check
        if symbol in self.rl_manager.agents:
            agent = self.rl_manager.agents[symbol]
            current_steps = getattr(agent, 'training_step', 0)
            current_epsilon = getattr(agent, 'epsilon', 1.0)
        
            print(f"📊 Aktueller Status:")
            print(f"   Steps: {current_steps}")
            print(f"   Epsilon: {current_epsilon:.3f}")
        
            if current_steps > 400 and current_epsilon < 0.1:
                override = input("⚠️ Agent bereits gut trainiert. Überschreiben? (ja/nein): ").lower()
                if override != "ja":
                    return
    
        print(f"📊 Training Setup:")
        print(f"   Symbol: {symbol}")
        print(f"   Episodes: {episodes}")
        print(f"   Geschätzte Dauer: {episodes//50} Minuten")
    
        confirm = input("\nTraining starten? (ja/nein): ").lower()
        if confirm != "ja":
            return
    
        # Training mit Progress
        def training_worker():
            try:
                print(f"🤖 Starte Training für {symbol}...")
                success = self.rl_manager.train_agent(symbol, episodes)
            
                if success:
                    print(f"✅ Training für {symbol} erfolgreich!")
                
                    # Auto-Save mit Timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                    model_path = f"{self.rl_manager.model_directory}/{symbol}_{timestamp}.h5"
                    self.rl_manager.agents[symbol].save_model(model_path)
                    print(f"💾 Modell gespeichert: {model_path}")
                else:
                    print(f"❌ Training für {symbol} fehlgeschlagen")
                
            except Exception as e:
                print(f"💥 Training Fehler: {e}")
    
        # Training starten
        training_thread = threading.Thread(target=training_worker, daemon=True)
        training_thread.start()
    
        print("🔄 Training läuft im Hintergrund...")

    def auto_detect_trading_symbols(self):
        """Automatische Erkennung der zu trainierenden Symbole"""
    
        symbols = set()
    
        # 1. Auto-Trading Symbole
        if hasattr(self, 'auto_trade_symbols') and self.auto_trade_symbols:
            symbols.update(self.auto_trade_symbols)
    
        # 2. Favoriten
        if hasattr(self, 'custom_pairs') and 'user_favorites' in self.custom_pairs:
            symbols.update(self.custom_pairs['user_favorites']['pairs'])
    
        # 3. Aktuelle offene Positionen
        if self.mt5_connected:
            try:
                positions = mt5.positions_get()
                if positions:
                    for pos in positions:
                        symbols.add(pos.symbol)
            except:
                pass
    
        # 4. Standard-Fallback
        if not symbols:
            symbols = {"EURUSD", "GBPUSD", "USDJPY"}
    
        return sorted(list(symbols))

    def test_rl_recommendation(self):
        """Testet RL-Empfehlung für Symbol"""
    
        print("\n🧠 RL EMPFEHLUNG TESTEN")
        print("─" * 25)
    
        if not self.rl_manager.agents:
            print("❌ Keine trainierten Agents verfügbar")
            print("💡 Trainieren Sie zuerst einen Agent (Option 1)")
            return
    
        # Verfügbare Agents anzeigen
        print("📊 Verfügbare Agents:")
        for i, symbol in enumerate(self.rl_manager.agents.keys(), 1):
            agent = self.rl_manager.agents[symbol]
            steps = getattr(agent, 'training_step', 0)
            print(f"   {i}. {symbol} ({steps} Trainingssteps)")
    
        # Symbol auswählen
        symbol = input("\nSymbol für Test: ").upper().strip()
        if symbol not in self.rl_manager.agents:
            print(f"❌ Kein trainierter Agent für {symbol}")
            return
    
        try:
            print(f"🔍 Hole RL-Empfehlung für {symbol}...")
        
            # RL Empfehlung
            rl_result = self.rl_manager.get_rl_recommendation(symbol)
        
            if rl_result:
                print(f"\n🤖 RL EMPFEHLUNG:")
                print("─" * 20)
                print(f"📊 Aktion: {rl_result['recommendation']}")
                print(f"🎯 Konfidenz: {rl_result['confidence']:.1f}%")
                print(f"💡 Begründung: {rl_result['reasoning']}")
            
                if rl_result['q_values']:
                    print(f"\n📈 Q-Values:")
                    actions = ['HOLD', 'BUY', 'SELL']
                    for i, (action, q_val) in enumerate(zip(actions, rl_result['q_values'])):
                        print(f"   {action}: {q_val:.4f}")
            
                # Vergleiche mit traditionellen Indikatoren
                print(f"\n📊 VERGLEICH MIT TRADITIONELLEN INDIKATOREN:")
                print("─" * 45)
            
                # RSI
                rsi = self.calculate_rsi(symbol)
                if rsi:
                    rsi_signal, rsi_desc = self.get_rsi_signal(rsi)
                    print(f"📈 RSI: {rsi_signal} ({rsi_desc})")
            
                # MACD
                macd_data = self.calculate_macd(symbol)
                if macd_data:
                    macd_signal, macd_desc = self.get_macd_signal(macd_data)
                    print(f"📊 MACD: {macd_signal} ({macd_desc[:30]}...)")
            
                # Consensus
                signals = []
                if rsi and rsi_signal in ['BUY', 'SELL']:
                    signals.append(rsi_signal)
                if macd_data and macd_signal in ['BUY', 'SELL']:
                    signals.append(macd_signal)
            
                rl_signal = rl_result['recommendation']
                signals.append(rl_signal)
            
                buy_count = signals.count('BUY')
                sell_count = signals.count('SELL')
            
                print(f"\n🎯 CONSENSUS:")
                print(f"   BUY Signale: {buy_count}")
                print(f"   SELL Signale: {sell_count}")
                print(f"   RL Gewichtung: {self.rl_recommendation_weight}")
            
                if buy_count > sell_count:
                    consensus = "BUY"
                elif sell_count > buy_count:
                    consensus = "SELL"
                else:
                    consensus = "NEUTRAL"
            
                print(f"   Consensus: {consensus}")
            
            else:
                print("❌ RL-Empfehlung konnte nicht abgerufen werden")
            
        except Exception as e:
            print(f"❌ Fehler beim Testen: {e}")

    def show_rl_statistics(self):
        """Zeigt RL Training-Statistiken"""
    
        print("\n📊 RL TRAINING-STATISTIKEN")
        print("─" * 30)
    
        if not self.rl_manager.training_stats:
            print("❌ Keine Statistiken verfügbar")
            print("💡 Trainieren Sie zuerst einen Agent")
            return
    
        for symbol, stats in self.rl_manager.training_stats.items():
            print(f"\n🎯 {symbol}:")
            print(f"   Episodes: {stats['episodes']}")
            print(f"   Finaler Reward: {stats['final_reward']:.2f}")
            print(f"   Durchschnitt: {stats['avg_reward']:.2f}")
            print(f"   Bester Reward: {stats['best_reward']:.2f}")
        
            # Agent Info
            if symbol in self.rl_manager.agents:
                agent = self.rl_manager.agents[symbol]
                print(f"   Training Steps: {getattr(agent, 'training_step', 0)}")
                print(f"   Epsilon: {getattr(agent, 'epsilon', 0):.4f}")
                print(f"   Memory Size: {len(getattr(agent, 'memory', []))}")

    def manage_rl_models(self):
        """Verwaltet RL Modelle (Speichern/Laden)"""
    
        print("\n💾 RL MODELL-VERWALTUNG")
        print("─" * 25)
    
        print("1. 💾 Modell speichern")
        print("2. 📁 Modell laden")
        print("3. 📂 Verfügbare Modelle anzeigen")
        print("4. 🗑️ Modell löschen")
    
        choice = input("\nWählen (1-4): ").strip()
    
        if choice == "1":
            # Modell speichern
            if not self.rl_manager.agents:
                print("❌ Keine Agents zum Speichern")
                return
        
            print("\n📊 Verfügbare Agents:")
            for symbol in self.rl_manager.agents.keys():
                print(f"   - {symbol}")
        
            symbol = input("Symbol zum Speichern: ").upper().strip()
            if symbol in self.rl_manager.agents:
                filename = input(f"Dateiname (Enter für {symbol}_manual.h5): ").strip()
                if not filename:
                    filename = f"{symbol}_manual.h5"
            
                if not filename.endswith('.h5'):
                    filename += '.h5'
            
                filepath = f"{self.rl_manager.model_directory}/{filename}"
                self.rl_manager.agents[symbol].save_model(filepath)
                print(f"✅ Modell gespeichert: {filepath}")
            else:
                print(f"❌ Kein Agent für {symbol}")
    
        elif choice == "2":
            # Modell laden
            import os
            models_dir = self.rl_manager.model_directory
        
            if not os.path.exists(models_dir):
                print(f"❌ Model Directory nicht gefunden: {models_dir}")
                return
        
            # Verfügbare Modelle anzeigen
            model_files = [f for f in os.listdir(models_dir) if f.endswith('.h5')]
        
            if not model_files:
                print("❌ Keine gespeicherten Modelle gefunden")
                return
        
            print("\n📁 Verfügbare Modelle:")
            for i, model_file in enumerate(model_files, 1):
                print(f"   {i}. {model_file}")
        
            try:
                model_choice = int(input(f"\nModell wählen (1-{len(model_files)}): ")) - 1
                if 0 <= model_choice < len(model_files):
                    selected_model = model_files[model_choice]
                    filepath = os.path.join(models_dir, selected_model)
                
                    # Symbol extrahieren
                    symbol = selected_model.split('_')[0].upper()
                
                    # Agent erstellen wenn nicht vorhanden
                    if symbol not in self.rl_manager.agents:
                        success = self.rl_manager.initialize_agent(symbol)
                        if not success:
                            print(f"❌ Agent Initialisierung für {symbol} fehlgeschlagen")
                            return
                
                    # Modell laden
                    success = self.rl_manager.agents[symbol].load_model(filepath)
                    if success:
                        print(f"✅ Modell geladen für {symbol}")
                    else:
                        print(f"❌ Fehler beim Laden des Modells")
                else:
                    print("❌ Ungültige Auswahl")
            except ValueError:
                print("❌ Ungültige Eingabe")
    
        elif choice == "3":
            # Verfügbare Modelle anzeigen
            import os
            models_dir = self.rl_manager.model_directory
        
            if os.path.exists(models_dir):
                model_files = [f for f in os.listdir(models_dir) if f.endswith('.h5')]
            
                if model_files:
                    print(f"\n📂 Modelle in {models_dir}:")
                    for model_file in model_files:
                        filepath = os.path.join(models_dir, model_file)
                        size = os.path.getsize(filepath) / 1024  # KB
                        modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                        print(f"   📄 {model_file} ({size:.1f} KB, {modified.strftime('%d.%m.%Y %H:%M')})")
                else:
                    print("❌ Keine Modelle gefunden")
            else:
                print(f"❌ Model Directory nicht gefunden: {models_dir}")

    def rl_settings(self):
        """RL Einstellungen verwalten"""
    
        print("\n⚙️ RL EINSTELLUNGEN")
        print("─" * 20)
    
        print(f"Aktuelle Einstellungen:")
        print(f"   🎯 RL Empfehlungsgewicht: {self.rl_recommendation_weight}")
        print(f"   📊 Training Episodes: {self.rl_manager.training_episodes}")
        print(f"   💾 Save Frequency: {self.rl_manager.model_save_frequency}")
    
        print(f"\nOptionen:")
        print("1. 🎯 Empfehlungsgewicht ändern")
        print("2. 📊 Training-Parameter anpassen")
        print("3. 🔄 Zurück")
    
        choice = input("\nWählen (1-3): ").strip()
    
        if choice == "1":
            try:
                new_weight = float(input(f"Neues Gewicht (0.0-1.0, aktuell {self.rl_recommendation_weight}): "))
                if 0.0 <= new_weight <= 1.0:
                    old_weight = self.rl_recommendation_weight
                    self.rl_recommendation_weight = new_weight
                    print(f"✅ Gewicht geändert: {old_weight} -> {new_weight}")
                else:
                    print("❌ Gewicht muss zwischen 0.0 und 1.0 liegen")
            except ValueError:
                print("❌ Ungültige Eingabe")
    
        elif choice == "2":
            try:
                print(f"\nTraining-Parameter:")
            
                new_episodes = int(input(f"Episodes (aktuell {self.rl_manager.training_episodes}): ") or str(self.rl_manager.training_episodes))
                if 100 <= new_episodes <= 10000:
                    self.rl_manager.training_episodes = new_episodes
                    print(f"✅ Training Episodes: {new_episodes}")
            
                new_save_freq = int(input(f"Save Frequency (aktuell {self.rl_manager.model_save_frequency}): ") or str(self.rl_manager.model_save_frequency))
                if 10 <= new_save_freq <= 1000:
                    self.rl_manager.model_save_frequency = new_save_freq
                    print(f"✅ Save Frequency: {new_save_freq}")
                
            except ValueError:
                print("❌ Ungültige Eingabe")

    def toggle_rl_auto_trading(self):
        """Aktiviert/Deaktiviert RL Auto-Trading"""
    
        print("\n🔄 RL AUTO-TRADING")
        print("─" * 20)
    
        if not self.rl_manager.agents:
            print("❌ Keine trainierten Agents verfügbar")
            print("💡 Trainieren Sie zuerst einen Agent")
            return
    
        # Status anzeigen
        print(f"Status: {'✅ Aktiviert' if self.rl_training_mode else '❌ Deaktiviert'}")
        print(f"Verfügbare Agents: {list(self.rl_manager.agents.keys())}")
    
        if self.rl_training_mode:
            choice = input("RL Auto-Trading deaktivieren? (ja/nein): ").lower()
            if choice == "ja":
                self.rl_training_mode = False
                print("✅ RL Auto-Trading deaktiviert")
        else:
            choice = input("RL Auto-Trading aktivieren? (ja/nein): ").lower()
            if choice == "ja":
                self.rl_training_mode = True
                print("✅ RL Auto-Trading aktiviert")
                print("💡 RL-Empfehlungen werden nun in Auto-Trading berücksichtigt")

    def compare_rl_performance(self):
        """Vergleicht RL Performance mit traditionellen Methoden"""
    
        print("\n📈 PERFORMANCE VERGLEICH")
        print("─" * 30)
    
        if not self.rl_manager.agents:
            print("❌ Keine trainierten Agents für Vergleich")
            return
    
        symbol = input("Symbol für Vergleich: ").upper().strip()
        if symbol not in self.rl_manager.agents:
            print(f"❌ Kein RL Agent für {symbol}")
            return
    
        try:
            print(f"\n🔍 Vergleiche Methoden für {symbol}...")
        
            # RL Empfehlung
            rl_result = self.rl_manager.get_rl_recommendation(symbol)
        
            # Traditionelle Indikatoren
            rsi = self.calculate_rsi(symbol)
            macd_data = self.calculate_macd(symbol)
            sr_data = self.calculate_support_resistance(symbol)
        
            print(f"\n📊 SIGNALE VERGLEICH:")
            print("─" * 25)
        
            # RL
            if rl_result:
                print(f"🤖 RL Agent: {rl_result['recommendation']} (Konfidenz: {rl_result['confidence']:.1f}%)")
        
            # RSI
            if rsi:
                rsi_signal, rsi_desc = self.get_rsi_signal(rsi)
                print(f"📈 RSI: {rsi_signal} ({rsi})")
        
            # MACD
            if macd_data:
                macd_signal, macd_desc = self.get_macd_signal(macd_data)
                print(f"📊 MACD: {macd_signal}")
        
            # Support/Resistance
            if sr_data:
                current_price = sr_data['current_price']
                sr_signal, sr_desc = self.get_sr_signal(sr_data, current_price)
                print(f"🎯 S/R: {sr_signal}")
        
            # Consensus Berechnung
            signals = []
            if rl_result:
                signals.append(('RL', rl_result['recommendation'], self.rl_recommendation_weight))
            if rsi:
                rsi_signal, _ = self.get_rsi_signal(rsi)
                signals.append(('RSI', rsi_signal, 0.2))
            if macd_data:
                macd_signal, _ = self.get_macd_signal(macd_data)
                signals.append(('MACD', macd_signal, 0.3))
            if sr_data:
                sr_signal, _ = self.get_sr_signal(sr_data, current_price)
                signals.append(('S/R', sr_signal, 0.2))
        
            # Gewichteter Consensus
            buy_weight = sum(weight for method, signal, weight in signals if signal == 'BUY')
            sell_weight = sum(weight for method, signal, weight in signals if signal == 'SELL')
        
            print(f"\n🎯 GEWICHTETER CONSENSUS:")
            print(f"   BUY Gewicht: {buy_weight:.2f}")
            print(f"   SELL Gewicht: {sell_weight:.2f}")
        
            if buy_weight > sell_weight:
                final_recommendation = "BUY"
                confidence = buy_weight / (buy_weight + sell_weight) * 100
            elif sell_weight > buy_weight:
                final_recommendation = "SELL" 
                confidence = sell_weight / (buy_weight + sell_weight) * 100
            else:
                final_recommendation = "NEUTRAL"
                confidence = 50
        
            print(f"   Final: {final_recommendation} (Konfidenz: {confidence:.1f}%)")
        
            # RL Vorteil hervorheben
            print(f"\n🤖 RL VORTEILE:")
            print("   • Lernt aus historischen Mustern")
            print("   • Berücksichtigt komplexe Interaktionen")
            print("   • Passt sich an Marktveränderungen an")
            print("   • Optimiert für maximale Profitabilität")
        
        except Exception as e:
            print(f"❌ Vergleich Fehler: {e}")

    def show_individual_advanced_indicators(self):
        """Zeigt einzelne erweiterte Indikatoren zur Auswahl"""
        while True:
            self.print_header("EINZELNE ERWEITERTE INDIKATOREN")
        
            print("📊 Verfügbare Indikatoren:")
            print("─" * 35)
        
            indicator_menu = [
                ("1", "📈", "Williams %R"),
                ("2", "📊", "Commodity Channel Index (CCI)"),
                ("3", "🌊", "Awesome Oscillator"),
                ("4", "☁️", "Ichimoku Cloud"),
                ("5", "📊", "VWAP (Volume Weighted Average Price)"),
                ("6", "💰", "Money Flow Index (MFI)"),
                ("7", "📈", "Average Directional Index (ADX)"),
                ("8", "📊", "Alle Indikatoren anzeigen"),
                ("9", "⬅️", "Zurück")
            ]
        
            for num, icon, desc in indicator_menu:
                print(f" {num}. {icon} {desc}")
        
            print("─" * 35)
        
            choice = input("🎯 Indikator wählen (1-9): ").strip()
        
            if choice == "9":
                break
            elif choice in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                symbol = input("💱 Symbol eingeben: ").upper()
                if symbol:
                    self.display_selected_indicator(choice, symbol)
            else:
                print("❌ Ungültige Auswahl")
        
            input("\nDrücken Sie Enter zum Fortfahren...")

    def display_selected_indicator(self, indicator_choice, symbol):
        """Zeigt einen spezifischen Indikator an"""
        if not self.advanced_indicators:
            print("❌ Erweiterte Indikatoren nicht verfügbar")
            return
    
        try:
            print(f"\n📊 Berechne Indikator für {symbol}...")
        
            if indicator_choice == "1":
                # Williams %R
                wr_data = self.advanced_indicators.calculate_williams_r(symbol)
                if wr_data:
                    print(f"\n📈 WILLIAMS %R ANALYSE:")
                    print(f"Wert: {wr_data['value']}%")
                    print(f"Signal: {wr_data['signal']}")
                    print(f"Beschreibung: {wr_data['description']}")
                    print(f"Überkauft Level: {wr_data['overbought_level']}")
                    print(f"Überverkauft Level: {wr_data['oversold_level']}")
        
            elif indicator_choice == "2":
                # CCI
                cci_data = self.advanced_indicators.calculate_cci(symbol)
                if cci_data:
                    print(f"\n📊 COMMODITY CHANNEL INDEX:")
                    print(f"Wert: {cci_data['value']}")
                    print(f"Signal: {cci_data['signal']}")
                    print(f"Beschreibung: {cci_data['description']}")
        
            elif indicator_choice == "3":
                # Awesome Oscillator
                ao_data = self.advanced_indicators.calculate_awesome_oscillator(symbol)
                if ao_data:
                    print(f"\n🌊 AWESOME OSCILLATOR:")
                    print(f"Wert: {ao_data['value']}")
                    print(f"Signal: {ao_data['signal']}")
                    print(f"Beschreibung: {ao_data['description']}")
                    print(f"Über Nulllinie: {ao_data['above_zero']}")
                    print(f"Momentum: {ao_data['momentum']}")
        
            elif indicator_choice == "4":
                # Ichimoku
                ichimoku_data = self.advanced_indicators.calculate_ichimoku(symbol)
                if ichimoku_data:
                    print(f"\n☁️ ICHIMOKU CLOUD ANALYSE:")
                    print(f"Tenkan-sen: {ichimoku_data['tenkan_sen']}")
                    print(f"Kijun-sen: {ichimoku_data['kijun_sen']}")
                    print(f"Cloud Top: {ichimoku_data['cloud_top']}")
                    print(f"Cloud Bottom: {ichimoku_data['cloud_bottom']}")
                    print(f"Preis vs Cloud: {ichimoku_data['price_vs_cloud']}")
                    print(f"Cloud Signal: {ichimoku_data['cloud_signal']}")
                    print(f"TK Signal: {ichimoku_data['tk_signal']}")
                    print(f"Gesamtsignal: {ichimoku_data['overall_signal']}")
        
            elif indicator_choice == "5":
                # VWAP
                vwap_data = self.advanced_indicators.calculate_vwap(symbol)
                if vwap_data:
                    print(f"\n📊 VWAP ANALYSE:")
                    print(f"VWAP: {vwap_data['vwap']}")
                    print(f"Aktueller Preis: {vwap_data['current_price']}")
                    print(f"Abstand: {vwap_data['distance_pct']}%")
                    print(f"Signal: {vwap_data['signal']}")
                    print(f"Beschreibung: {vwap_data['description']}")
        
            elif indicator_choice == "6":
                # MFI
                mfi_data = self.advanced_indicators.calculate_mfi(symbol)
                if mfi_data:
                    print(f"\n💰 MONEY FLOW INDEX:")
                    print(f"Wert: {mfi_data['value']}")
                    print(f"Signal: {mfi_data['signal']}")
                    print(f"Beschreibung: {mfi_data['description']}")
        
            elif indicator_choice == "7":
                # ADX
                adx_data = self.advanced_indicators.calculate_adx(symbol)
                if adx_data:
                    print(f"\n📈 AVERAGE DIRECTIONAL INDEX:")
                    print(f"ADX: {adx_data['adx']}")
                    print(f"DI+: {adx_data['di_plus']}")
                    print(f"DI-: {adx_data['di_minus']}")
                    print(f"Trend-Stärke: {adx_data['trend_strength']}")
                    print(f"Trend-Richtung: {adx_data['trend_direction']}")
                    print(f"Signal: {adx_data['signal']}")
        
            elif indicator_choice == "8":
                # Alle Indikatoren
                analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
                if analysis:
                    self.advanced_indicators.print_analysis_report(symbol, analysis)
        
        except Exception as e:
            print(f"❌ Fehler bei Indikator-Berechnung: {e}")

    def comprehensive_technical_analysis(self):
        """Vollständige technische Analyse mit allen verfügbaren Indikatoren"""
        self.print_header("VOLLSTÄNDIGE TECHNISCHE ANALYSE")
    
        symbol = input("💱 Symbol für vollständige Analyse: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
    
        print(f"\n🔄 Führe vollständige Analyse für {symbol} durch...")
        print("─" * 60)
    
        try:
            # 1. Basis-Indikatoren (Ihr bestehender Code)
            print("📊 BASIS-INDIKATOREN:")
            print("─" * 30)
        
            # RSI
            rsi_value = self.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, rsi_desc = self.get_rsi_signal(rsi_value)
                icon = "🟢" if rsi_signal == "BUY" else "🔴" if rsi_signal == "SELL" else "🟡"
                print(f"{icon} RSI: {rsi_value} - {rsi_desc}")
        
            # MACD
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, macd_desc = self.get_macd_signal(macd_data)
                icon = "🟢" if macd_signal == "BUY" else "🔴" if macd_signal == "SELL" else "🟡"
                print(f"{icon} MACD: {macd_desc}")
        
            # Support/Resistance
            sr_data = self.calculate_support_resistance(symbol)
            if sr_data:
                current_price = sr_data['current_price']
                sr_signal, sr_desc = self.get_sr_signal(sr_data, current_price)
                icon = "🟢" if sr_signal == "BUY" else "🔴" if sr_signal == "SELL" else "🟡"
                print(f"{icon} S/R: {sr_desc}")
        
            # 2. Erweiterte Indikatoren
            if self.advanced_indicators:
                print("\n📈 ERWEITERTE INDIKATOREN:")
                print("─" * 30)
            
                advanced_analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
                if advanced_analysis:
                    self.advanced_indicators.print_analysis_report(symbol, advanced_analysis)
        
            # 3. Gesamtbewertung
            if self.integration:
                print("\n🎯 GESAMTBEWERTUNG:")
                print("─" * 30)
            
                trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
            
                signal_icon = "🚀" if trading_signal['signal'] == "STRONG_BUY" else \
                             "🟢" if trading_signal['signal'] == "BUY" else \
                             "💥" if trading_signal['signal'] == "STRONG_SELL" else \
                             "🔴" if trading_signal['signal'] == "SELL" else "🟡"
            
                print(f"{signal_icon} SIGNAL: {trading_signal['signal']}")
                print(f"🎯 KONFIDENZ: {trading_signal['confidence']}")
                print(f"📊 ANALYSIERTE INDIKATOREN: {trading_signal['total_indicators']}")
            
                if trading_signal.get('buy_ratio', 0) > 0 or trading_signal.get('sell_ratio', 0) > 0:
                    print(f"📈 Bullisch: {trading_signal.get('buy_ratio', 0):.1%}")
                    print(f"📉 Bearisch: {trading_signal.get('sell_ratio', 0):.1%}")
            
                # Top-Signale anzeigen
                if trading_signal.get('supporting_signals'):
                    print(f"\n✅ TOP UNTERSTÜTZENDE SIGNALE:")
                    for i, signal in enumerate(trading_signal['supporting_signals'][:5], 1):
                        print(f"{i}. {signal}")
        
            print("─" * 60)
        
        except Exception as e:
            print(f"❌ Vollständige Analyse Fehler: {e}")

    def currency_pair_management_menu(self):
        """Vollständiges Währungspaar-Management ohne externe Abhängigkeiten"""
    
        # NOTFALL-INITIALISIERUNG (falls Attribute fehlen)
        if not hasattr(self, 'custom_pairs'):
            self.custom_pairs = {
                "user_favorites": {
                    "name": "Meine Favoriten",
                    "pairs": [],
                    "description": "Ihre persönlichen Lieblings-Paare"
                }
            }
    
        # Vordefinierte Listen direkt hier
        predefined_lists = {
            "major": {
                "name": "Majors (Hauptwährungspaare)",
                "pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"],
                "description": "Die 7 wichtigsten Forex-Paare"
            },
            "eur_cross": {
                "name": "EUR Cross-Paare", 
                "pairs": ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD"],
                "description": "Euro-basierte Währungspaare"
            },
            "gbp_cross": {
                "name": "GBP Cross-Paare",
                "pairs": ["GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD"],
                "description": "Pfund-basierte Währungspaare"
            },
            "conservative": {
                "name": "Konservative Auswahl",
                "pairs": ["EURUSD", "GBPUSD", "USDCHF"],
                "description": "Stabile, gut vorhersagbare Paare"
            },
            "volatile": {
                "name": "Volatile Paare",
                "pairs": ["GBPJPY", "GBPAUD", "EURJPY", "AUDJPY", "GBPNZD"],
                "description": "Hochvolatile Paare für erfahrene Trader"
            },
            "safe_haven": {
                "name": "Safe Haven",
                "pairs": ["USDCHF", "USDJPY", "CHFJPY", "XAUUSD"],
                "description": "Sichere Häfen"
            }
        }
    
        while True:
            self.print_header("WÄHRUNGSPAAR MANAGEMENT")
        
            print("📋 AKTUELLE KONFIGURATION:")
            print("─" * 40)
        
            if hasattr(self, 'auto_trade_symbols') and self.auto_trade_symbols:
                print(f"📊 Auto-Trading Paare: {len(self.auto_trade_symbols)}")
                for i, symbol in enumerate(self.auto_trade_symbols[:5], 1):
                    print(f"   {i}. {symbol}")
                if len(self.auto_trade_symbols) > 5:
                    print(f"   ... und {len(self.auto_trade_symbols) - 5} weitere")
            else:
                print("❌ Keine Auto-Trading Paare konfiguriert")
        
            favorites = self.custom_pairs["user_favorites"]["pairs"]
            if favorites:
                print(f"💾 Favoriten: {len(favorites)} - {', '.join(favorites[:3])}")
                if len(favorites) > 3:
                    print(f"            ... und {len(favorites) - 3} weitere")
        
            print(f"\n📋 OPTIONEN:")
            print("─" * 15)
            print(" 1. 🔧 Vordefinierte Liste wählen")
            print(" 2. ✍️ Manuell eingeben")
            print(" 3. 💾 Favoriten verwalten")
            print(" 4. 📊 Verfügbare Paare anzeigen")
            print(" 5. 🔍 Paar-Verfügbarkeit prüfen")
            print(" 6. 📈 Performance-Analyse")
            print(" 7. ⬅️ Zurück")
        
            choice = input("\n🎯 Ihre Wahl (1-7): ").strip()
        
            if choice == "1":
                # Vordefinierte Listen anzeigen
                print(f"\n📋 VORDEFINIERTE LISTEN:")
                print("─" * 30)
            
                list_options = {}
                counter = 1
            
                for key, config in predefined_lists.items():
                    list_options[str(counter)] = (key, config)
                    print(f" {counter}. {config['name']} ({len(config['pairs'])} Paare)")
                    print(f"    💡 {config['description']}")
                    if len(config['pairs']) <= 7:
                        print(f"    💱 {', '.join(config['pairs'])}")
                    else:
                        print(f"    💱 {', '.join(config['pairs'][:5])}...")
                    print()
                    counter += 1
            
                print(" 0. ⬅️ Zurück")
            
                list_choice = input(f"Wählen Sie eine Liste (0-{counter-1}): ").strip()
            
                if list_choice == "0":
                    continue
                elif list_choice in list_options:
                    key, config = list_options[list_choice]
                
                    # Verfügbarkeits-Check
                    available_pairs = config['pairs'].copy()
                    unavailable_pairs = []
                
                    if self.mt5_connected:
                        print(f"\n🔍 Prüfe Verfügbarkeit...")
                        available_pairs = []
                    
                        for pair in config['pairs']:
                            symbol_info = mt5.symbol_info(pair)
                            if symbol_info and symbol_info.visible:
                                available_pairs.append(pair)
                            else:
                                unavailable_pairs.append(pair)
                    
                        print(f"✅ Verfügbar: {len(available_pairs)}/{len(config['pairs'])}")
                        if unavailable_pairs:
                            print(f"❌ Nicht verfügbar: {', '.join(unavailable_pairs)}")
                
                    if available_pairs:
                        print(f"\n📊 {config['name']}")
                        print(f"💱 Verfügbare Paare: {', '.join(available_pairs)}")
                    
                        confirm = input("\nDiese Auswahl für Auto-Trading verwenden? (ja/nein): ").lower()
                        if confirm == "ja":
                            self.auto_trade_symbols = available_pairs
                            print(f"✅ {len(available_pairs)} Paare für Auto-Trading aktiviert!")
                        
                            # Optional zu Favoriten hinzufügen
                            save_fav = input("Auswahl zu Favoriten hinzufügen? (ja/nein): ").lower()
                            if save_fav == "ja":
                                for pair in available_pairs:
                                    if pair not in favorites:
                                        favorites.append(pair)
                                print("✅ Zu Favoriten hinzugefügt")
                    else:
                        print("❌ Keine verfügbaren Paare in dieser Liste")
                else:
                    print("❌ Ungültige Auswahl")
                
            elif choice == "2":
                # Manuelle Eingabe
                print(f"\n✍️ MANUELLE EINGABE:")
                print("─" * 25)
                print("💡 Formate:")
                print("   • Einzeln: EURUSD")
                print("   • Mehrere: EURUSD,GBPUSD,USDJPY")
                print("   • Mit Leerzeichen: EURUSD GBPUSD USDJPY")
            
                user_input = input("\n💱 Währungspaare eingeben: ").upper().strip()
            
                if user_input:
                    # Parse Input
                    if ',' in user_input:
                        pairs = [p.strip() for p in user_input.split(',')]
                    else:
                        pairs = user_input.split()
                
                    # Validierung
                    valid_pairs = []
                    invalid_pairs = []
                
                    for pair in pairs:
                        if pair:
                            if self.mt5_connected:
                                symbol_info = mt5.symbol_info(pair)
                                if symbol_info and symbol_info.visible:
                                    valid_pairs.append(pair)
                                else:
                                    invalid_pairs.append(pair)
                            else:
                                valid_pairs.append(pair)
                
                    print(f"\n📊 VALIDIERUNG:")
                    if valid_pairs:
                        print(f"✅ Gültig: {len(valid_pairs)} - {', '.join(valid_pairs)}")
                    if invalid_pairs:
                        print(f"❌ Ungültig: {len(invalid_pairs)} - {', '.join(invalid_pairs)}")
                
                    if valid_pairs:
                        confirm = input(f"\n{len(valid_pairs)} gültige Paare verwenden? (ja/nein): ").lower()
                        if confirm == "ja":
                            self.auto_trade_symbols = valid_pairs
                            print(f"✅ {len(valid_pairs)} Paare aktiviert!")
                    else:
                        print("❌ Keine gültigen Paare")
                else:
                    print("❌ Keine Eingabe")
                
            elif choice == "3":
                # Favoriten verwalten
                self.manage_favorite_pairs_simple()
            
            elif choice == "4":
                # Verfügbare Paare anzeigen
                self.show_available_pairs_simple()
            
            elif choice == "5":
                # Verfügbarkeit prüfen
                self.check_pair_availability_simple()
            
            elif choice == "6":
                # Performance-Analyse
                self.analyze_pair_performance_simple()
            
            elif choice == "7":
                break
            
            else:
                print("❌ Ungültige Auswahl")
        
            input("\nDrücken Sie Enter zum Fortfahren...")

    def manage_favorite_pairs_simple(self):
        """Vereinfachte Favoriten-Verwaltung"""
    
        favorites = self.custom_pairs["user_favorites"]["pairs"]
    
        while True:
            print(f"\n💾 FAVORITEN VERWALTEN:")
            print("─" * 25)
        
            if favorites:
                print("📋 Aktuelle Favoriten:")
                for i, pair in enumerate(favorites, 1):
                    print(f"   {i}. {pair}")
            else:
                print("📋 Keine Favoriten gespeichert")
        
            print(f"\nOptionen:")
            print("1. ➕ Favorit hinzufügen")
            print("2. ➖ Favorit entfernen") 
            print("3. 🔄 Favoriten für Auto-Trading verwenden")
            print("4. 🗑️ Alle Favoriten löschen")
            print("5. ⬅️ Zurück")
        
            choice = input("\nWählen (1-5): ").strip()
        
            if choice == "1":
                new_pair = input("Währungspaar eingeben: ").upper().strip()
                if new_pair and new_pair not in favorites:
                    favorites.append(new_pair)
                    print(f"✅ {new_pair} zu Favoriten hinzugefügt")
                else:
                    print("❌ Ungültiges Paar oder bereits vorhanden")
        
            elif choice == "2":
                if favorites:
                    try:
                        index = int(input("Nummer zum Entfernen: ")) - 1
                        if 0 <= index < len(favorites):
                            removed = favorites.pop(index)
                            print(f"✅ {removed} entfernt")
                        else:
                            print("❌ Ungültige Nummer")
                    except ValueError:
                        print("❌ Ungültige Eingabe")
                else:
                    print("❌ Keine Favoriten vorhanden")
        
            elif choice == "3":
                if favorites:
                    self.auto_trade_symbols = favorites.copy()
                    print(f"✅ {len(favorites)} Favoriten für Auto-Trading aktiviert")
                    return
                else:
                    print("❌ Keine Favoriten vorhanden")
        
            elif choice == "4":
                if favorites:
                    confirm = input("Alle Favoriten löschen? (ja/nein): ").lower()
                    if confirm == "ja":
                        favorites.clear()
                        print("✅ Alle Favoriten gelöscht")
                else:
                    print("❌ Keine Favoriten vorhanden")
        
            elif choice == "5":
                break

    def show_available_pairs_simple(self):
        """Vereinfachte Anzeige verfügbarer Paare"""
    
        if not self.mt5_connected:
            print("❌ MT5 nicht verbunden - kann Verfügbarkeit nicht prüfen")
            return
    
        print("\n📊 VERFÜGBARE WÄHRUNGSPAARE:")
        print("─" * 35)
    
        try:
            symbols = mt5.symbols_get()
            if not symbols:
                print("❌ Keine Symbole gefunden")
                return
        
            # Nur Forex-Paare (6 Zeichen, nur Buchstaben)
            forex_pairs = [s.name for s in symbols if s.visible and len(s.name) == 6 and s.name.isalpha()]
        
            if forex_pairs:
                print(f"💱 Forex-Paare ({len(forex_pairs)}):")
                # Zeige in 4er-Spalten
                for i in range(0, len(forex_pairs), 4):
                    row = forex_pairs[i:i+4]
                    print("   " + "".join(f"{pair:<12}" for pair in row))
        
            print(f"\n📊 Gesamt verfügbare Forex-Paare: {len(forex_pairs)}")
        
        except Exception as e:
            print(f"❌ Fehler: {e}")

    def check_pair_availability_simple(self):
        """Vereinfachte Verfügbarkeits-Prüfung"""
    
        pairs_input = input("\n💱 Paare prüfen (kommagetrennt): ").upper().strip()
        if not pairs_input:
            return
    
        pairs = [p.strip() for p in pairs_input.split(',')]
    
        print(f"\n🔍 VERFÜGBARKEITS-CHECK:")
        print("─" * 30)
    
        for pair in pairs:
            if self.mt5_connected:
                symbol_info = mt5.symbol_info(pair)
                if symbol_info and symbol_info.visible:
                    tick = mt5.symbol_info_tick(pair)
                    if tick:
                        price = (tick.bid + tick.ask) / 2
                        print(f"✅ {pair:<10} Preis: {price:.5f}")
                    else:
                        print(f"⚠️ {pair:<10} Symbol OK, keine Preise")
                else:
                    print(f"❌ {pair:<10} Nicht verfügbar")
            else:
                print(f"❓ {pair:<10} MT5 nicht verbunden")

    def analyze_pair_performance_simple(self):
        """Vereinfachte Performance-Analyse"""
    
        if not hasattr(self, 'auto_trade_symbols') or not self.auto_trade_symbols:
            print("❌ Keine Auto-Trading Paare konfiguriert")
            return
    
        print(f"\n📈 PERFORMANCE-ANALYSE:")
        print("─" * 30)
    
        for symbol in self.auto_trade_symbols[:10]:
            try:
                if self.mt5_connected:
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        # RSI berechnen
                        rsi = self.calculate_rsi(symbol) if hasattr(self, 'calculate_rsi') else None
                        rsi_status = "📈" if rsi and rsi < 30 else "📉" if rsi and rsi > 70 else "📊"
                    
                        # Spread als Volatilitäts-Indikator
                        spread = tick.ask - tick.bid
                        vol_status = "🔥" if spread > 0.0003 else "🟢" if spread < 0.0001 else "🟡"
                    
                        print(f"{rsi_status} {symbol:<10} RSI: {rsi or 'N/A':<5} | Vol: {vol_status}")
                    else:
                        print(f"❌ {symbol:<10} Keine Daten")
                else:
                    print(f"❓ {symbol:<10} MT5 nicht verbunden")
            except Exception as e:
                print(f"⚠️ {symbol:<10} Fehler")
    
        print("\n💡 Legende: 📈 Überverkauft | 📉 Überkauft | 📊 Neutral")
        print("💡 Volatilität: 🔥 Hoch | 🟡 Normal | 🟢 Niedrig")

    def companion_menu(self):
        """Separates Trading Companion Menü"""
        while True:
            self.print_header("TRADING COMPANION")
            
            print(f"📊 Status: {'🟢 Aktiv' if self.companion_enabled else '🔴 Inaktiv'}")
            print(f"🔄 Auto-Start: {'✅ Ein' if self.auto_start_companion else '❌ Aus'}")
            
            if self.companion_enabled:
                print("🔧 Trading Companion ist bereit für erweiterte Analysen")
            else:
                print("❌ Trading Companion ist nicht verfügbar")
            
            print("\n📋 OPTIONEN:")
            print("─" * 25)
            print(" 1. 🔄 Starten/Stoppen")
            print(" 2. ⚙️ Auto-Start ein/aus")
            print(" 3. 📊 Erweiterte Analyse anfordern")
            print(" 4. 🔇 Silent Mode ein/aus")
            print(" 5. ⬅️ Zurück zum Hauptmenü")
            print("─" * 35)
            
            choice = input("🎯 Ihre Wahl (1-5): ").strip()
            
            if choice == "1":
                if self.companion_enabled:
                    print("🔧 Stoppe Trading Companion...")
                    self.stop_trading_companion()
                else:
                    print("🔧 Starte Trading Companion...")
                    self.start_trading_companion()
                
                input("\n📝 Drücken Sie Enter zum Fortfahren...")
            
            elif choice == "2":
                self.auto_start_companion = not self.auto_start_companion
                status = "✅ Aktiviert" if self.auto_start_companion else "❌ Deaktiviert"
                print(f"🔄 Auto-Start: {status}")
                input("\n📝 Drücken Sie Enter zum Fortfahren...")
            
            elif choice == "3":
                if self.companion_enabled:
                    symbol = input("💱 Symbol für erweiterte Analyse: ").upper()
                    if symbol:
                        print("🔧 Fordere erweiterte Analyse an...")
                        self.request_companion_analysis(symbol)
                else:
                    print("❌ Trading Companion ist nicht aktiv")
                
                input("\n📝 Drücken Sie Enter zum Fortfahren...")
            
            elif choice == "4":
                self.companion_silent_mode = not self.companion_silent_mode
                status = "🔇 Ein" if self.companion_silent_mode else "🔊 Aus"
                print(f"Silent Mode: {status}")
                input("\n📝 Drücken Sie Enter zum Fortfahren...")
            
            elif choice == "5":
                break
            
            else:
                print("❌ Ungültige Auswahl")
                input("\n📝 Drücken Sie Enter zum Fortfahren...")

    def calculate_macd(self, symbol, timeframe=None, fast_period=None, slow_period=None, signal_period=None):
        """Berechnet MACD für ein Symbol"""
        if not self.mt5_connected:
            return None
    
        try:
            if timeframe is None:
                timeframe = self.macd_timeframe
            if fast_period is None:
                fast_period = self.macd_fast_period
            if slow_period is None:
                slow_period = self.macd_slow_period
            if signal_period is None:
                signal_period = self.macd_signal_period
        
            # Hole historische Daten (mehr für EMA-Berechnung)
            required_bars = max(slow_period, signal_period) + signal_period + 20
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, required_bars)
        
            if rates is None or len(rates) < required_bars:
                return None
        
            # Extrahiere Schlusskurse
            closes = np.array([rate['close'] for rate in rates])
        
            # Berechne EMAs
            def calculate_ema(data, period):
                """Berechnet Exponential Moving Average"""
                alpha = 2 / (period + 1)
                ema = np.zeros_like(data)
                ema[0] = data[0]
            
                for i in range(1, len(data)):
                    ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            
                return ema
        
            # Berechne Fast und Slow EMA
            fast_ema = calculate_ema(closes, fast_period)
            slow_ema = calculate_ema(closes, slow_period)
        
            # MACD Line = Fast EMA - Slow EMA
            macd_line = fast_ema - slow_ema
        
            # Signal Line = EMA von MACD Line
            signal_line = calculate_ema(macd_line, signal_period)
        
            # Histogram = MACD Line - Signal Line
            histogram = macd_line - signal_line
        
            # Aktuelle Werte (letzte 3 für Trend-Analyse)
            current_macd = macd_line[-1]
            current_signal = signal_line[-1]
            current_histogram = histogram[-1]
        
            # Vorherige Werte für Kreuzungen
            prev_macd = macd_line[-2] if len(macd_line) > 1 else current_macd
            prev_signal = signal_line[-2] if len(signal_line) > 1 else current_signal
            prev_histogram = histogram[-2] if len(histogram) > 1 else current_histogram
        
            # Histogram Trend (letzte 3 Balken)
            if len(histogram) >= 3:
                histogram_trend = "STEIGEND" if histogram[-1] > histogram[-2] > histogram[-3] else \
                                "FALLEND" if histogram[-1] < histogram[-2] < histogram[-3] else "SEITWÄRTS"
            else:
                histogram_trend = "UNBEKANNT"
        
            return {
                'macd': round(current_macd, 6),
                'signal': round(current_signal, 6),
                'histogram': round(current_histogram, 6),
                'prev_macd': round(prev_macd, 6),
                'prev_signal': round(prev_signal, 6),
                'prev_histogram': round(prev_histogram, 6),
                'histogram_trend': histogram_trend,
                'macd_line': macd_line[-10:],  # Letzte 10 Werte für erweiterte Analyse
                'signal_line': signal_line[-10:],
                'histogram_values': histogram[-10:]
            }
        
        except Exception as e:
            print(f"MACD Berechnung Fehler: {e}")
            return None
   
    def get_macd_signal(self, macd_data):
        """Interpretiert MACD-Werte für Trading-Signal"""
        if not macd_data:
            return "NEUTRAL", "MACD nicht verfügbar"
    
        try:
            macd = macd_data['macd']
            signal = macd_data['signal']
            histogram = macd_data['histogram']
            prev_macd = macd_data['prev_macd']
            prev_signal = macd_data['prev_signal']
            prev_histogram = macd_data['prev_histogram']
            histogram_trend = macd_data['histogram_trend']
        
            signals = []
            signal_strength = 0
        
            # 1. MACD Line Kreuzung mit Signal Line
            macd_above_signal = macd > signal
            prev_macd_above_signal = prev_macd > prev_signal
        
            # Bullische Kreuzung (MACD kreuzt Signal von unten)
            if macd_above_signal and not prev_macd_above_signal:
                signals.append("BULLISCHE KREUZUNG")
                signal_strength += 2
            
            # Bearische Kreuzung (MACD kreuzt Signal von oben)
            elif not macd_above_signal and prev_macd_above_signal:
                signals.append("BEARISCHE KREUZUNG")
                signal_strength -= 2
        
            # 2. Nulllinie Kreuzung
            macd_above_zero = macd > 0
            prev_macd_above_zero = prev_macd > 0
        
            # MACD kreuzt Nulllinie nach oben
            if macd_above_zero and not prev_macd_above_zero:
                signals.append("NULLLINIE BULLISCH")
                signal_strength += 1
            
            # MACD kreuzt Nulllinie nach unten
            elif not macd_above_zero and prev_macd_above_zero:
                signals.append("NULLLINIE BEARISCH")
                signal_strength -= 1
        
            # 3. Histogram Analyse
            histogram_above_zero = histogram > 0
            prev_histogram_above_zero = prev_histogram > 0
        
            # Histogram wird positiv
            if histogram_above_zero and not prev_histogram_above_zero:
                signals.append("MOMENTUM BULLISCH")
                signal_strength += 1
            
            # Histogram wird negativ
            elif not histogram_above_zero and prev_histogram_above_zero:
                signals.append("MOMENTUM BEARISCH")
                signal_strength -= 1
        
            # 4. Histogram Trend
            if histogram_trend == "STEIGEND":
                if histogram > 0:
                    signals.append("AUFWÄRTS-MOMENTUM")
                    signal_strength += 1
                else:
                    signals.append("MOMENTUM ERHOLT SICH")
            elif histogram_trend == "FALLEND":
                if histogram < 0:
                    signals.append("ABWÄRTS-MOMENTUM")
                    signal_strength -= 1
                else:
                    signals.append("MOMENTUM SCHWÄCHT AB")
        
            # 5. Position relativ zur Nulllinie
            if macd > 0 and signal > 0:
                signals.append("ÜBER NULLLINIE")
            elif macd < 0 and signal < 0:
                signals.append("UNTER NULLLINIE")
        
            # Signal-Bewertung
            if signal_strength >= 3:
                main_signal = "BUY"
                description = f"Starkes Kaufsignal ({signal_strength}): {', '.join(signals[:2])}"
            elif signal_strength >= 1:
                main_signal = "BUY"
                description = f"Kaufsignal ({signal_strength}): {', '.join(signals[:2])}"
            elif signal_strength <= -3:
                main_signal = "SELL"
                description = f"Starkes Verkaufssignal ({signal_strength}): {', '.join(signals[:2])}"
            elif signal_strength <= -1:
                main_signal = "SELL"
                description = f"Verkaufssignal ({signal_strength}): {', '.join(signals[:2])}"
            else:
                main_signal = "NEUTRAL"
                if signals:
                    description = f"Neutral: {', '.join(signals[:2])}"
                else:
                    description = f"Seitwärts (MACD: {macd:.6f}, Signal: {signal:.6f})"
        
            # Zusätzliche Informationen
            detailed_info = {
                'signal': main_signal,
                'description': description,
                'strength': signal_strength,
                'all_signals': signals,
                'macd_above_signal': macd_above_signal,
                'macd_above_zero': macd_above_zero,
                'histogram_positive': histogram_above_zero,
                'trend': histogram_trend
            }
        
            return main_signal, description
        
        except Exception as e:
            return "NEUTRAL", f"MACD Analyse Fehler: {e}"

    def get_higher_timeframe_trend(self, symbol):
        """Analysiert den übergeordneten Trend auf höherem Timeframe"""
        if not self.mt5_connected:
            return None
    
        try:
            # Hole Daten vom höheren Timeframe (H1)
            required_bars = self.trend_ema_period + 10
            rates = mt5.copy_rates_from_pos(symbol, self.trend_timeframe, 0, required_bars)
        
            if rates is None or len(rates) < required_bars:
                return None
        
            # Extrahiere Schlusskurse
            closes = np.array([rate['close'] for rate in rates])
            highs = np.array([rate['high'] for rate in rates])
            lows = np.array([rate['low'] for rate in rates])
        
            # Berechne EMA für Trendbestimmung
            def calculate_ema(data, period):
                alpha = 2 / (period + 1)
                ema = np.zeros_like(data)
                ema[0] = data[0]
            
                for i in range(1, len(data)):
                    ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            
                return ema
        
            # EMA berechnen
            ema = calculate_ema(closes, self.trend_ema_period)
        
            # Aktuelle Werte
            current_price = closes[-1]
            current_ema = ema[-1]
            prev_ema = ema[-2] if len(ema) > 1 else current_ema
            ema_slope = current_ema - prev_ema
        
            # EMA-Trend bestimmen
            price_above_ema = current_price > current_ema
            ema_rising = current_ema > prev_ema
        
            # Trendstärke berechnen (Abstand zwischen Preis und EMA)
            trend_strength = abs(current_price - current_ema)
        
            # Zusätzliche Trend-Bestätigung durch Swing-Analyse
            recent_bars = 10
            recent_highs = highs[-recent_bars:]
            recent_lows = lows[-recent_bars:]
        
            # Higher Highs / Lower Lows Pattern
            higher_highs = len([i for i in range(1, len(recent_highs)) if recent_highs[i] > recent_highs[i-1]]) >= 6
            lower_lows = len([i for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i-1]]) >= 6
        
            # Trend-Richtung bestimmen
            if price_above_ema and ema_rising:
                if trend_strength >= self.trend_strength_threshold:
                    direction = "BULLISH"
                else:
                    direction = "WEAK_BULLISH"
            elif not price_above_ema and not ema_rising:
                if trend_strength >= self.trend_strength_threshold:
                    direction = "BEARISH"
                else:
                    direction = "WEAK_BEARISH"
            else:
                direction = "NEUTRAL"
        
            # Zusätzliche Bestätigung durch Swing-Pattern
            if direction == "BULLISH" and not higher_highs:
                direction = "WEAK_BULLISH"
            elif direction == "BEARISH" and not lower_lows:
                direction = "WEAK_BEARISH"
        
            # Trend-Qualität bewerten
            trend_quality = "STRONG" if trend_strength >= self.trend_strength_threshold * 2 else \
                           "MODERATE" if trend_strength >= self.trend_strength_threshold else "WEAK"
        
            # Momentum berechnen (letzte 5 Bars)
            momentum_bars = 5
            if len(closes) >= momentum_bars:
                momentum = closes[-1] - closes[-momentum_bars]
                momentum_direction = "UP" if momentum > 0 else "DOWN" if momentum < 0 else "FLAT"
            else:
                momentum = 0
                momentum_direction = "FLAT"
        
            return {
                'direction': direction,
                'strength': trend_strength,
                'quality': trend_quality,
                'current_price': current_price,
                'ema_level': current_ema,
                'ema_slope': ema_slope,
                'price_above_ema': price_above_ema,
                'ema_rising': ema_rising,
                'momentum': momentum,
                'momentum_direction': momentum_direction,
                'higher_highs': higher_highs,
                'lower_lows': lower_lows,
                'timeframe': self.trend_timeframe
            }
        
        except Exception as e:
            print(f"Trend-Analyse Fehler: {e}")
            return None

    def update_trailing_stops(self):
        """Aktualisiert alle Trailing Stops für offene Positionen"""
        if not self.mt5_connected or not self.trailing_stop_enabled:
            return
    
        try:
            positions = mt5.positions_get()
            if not positions:
                return
        
            updated_count = 0
        
            for position in positions:
                # Nur eigene Positionen (Magic Number)
                if position.magic != 234000:
                    continue
            
                # Aktuelle Marktpreise holen
                tick = mt5.symbol_info_tick(position.symbol)
                if not tick:
                    continue
            
                current_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
            
                # Berechne neuen Trailing Stop
                new_sl = self.calculate_trailing_stop(position, current_price)
            
                if new_sl and new_sl != position.sl:
                    # Stop Loss modifizieren
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": position.symbol,
                        "position": position.ticket,
                        "sl": new_sl,
                        "tp": position.tp
                    }
                
                    result = mt5.order_send(request)
                
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        updated_count += 1
                        self.log("INFO", f"Trailing Stop aktualisiert: {position.symbol} SL: {position.sl:.5f} -> {new_sl:.5f}", "TRAILING")
                        print(f"Trailing Stop {position.symbol}: {new_sl:.5f}")
                    else:
                        self.log("WARNING", f"Trailing Stop Fehler {position.symbol}: {result.comment}", "TRAILING")
        
            if updated_count > 0:
                self.log("INFO", f"{updated_count} Trailing Stops aktualisiert", "TRAILING")
            
        except Exception as e:
            self.log_error("update_trailing_stops", e)

    def calculate_trailing_stop(self, position, current_price):
        """Berechnet neuen Trailing Stop Level für eine Position"""
        try:
            symbol_info = mt5.symbol_info(position.symbol)
            if not symbol_info:
                return None
        
            # Pip-Wert für das Symbol
            pip_size = symbol_info.point
            if symbol_info.digits == 3 or symbol_info.digits == 5:
                pip_size *= 10
        
            # Profit in Pips berechnen
            if position.type == mt5.ORDER_TYPE_BUY:
                profit_pips = (current_price - position.price_open) / pip_size
            
                # Prüfe ob Mindest-Profit erreicht
                if profit_pips < self.trailing_stop_start_profit_pips:
                    return None
            
                # Berechne neuen Stop Loss
                new_sl = current_price - (self.trailing_stop_distance_pips * pip_size)
            
                # Stop Loss darf nur nach oben (günstiger) bewegt werden
                if position.sl == 0 or new_sl > position.sl:
                    # Prüfe Mindestabstand
                    min_distance = symbol_info.trade_stops_level * symbol_info.point
                    if (current_price - new_sl) >= min_distance:
                        return round(new_sl, symbol_info.digits)
                    
            else:  # SELL Position
                profit_pips = (position.price_open - current_price) / pip_size
            
                # Prüfe ob Mindest-Profit erreicht
                if profit_pips < self.trailing_stop_start_profit_pips:
                    return None
            
                # Berechne neuen Stop Loss
                new_sl = current_price + (self.trailing_stop_distance_pips * pip_size)
            
                # Stop Loss darf nur nach unten (günstiger) bewegt werden
                if position.sl == 0 or new_sl < position.sl:
                    # Prüfe Mindestabstand
                    min_distance = symbol_info.trade_stops_level * symbol_info.point
                    if (new_sl - current_price) >= min_distance:
                        return round(new_sl, symbol_info.digits)
        
            return None
        
        except Exception as e:
            self.log_error("calculate_trailing_stop", e, f"Position: {position.ticket}")
            return None
    
    def trailing_stop_settings_menu(self):
        """Trailing Stop Einstellungen Menü"""
        while True:
            print("\n🎯 TRAILING STOP EINSTELLUNGEN")
            print("─" * 40)
            print(f"Status: {'✅ Aktiviert' if self.trailing_stop_enabled else '❌ Deaktiviert'}")
            print(f"Abstand: {self.trailing_stop_distance_pips} Pips")
            print(f"Schritt: {self.trailing_stop_step_pips} Pips")
            print(f"Start ab Profit: {self.trailing_stop_start_profit_pips} Pips")
        
            print("\n1. Ein/Ausschalten")
            print("2. Abstand ändern")
            print("3. Schrittweite ändern")
            print("4. Start-Profit ändern")
            print("5. Sofort aktualisieren")
            print("6. Zurück")
        
            choice = input("\nWählen (1-6): ").strip()
        
            if choice == "1":
                old_status = self.trailing_stop_enabled
                self.trailing_stop_enabled = not self.trailing_stop_enabled
                status = "aktiviert" if self.trailing_stop_enabled else "deaktiviert"
                self.log("INFO", f"Trailing Stop {status}", "SETTINGS")
                print(f"Trailing Stop {status}")
        
            elif choice == "2":
                try:
                    old_distance = self.trailing_stop_distance_pips
                    new_distance = int(input(f"Abstand in Pips (aktuell {self.trailing_stop_distance_pips}): "))
                    if 5 <= new_distance <= 100:
                        self.trailing_stop_distance_pips = new_distance
                        self.log("INFO", f"Trailing Stop Abstand: {old_distance} -> {new_distance} Pips", "SETTINGS")
                        print(f"Abstand auf {new_distance} Pips gesetzt")
                    else:
                        print("Abstand muss zwischen 5 und 100 Pips liegen")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "3":
                try:
                    old_step = self.trailing_stop_step_pips
                    new_step = int(input(f"Schrittweite in Pips (aktuell {self.trailing_stop_step_pips}): "))
                    if 1 <= new_step <= 20:
                        self.trailing_stop_step_pips = new_step
                        self.log("INFO", f"Trailing Stop Schritt: {old_step} -> {new_step} Pips", "SETTINGS")
                        print(f"Schrittweite auf {new_step} Pips gesetzt")
                    else:
                        print("Schrittweite muss zwischen 1 und 20 Pips liegen")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "4":
                try:
                    old_start = self.trailing_stop_start_profit_pips
                    new_start = int(input(f"Start-Profit in Pips (aktuell {self.trailing_stop_start_profit_pips}): "))
                    if 5 <= new_start <= 50:
                        self.trailing_stop_start_profit_pips = new_start
                        self.log("INFO", f"Trailing Stop Start: {old_start} -> {new_start} Pips", "SETTINGS")
                        print(f"Start-Profit auf {new_start} Pips gesetzt")
                    else:
                        print("Start-Profit muss zwischen 5 und 50 Pips liegen")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "5":
                if self.trailing_stop_enabled:
                    print("Aktualisiere Trailing Stops...")
                    self.update_trailing_stops()
                    print("Trailing Stops aktualisiert")
                else:
                    print("Trailing Stop ist deaktiviert")
        
            elif choice == "6":
                break
        
            else:
                print("Ungültige Auswahl")
        
            input("\nDrücken Sie Enter zum Fortfahren...")

    def enhanced_enable_auto_trading(self):
        """Erweiterte Auto-Trading Aktivierung mit verbesserter Benutzerführung"""
    
        if not self.trading_enabled:
            print("❌ Erst Trading aktivieren!")
            return False
    
        print("\n🤖 VOLLAUTOMATISCHES TRADING SETUP")
        print("═" * 50)
        print("⚠️ WARNUNG: Automatisches Trading ist hochriskant!")
        print("💰 Nur mit Geld handeln, das Sie verlieren können!")
    
        # Sicherheitsabfragen
        confirm1 = input("\nAuto-Trading aktivieren? (GEFÄHRLICH/nein): ")
        if confirm1 != "GEFÄHRLICH":
            return False
    
        confirm2 = input("Risiko verstanden? (ICH_VERSTEHE): ")
        if confirm2 != "ICH_VERSTEHE":
            return False
    
        # Währungspaar-Auswahl mit verbesserter UI
        print(f"\n📋 WÄHRUNGSPAAR AUSWAHL")
        print("─" * 30)
        print("1. 🔥 Standard Majors (EURUSD, GBPUSD, USDJPY)")
        print("2. 🌍 Erweiterte Majors (+ USDCHF, AUDUSD, USDCAD)")
        print("3. 🌎 Alle verfügbaren Paare")
        print("4. ✏️ Eigene Auswahl")
        print("5. 📊 Aktuelle Paare beibehalten")
    
        choice = input("Wählen Sie (1-5): ").strip()
    
        if choice == "1":
            self.auto_trade_symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        elif choice == "2":
            self.auto_trade_symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"]
        elif choice == "3":
            # Alle verfügbaren Forex-Paare
            all_symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", 
                          "NZDUSD", "EURJPY", "GBPJPY", "AUDJPY", "EURGBP", "EURAUD"]
        
            # Prüfe welche verfügbar sind
            available_symbols = []
            print("📊 Prüfe verfügbare Symbole...")
        
            for symbol in all_symbols:
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    available_symbols.append(symbol)
                    print(f"✅ {symbol}")
                else:
                    print(f"❌ {symbol} (nicht verfügbar)")
        
            if available_symbols:
                self.auto_trade_symbols = available_symbols
                print(f"✅ {len(available_symbols)} Paare verfügbar")
            else:
                print("❌ Keine Paare verfügbar - verwende EURUSD")
                self.auto_trade_symbols = ["EURUSD"]
            
        elif choice == "4":
            symbols_input = input("Symbole eingeben (getrennt durch Komma): ").upper()
            if symbols_input:
                symbols = [s.strip() for s in symbols_input.split(',')]
                # Validiere Symbole
                valid_symbols = []
                for symbol in symbols:
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        valid_symbols.append(symbol)
                        print(f"✅ {symbol}")
                    else:
                        print(f"❌ {symbol} (nicht verfügbar)")
            
                if valid_symbols:
                    self.auto_trade_symbols = valid_symbols
                else:
                    print("❌ Keine gültigen Symbole - verwende EURUSD")
                    self.auto_trade_symbols = ["EURUSD"]
            else:
                return False
            
        elif choice == "5":
            if hasattr(self, 'auto_trade_symbols') and self.auto_trade_symbols:
                print(f"📊 Aktuelle Paare: {', '.join(self.auto_trade_symbols)}")
            else:
                print("❌ Keine aktuellen Paare - verwende EURUSD")
                self.auto_trade_symbols = ["EURUSD"]
        else:
            print("❌ Ungültige Auswahl")
            return False
    
        # Intervall-Einstellung
        print(f"\n⏱️ TRADING INTERVALL")
        print("─" * 25)
        print(f"Aktuell: {self.analysis_interval}s")
        print("💡 Empfohlene Intervalle:")
        print("   • 60-120s:  🔥 Aggressiv (mehr Trades)")
        print("   • 180-300s: 📊 Normal (ausgewogen)")
        print("   • 300-600s: 🛡️ Konservativ (weniger Trades)")
    
        new_interval = input(f"Neues Intervall in Sekunden (Enter für {self.analysis_interval}): ")
        if new_interval:
            try:
                interval_value = int(new_interval)
                if 30 <= interval_value <= 3600:  # 30s bis 1h
                    self.analysis_interval = interval_value
                    print(f"✅ Intervall auf {self.analysis_interval}s gesetzt")
                else:
                    print("⚠️ Intervall außerhalb des empfohlenen Bereichs (30-3600s)")
                    self.analysis_interval = max(30, min(3600, interval_value))
                    print(f"✅ Angepasst auf {self.analysis_interval}s")
            except ValueError:
                print("❌ Ungültiges Intervall - verwende aktuelles")
    
        # Risk Management Check
        print(f"\n🛡️ RISK MANAGEMENT STATUS")
        print("─" * 30)
    
        if hasattr(self, 'risk_manager') and self.risk_manager:
            try:
                summary = self.risk_manager.get_risk_summary()
                print("✅ Risk Management aktiv")
                print(f"💰 Aktueller Tages P&L: {summary.get('daily_pnl', 0):.2f}€")
                print(f"📊 Max Verlust heute: {self.risk_manager.max_daily_loss:.2f}€")
                print(f"🎯 Verbleibende Trades: {self.risk_manager.max_trades_per_day - summary.get('trades_today', 0)}")
                print(f"💼 Offene Positionen: {summary.get('open_positions', 0)}/{self.risk_manager.max_total_positions}")
            
                # Warnung bei kritischen Werten
                if summary.get('daily_pnl', 0) <= self.risk_manager.max_daily_loss * 0.8:
                    print("🔴 WARNUNG: Verlustlimit fast erreicht!")
            
            except Exception as e:
                print(f"⚠️ Risk Manager Status-Fehler: {e}")
        else:
            print("❌ Risk Management nicht verfügbar")
            print("⚠️ Trading ohne Schutz - SEHR RISKANT!")
        
            no_risk_confirm = input("Trotzdem fortfahren? (OHNE_SCHUTZ): ")
            if no_risk_confirm != "OHNE_SCHUTZ":
                return False
    
        # Multi-Timeframe Status
        print(f"\n📈 ANALYSE-FILTER STATUS")
        print("─" * 25)
        print(f"📊 RSI Filter: ✅ (Periode: {self.rsi_period})")
        print(f"📈 MACD Filter: ✅ ({self.macd_fast_period}/{self.macd_slow_period}/{self.macd_signal_period})")
        print(f"🎯 S/R Filter: ✅ (Lookback: {self.sr_lookback_period})")
    
        if self.mtf_enabled:
            tf_name = self.timeframe_names.get(self.trend_timeframe, "H1")
            print(f"⏰ Trend Filter: ✅ ({tf_name} Timeframe)")
        else:
            print(f"⏰ Trend Filter: ❌ (deaktiviert)")
    
        # Final Setup
        self.auto_trading = True
    
        print(f"\n🚀 AUTO-TRADING BEREIT!")
        print("═" * 35)
        print(f"📊 Anzahl Paare: {len(self.auto_trade_symbols)}")
        print(f"💱 Symbole: {', '.join(self.auto_trade_symbols[:5])}")
        if len(self.auto_trade_symbols) > 5:
            print(f"         ... und {len(self.auto_trade_symbols) - 5} weitere")
        print(f"⏱️ Analyse-Intervall: {self.analysis_interval}s")
        print(f"🛡️ Risk Management: {'✅' if hasattr(self, 'risk_manager') and self.risk_manager else '❌'}")
        print(f"📈 Filter aktiv: RSI + MACD + S/R{' + Trend' if self.mtf_enabled else ''}")
        print("═" * 35)
    
        # Letzte Bestätigung
        final_confirm = input("\n🎯 Auto-Trading jetzt starten? (START/abbrechen): ")
        if final_confirm == "START":
            self.log("INFO", f"Auto-Trading aktiviert mit {len(self.auto_trade_symbols)} Paaren", "TRADE")
            print(f"\n🚀 STARTE AUTO-TRADING...")
            print("⏸️ Stopp mit Ctrl+C")
            return True
        else:
            self.auto_trading = False
            print("❌ Auto-Trading abgebrochen")
            return False

    def macd_settings_menu(self):
        """MACD Einstellungen Menü"""
        while True:
            print("\n📊 MACD EINSTELLUNGEN")
            print("─" * 40)
            print(f"Fast EMA: {self.macd_fast_period}")
            print(f"Slow EMA: {self.macd_slow_period}")
            print(f"Signal EMA: {self.macd_signal_period}")
            print(f"Zeitrahmen: {self.macd_timeframe}")
        
            print("\n1. Fast EMA Period ändern")
            print("2. Slow EMA Period ändern")
            print("3. Signal EMA Period ändern")
            print("4. Zeitrahmen ändern")
            print("5. MACD Test")
            print("6. Zurück")
        
            choice = input("\nWählen (1-6): ").strip()
        
            if choice == "1":
                try:
                    old_fast = self.macd_fast_period
                    new_fast = int(input(f"Fast EMA Period (aktuell {self.macd_fast_period}): "))
                    if 5 <= new_fast <= 20 and new_fast < self.macd_slow_period:
                        self.macd_fast_period = new_fast
                        self.log("INFO", f"MACD Fast EMA: {old_fast} -> {new_fast}", "SETTINGS")
                        print(f"Fast EMA auf {new_fast} gesetzt")
                    else:
                        print("Fast EMA muss zwischen 5-20 und kleiner als Slow EMA sein")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "2":
                try:
                    old_slow = self.macd_slow_period
                    new_slow = int(input(f"Slow EMA Period (aktuell {self.macd_slow_period}): "))
                    if 20 <= new_slow <= 50 and new_slow > self.macd_fast_period:
                        self.macd_slow_period = new_slow
                        self.log("INFO", f"MACD Slow EMA: {old_slow} -> {new_slow}", "SETTINGS")
                        print(f"Slow EMA auf {new_slow} gesetzt")
                    else:
                        print("Slow EMA muss zwischen 20-50 und größer als Fast EMA sein")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "3":
                try:
                    old_signal = self.macd_signal_period
                    new_signal = int(input(f"Signal EMA Period (aktuell {self.macd_signal_period}): "))
                    if 5 <= new_signal <= 15:
                        self.macd_signal_period = new_signal
                        self.log("INFO", f"MACD Signal EMA: {old_signal} -> {new_signal}", "SETTINGS")
                        print(f"Signal EMA auf {new_signal} gesetzt")
                    else:
                        print("Signal EMA muss zwischen 5-15 liegen")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "4":
                print("\nZeitrahmen:")
                print("1. M1 (1 Minute)")
                print("2. M5 (5 Minuten)")
                print("3. M15 (15 Minuten)")
                print("4. M30 (30 Minuten)")
                print("5. H1 (1 Stunde)")
            
                tf_choice = input("Wählen (1-5): ").strip()
            
                timeframes = {
                    "1": mt5.TIMEFRAME_M1,
                    "2": mt5.TIMEFRAME_M5,
                    "3": mt5.TIMEFRAME_M15,
                    "4": mt5.TIMEFRAME_M30,
                    "5": mt5.TIMEFRAME_H1
                }
            
                if tf_choice in timeframes:
                    old_tf = self.macd_timeframe
                    self.macd_timeframe = timeframes[tf_choice]
                    tf_names = {"1": "M1", "2": "M5", "3": "M15", "4": "M30", "5": "H1"}
                    self.log("INFO", f"MACD Zeitrahmen geändert zu {tf_names[tf_choice]}", "SETTINGS")
                    print(f"Zeitrahmen auf {tf_names[tf_choice]} gesetzt")
                else:
                    print("Ungültige Auswahl")
        
            elif choice == "5":
                symbol = input("Symbol für MACD Test: ").upper()
                if symbol:
                    self.log("INFO", f"MACD Test gestartet für {symbol}", "ANALYSIS")
                    macd_data = self.calculate_macd(symbol)
                    if macd_data:
                        signal, desc = self.get_macd_signal(macd_data)
                        print(f"\n{symbol} MACD Test:")
                        print(f"MACD: {macd_data['macd']}")
                        print(f"Signal: {macd_data['signal']}")
                        print(f"Histogram: {macd_data['histogram']}")
                        print(f"Signal: {signal}")
                        print(f"Beschreibung: {desc}")
                    else:
                        print("MACD Berechnung fehlgeschlagen")
        
            elif choice == "6":
                break
        
            else:
                print("Ungültige Auswahl")
        
            input("\nDrücken Sie Enter zum Fortfahren...")

    def stop_trading_companion(self):
        """Stoppt den Trading Companion sicher"""
        try:
            if self.companion_process:
                print("🔧 Beende Trading Companion...")
                self.companion_process.terminate()
                try:
                    self.companion_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.companion_process.kill()
                self.companion_process = None
            self.companion_enabled = False
            print("✅ Trading Companion gestoppt")
        except Exception as e:
            print(f"❌ Fehler beim Stoppen des Companions: {e}")

    def risk_management_menu(self):
        """Neues Risk Management Menü"""
        while True:
            self.print_header("RISK MANAGEMENT")
            
            # Zeige aktuellen Status

            self.risk_manager.print_risk_status()
            
            print("\n📋 OPTIONEN:")
            print("─" * 25)
            print(" 1. 📊 Risk Status anzeigen")
            print(" 2. ⚙️ Limits anpassen")
            print(" 3. 💰 Position Size Rechner")
            print(" 4. 📈 Tagesstatistiken")
            print(" 5. 🔄 Settings zurücksetzen")
            print(" 6. ⬅️ Zurück zum Hauptmenü")
            print("─" * 35)
            
            choice = input("🎯 Ihre Wahl (1-6): ").strip()
            
            if choice == "1":
                self.risk_manager.print_risk_status()
                
            elif choice == "2":
                self.adjust_risk_limits()
                
            elif choice == "3":
                self.position_size_calculator()
                
            elif choice == "4":
                self.show_daily_stats()
                
            elif choice == "5":
                self.reset_risk_settings()
                
            elif choice == "6":
                break
                
            else:
                print("❌ Ungültige Auswahl")
            
            input("\n📝 Drücken Sie Enter zum Fortfahren...")
    
    def adjust_risk_limits(self):
        """Risk Limits anpassen"""
        print("\n⚙️ RISK LIMITS ANPASSEN")
        print("─" * 30)
        
        try:
            print(f"Aktueller Max. Tagesverlust: {self.risk_manager.max_daily_loss}€")
            new_daily_loss = input("Neuer Max. Tagesverlust (Enter für keine Änderung): ")
            
            print(f"Aktuelles Max. Risiko pro Trade: {self.risk_manager.max_risk_per_trade}%")
            new_risk_per_trade = input("Neues Max. Risiko pro Trade (Enter für keine Änderung): ")
            
            print(f"Aktuelle Max. Gesamtpositionen: {self.risk_manager.max_total_positions}")
            new_max_positions = input("Neue Max. Gesamtpositionen (Enter für keine Änderung): ")
            
            # Updates anwenden
            updates = {}
            if new_daily_loss:
                updates['max_daily_loss'] = float(new_daily_loss)
            if new_risk_per_trade:
                updates['max_risk_per_trade'] = float(new_risk_per_trade)
            if new_max_positions:
                updates['max_total_positions'] = int(new_max_positions)
            
            if updates:
                self.risk_manager.update_settings(**updates)
                print("✅ Risk Limits aktualisiert")
            else:
                print("ℹ️ Keine Änderungen vorgenommen")
                
        except ValueError:
            print("❌ Ungültige Eingabe")
        except Exception as e:
            print(f"❌ Fehler: {e}")
    
    def position_size_calculator(self):
        """Position Size Rechner"""
        print("\n💰 POSITION SIZE RECHNER")
        print("─" * 30)
        
        try:
            symbol = input("Symbol: ").upper()
            if not symbol:
                return
            
            stop_loss_pips = float(input("Stop Loss Abstand (Pips): "))
            risk_percent = float(input(f"Risiko % (aktuell {self.risk_manager.max_risk_per_trade}%): ") or self.risk_manager.max_risk_per_trade)
            
            calculated_size = self.risk_manager.calculate_position_size(symbol, stop_loss_pips, risk_percent)
            
            print(f"\n📊 ERGEBNIS:")
            print(f"Symbol: {symbol}")
            print(f"Stop Loss: {stop_loss_pips} Pips")
            print(f"Risiko: {risk_percent}%")
            print(f"Empfohlene Lot Size: {calculated_size}")
            
        except ValueError:
            print("❌ Ungültige Eingabe")
        except Exception as e:
            print(f"❌ Fehler: {e}")
    
    def show_daily_stats(self):
        """Zeigt Tagesstatistiken"""
        print("\n📈 TAGESSTATISTIKEN")
        print("─" * 25)
        
        summary = self.risk_manager.get_risk_summary()
        
        print(f"Tages P&L: {summary.get('daily_pnl', 0):.2f}€")
        print(f"Trades heute: {summary.get('trades_today', 0)}")
        print(f"Offene Positionen: {summary.get('open_positions', 0)}")
        print(f"Account Balance: {summary.get('account_balance', 0):.2f}€")
        print(f"Margin Level: {summary.get('margin_level', 0):.1f}%")
    
    def reset_risk_settings(self):
        """Risk Settings zurücksetzen"""
        confirm = input("Risk Settings auf Standard zurücksetzen? (ja/nein): ")
        if confirm.lower() == "ja":
            self.risk_manager = RiskManager(logger=self.logger)
            print("✅ Risk Settings zurückgesetzt")
        else:
            print("ℹ️ Keine Änderungen vorgenommen")

    def request_companion_analysis(self, symbol):
        """Führt eine erweiterte Analyse mit dem Trading Companion durch"""
        if not self.companion_enabled:
            print("❌ Trading Companion nicht aktiv")
            return
        try:
            if not self.companion_process or self.companion_process.poll() is not None:
                print("❌ Trading Companion nicht verfügbar")
                return
            print(f"🔄 Starte erweiterte Analyse für {symbol}...")
            # Hier könnte die Kommunikation mit dem Companion implementiert werden
            rsi_value = self.calculate_rsi(symbol)
            sr_data = self.calculate_support_resistance(symbol)
            print("\n📊 ERWEITERTE ANALYSE:")
            print("─" * 40)
            if rsi_value:
                signal, desc = self.get_rsi_signal(rsi_value)
                print(f"📈 RSI: {rsi_value} - {desc}")
            if sr_data:
                if sr_data['nearest_support']:
                    level, strength = sr_data['nearest_support']
                    print(f"🔵 Support: {level:.5f} (Stärke: {strength})")
                if sr_data['nearest_resistance']:
                    level, strength = sr_data['nearest_resistance']
                    print(f"🔴 Resistance: {level:.5f} (Stärke: {strength})")
            print("─" * 40)
        except Exception as e:
            print(f"❌ Analyse-Fehler: {e}")

    def sr_settings_menu(self):
        """Support/Resistance Einstellungen Menü"""
        while True:
            print("\n📊 SUPPORT/RESISTANCE EINSTELLUNGEN")
            print("─" * 40)
            print(f"Lookback Periode: {self.sr_lookback_period}")
            print(f"Min. Berührungen: {self.sr_min_touches}")
            print(f"Toleranz: {self.sr_tolerance}")
            print(f"Stärke Schwelle: {self.sr_strength_threshold}")
            print("\n1. Lookback Periode ändern")
            print("2. Min. Berührungen ändern")
            print("3. Toleranz ändern")
            print("4. Stärke Schwelle ändern")
            print("5. Zurück")
            choice = input("\nWählen (1-5): ").strip()
            if choice == "1":
                try:
                    new_period = int(input(f"Lookback Periode (aktuell {self.sr_lookback_period}): "))
                    if 20 <= new_period <= 200:
                        self.sr_lookback_period = new_period
                        print("✅ Lookback Periode aktualisiert")
                    else:
                        print("❌ Periode muss zwischen 20 und 200 liegen")
                except ValueError:
                    print("❌ Ungültige Eingabe")
            elif choice == "2":
                try:
                    new_touches = int(input(f"Min. Berührungen (aktuell {self.sr_min_touches}): "))
                    if 1 <= new_touches <= 5:
                        self.sr_min_touches = new_touches
                        print("✅ Min. Berührungen aktualisiert")
                    else:
                        print("❌ Wert muss zwischen 1 und 5 liegen")
                except ValueError:
                    print("❌ Ungültige Eingabe")
            elif choice == "3":
                try:
                    new_tolerance = float(input(f"Toleranz in Pips (aktuell {self.sr_tolerance*10000:.1f}): ")) / 10000
                    if 0.0001 <= new_tolerance <= 0.001:
                        self.sr_tolerance = new_tolerance
                        print("✅ Toleranz aktualisiert")
                    else:
                        print("❌ Toleranz muss zwischen 1 und 10 Pips liegen")
                except ValueError:
                    print("❌ Ungültige Eingabe")
            elif choice == "4":
                try:
                    new_threshold = int(input(f"Stärke Schwelle (aktuell {self.sr_strength_threshold}): "))
                    if 2 <= new_threshold <= 5:
                        self.sr_strength_threshold = new_threshold
                        print("✅ Stärke Schwelle aktualisiert")
                    else:
                        print("❌ Wert muss zwischen 2 und 5 liegen")
                except ValueError:
                    print("❌ Ungültige Eingabe")
            elif choice == "5":
                break

    def print_loading_animation(text, duration=2):
        """Zeigt eine schöne Lade-Animation"""
        import time
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        end_time = time.time() + duration
        
        while time.time() < end_time:
            for frame in frames:
                print(f"\r{frame} {text}", end="", flush=True)
                time.sleep(0.1)
                if time.time() >= end_time:
                    break
        
        print(f"\r✅ {text} - Abgeschlossen!    ")

    def calculate_support_resistance(self, symbol, timeframe=None, lookback=None):
        """Erkennt Support und Resistance Level"""
        if not self.mt5_connected:
            return None
        
        try:
            if timeframe is None:
                timeframe = self.rsi_timeframe
            if lookback is None:
                lookback = self.sr_lookback_period
            
            # Hole historische Daten
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
            
            if rates is None or len(rates) < 20:
                return None
            
            highs = np.array([rate['high'] for rate in rates])
            lows = np.array([rate['low'] for rate in rates])
            closes = np.array([rate['close'] for rate in rates])
            
            # Finde lokale Maxima (Resistance) und Minima (Support)
            resistance_levels = []
            support_levels = []
            
            # Suche nach Pivot Points
            for i in range(2, len(highs) - 2):
                # Resistance: Lokales Maximum
                if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                    highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                    resistance_levels.append(highs[i])
                
                # Support: Lokales Minimum
                if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                    lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                    support_levels.append(lows[i])
            
            # Gruppiere ähnliche Levels
            def group_levels(levels, tolerance):
                if not levels:
                    return []
                
                grouped = []
                levels_sorted = sorted(levels)
                
                current_group = [levels_sorted[0]]
                
                for level in levels_sorted[1:]:
                    if abs(level - current_group[-1]) <= tolerance:
                        current_group.append(level)
                    else:
                        # Berechne Durchschnitt der Gruppe
                        avg_level = sum(current_group) / len(current_group)
                        strength = len(current_group)
                        grouped.append((avg_level, strength))
                        current_group = [level]
                
                # Letzte Gruppe hinzufügen
                if current_group:
                    avg_level = sum(current_group) / len(current_group)
                    strength = len(current_group)
                    grouped.append((avg_level, strength))
                
                return grouped
            
            # Gruppiere Levels
            tolerance = self.sr_tolerance
            grouped_resistance = group_levels(resistance_levels, tolerance)
            grouped_support = group_levels(support_levels, tolerance)
            
            # Filtere nach Mindest-Stärke
            strong_resistance = [(level, strength) for level, strength in grouped_resistance 
                               if strength >= self.sr_strength_threshold]
            strong_support = [(level, strength) for level, strength in grouped_support 
                            if strength >= self.sr_strength_threshold]
            
            # Sortiere nach Stärke
            strong_resistance.sort(key=lambda x: x[1], reverse=True)
            strong_support.sort(key=lambda x: x[1], reverse=True)
            
            current_price = closes[-1]
            
            # Finde nächste Support/Resistance Levels
            nearest_resistance = None
            nearest_support = None
            
            for level, strength in strong_resistance:
                if level > current_price:
                    if nearest_resistance is None or level < nearest_resistance[0]:
                        nearest_resistance = (level, strength)
            
            for level, strength in strong_support:
                if level < current_price:
                    if nearest_support is None or level > nearest_support[0]:
                        nearest_support = (level, strength)
            
            return {
                'current_price': current_price,
                'nearest_resistance': nearest_resistance,
                'nearest_support': nearest_support,
                'all_resistance': strong_resistance[:5],  # Top 5
                'all_support': strong_support[:5]  # Top 5
            }
            
        except Exception as e:
            print(f"S/R Berechnung Fehler: {e}")
            return None
    
    def get_sr_signal(self, sr_data, current_price):
        """Interpretiert Support/Resistance für Trading-Signal"""
        if not sr_data:
            return "NEUTRAL", "S/R nicht verfügbar"
        
        try:
            signals = []
            
            # Prüfe Nähe zu Support
            if sr_data['nearest_support']:
                support_level, support_strength = sr_data['nearest_support']
                distance_to_support = abs(current_price - support_level) / current_price * 100
                
                if distance_to_support < 0.1:  # Sehr nah an Support
                    signals.append(f"BUY - An starkem Support ({support_level:.5f}, Stärke: {support_strength})")
                elif distance_to_support < 0.2:
                    signals.append(f"WATCH - Nahe Support ({support_level:.5f})")
            
            # Prüfe Nähe zu Resistance
            if sr_data['nearest_resistance']:
                resistance_level, resistance_strength = sr_data['nearest_resistance']
                distance_to_resistance = abs(current_price - resistance_level) / current_price * 100
                
                if distance_to_resistance < 0.1:  # Sehr nah an Resistance
                    signals.append(f"SELL - An starker Resistance ({resistance_level:.5f}, Stärke: {resistance_strength})")
                elif distance_to_resistance < 0.2:
                    signals.append(f"WATCH - Nahe Resistance ({resistance_level:.5f})")
            
            if not signals:
                return "NEUTRAL", "Zwischen S/R Levels"
            
            # Bestimme stärkstes Signal
            if any("BUY" in signal for signal in signals):
                buy_signals = [s for s in signals if "BUY" in s]
                return "BUY", buy_signals[0]
            elif any("SELL" in signal for signal in signals):
                sell_signals = [s for s in signals if "SELL" in s]
                return "SELL", sell_signals[0]
            else:
                return "WATCH", signals[0]
                
        except Exception as e:
            return "NEUTRAL", f"S/R Analyse Fehler: {e}"
    
    def calculate_rsi(self, symbol, timeframe=None, period=None):
        """Berechnet RSI für ein Symbol"""
        if not self.mt5_connected:
            return None
        
        try:
            if timeframe is None:
                timeframe = self.rsi_timeframe
            if period is None:
                period = self.rsi_period
            
            # Hole historische Daten (mehr als RSI-Periode für bessere Berechnung)
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 10)
            
            if rates is None or len(rates) < period + 1:
                return None
            
            # Extrahiere Schlusskurse
            closes = np.array([rate['close'] for rate in rates])
            
            # Berechne Preisänderungen
            deltas = np.diff(closes)
            
            # Trenne Gewinne und Verluste
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            # Berechne Average Gain und Average Loss
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                return 100
            
            # RSI Formel
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
            
        except Exception as e:
            print(f"RSI Berechnung Fehler: {e}")
            return None
    
    def get_rsi_signal(self, rsi_value):
        """Interpretiert RSI-Wert für Trading-Signal"""
        if rsi_value is None:
            return "NEUTRAL", "RSI nicht verfügbar"
        
        if rsi_value >= self.rsi_overbought:
            return "SELL", f"Überkauft (RSI: {rsi_value})"
        elif rsi_value <= self.rsi_oversold:
            return "BUY", f"Überverkauft (RSI: {rsi_value})"
        elif rsi_value > 60:
            return "NEUTRAL", f"Leicht überkauft (RSI: {rsi_value})"
        elif rsi_value < 40:
            return "NEUTRAL", f"Leicht überverkauft (RSI: {rsi_value})"
        else:
            return "NEUTRAL", f"Neutral (RSI: {rsi_value})"
        """Berechnet RSI für ein Symbol"""
        if not self.mt5_connected:
            return None
        
        try:
            if timeframe is None:
                timeframe = self.rsi_timeframe
            if period is None:
                period = self.rsi_period
            
            # Hole historische Daten (mehr als RSI-Periode für bessere Berechnung)
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 10)
            
            if rates is None or len(rates) < period + 1:
                return None
            
            # Extrahiere Schlusskurse
            closes = np.array([rate['close'] for rate in rates])
            
            # Berechne Preisänderungen
            deltas = np.diff(closes)
            
            # Trenne Gewinne und Verluste
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            # Berechne Average Gain und Average Loss
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                return 100
            
            # RSI Formel
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
            
        except Exception as e:
            print(f"RSI Berechnung Fehler: {e}")
            return None

    def connect_mt5(self):
        if not MT5_AVAILABLE:
            print("MT5 nicht verfügbar")
            return False
        
        try:
            print("Verbinde zu MT5...")
            if not mt5.initialize():
                print("MT5 nicht initialisiert")
                return False
            
            account_info = mt5.account_info()
            if account_info is None:
                print("Keine Account-Info")
                return False
            
            print(f"MT5 verbunden: {account_info.company}")
            self.mt5_connected = True
            return True
            
        except Exception as e:
            print(f"MT5 Fehler: {e}")
            return False
    
    def disconnect_mt5(self):
        if MT5_AVAILABLE and self.mt5_connected:
            mt5.shutdown()
            print("MT5 getrennt")
            self.mt5_connected = False
    
    def get_mt5_live_data(self, symbol):
        if not self.mt5_connected:
            return "MT5 nicht verbunden"
    
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return f"Symbol {symbol} nicht gefunden"
        
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return f"Keine Tick-Daten für {symbol}"
        
            current_price = (tick.bid + tick.ask) / 2
            spread = tick.ask - tick.bid
        
            # RSI berechnen
            rsi_value = self.calculate_rsi(symbol)
            rsi_signal, rsi_desc = self.get_rsi_signal(rsi_value)
        
            # MACD berechnen
            macd_data = self.calculate_macd(symbol)
            macd_signal, macd_desc = self.get_macd_signal(macd_data)
        
            # Support/Resistance berechnen
            sr_data = self.calculate_support_resistance(symbol)
            sr_signal, sr_desc = self.get_sr_signal(sr_data, current_price)
        
            rsi_info = f"RSI: {rsi_desc}" if rsi_value else "RSI: Nicht verfügbar"
            macd_info = f"MACD: {macd_desc}" if macd_data else "MACD: Nicht verfügbar"
            sr_info = f"S/R: {sr_desc}"
        
            # Formatiere S/R Levels für Anzeige
            sr_levels_info = ""
            if sr_data:
                if sr_data['nearest_support']:
                    level, strength = sr_data['nearest_support']
                    distance = abs(current_price - level) / current_price * 10000  # in Pips
                    sr_levels_info += f"\nSupport: {level:.5f} (Stärke: {strength}, {distance:.1f} Pips)"
            
                if sr_data['nearest_resistance']:
                    level, strength = sr_data['nearest_resistance']
                    distance = abs(current_price - level) / current_price * 10000  # in Pips
                    sr_levels_info += f"\nResistance: {level:.5f} (Stärke: {strength}, {distance:.1f} Pips)"
        
            # Formatiere MACD Details für Anzeige
            macd_details_info = ""
            if macd_data:
                macd_details_info += f"\nMACD Line: {macd_data['macd']:.6f}"
                macd_details_info += f"\nSignal Line: {macd_data['signal']:.6f}"
                macd_details_info += f"\nHistogram: {macd_data['histogram']:.6f}"
                macd_details_info += f"\nTrend: {macd_data['histogram_trend']}"
        
            return f"""
    MT5 LIVE-DATEN für {symbol}:
    Bid/Ask: {tick.bid:.5f} / {tick.ask:.5f}
    Preis: {current_price:.5f}
    Spread: {spread:.5f}
    {rsi_info}
    RSI-Signal: {rsi_signal}
    {macd_info}
    MACD-Signal: {macd_signal}{macd_details_info}
    {sr_info}
    S/R-Signal: {sr_signal}{sr_levels_info}
    Stand: {datetime.fromtimestamp(tick.time).strftime('%H:%M:%S')}
    """
        
        except Exception as e:
            return f"Daten-Fehler: {e}"
    
    def check_ollama_status(self):
        """Überprüft die Verfügbarkeit des Ollama-Servers"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print("Ollama läuft")
                return True
            print("Ollama nicht erreichbar")
            return False
        except Exception as e:
            print(f"Ollama-Verbindungsfehler: {e}")
            return False
    
    def get_available_models(self):
        try:
            response = requests.get(f"{self.ollama_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                self.available_models = [model['name'] for model in data.get('models', [])]
                print(f"{len(self.available_models)} Modelle gefunden")
                return True
            return False
        except Exception as e:
            print(f"Modell-Fehler: {e}")
            return False
    
    def mtf_settings_menu(self):
        """Multi-Timeframe Einstellungen Menü"""

        # Timeframe-Namen für Anzeige
        def get_timeframe_name(timeframe):
            timeframe_names = {
                mt5.TIMEFRAME_M1: "M1",
                mt5.TIMEFRAME_M5: "M5", 
                mt5.TIMEFRAME_M15: "M15",
                mt5.TIMEFRAME_M30: "M30",
                mt5.TIMEFRAME_H1: "H1",
                mt5.TIMEFRAME_H4: "H4",
                mt5.TIMEFRAME_D1: "D1"
            }

            trend_tf_name = timeframe_names.get(self.trend_timeframe, f"Unbekannt ({self.trend_timeframe})")
            entry_tf_name = timeframe_names.get(self.entry_timeframe, f"Unbekannt ({self.entry_timeframe})")

            return timeframe_names.get(timeframe, f"Unbekannt ({timeframe})")

        while True:
            print("\n📈 MULTI-TIMEFRAME EINSTELLUNGEN")
            print("─" * 40)
            print(f"Status: {'✅ Aktiviert' if self.mtf_enabled else '❌ Deaktiviert'}")
            print(f"Trend-Timeframe: {get_timeframe_name(self.trend_timeframe)}")
            print(f"Entry-Timeframe: {get_timeframe_name(self.entry_timeframe)}")
            print(f"EMA Periode: {self.trend_ema_period}")
            print(f"Trend-Stärke Schwelle: {self.trend_strength_threshold}")
            print(f"Trend-Bestätigung erforderlich: {'✅' if self.require_trend_confirmation else '❌'}")
        
        
            print("\n1. Ein/Ausschalten")
            print("2. Trend-Timeframe ändern")
            print("3. Entry-Timeframe ändern")
            print("4. EMA Periode ändern")
            print("5. Trend-Stärke Schwelle ändern")
            print("6. Trend-Bestätigung ein/aus")
            print("7. Trend-Test")
            print("8. Zurück")
        
            choice = input("\nWählen (1-8): ").strip()
        
            if choice == "1":
                old_status = self.mtf_enabled
                self.mtf_enabled = not self.mtf_enabled
                status = "aktiviert" if self.mtf_enabled else "deaktiviert"
                self.log("INFO", f"Multi-Timeframe {status}", "SETTINGS")
                print(f"Multi-Timeframe {status}")
        
            elif choice == "2":
                print("\nTrend-Timeframe:")
                print("1. M30 (30 Minuten)")
                print("2. H1 (1 Stunde)")
                print("3. H4 (4 Stunden)")
                print("4. D1 (1 Tag)")
            
                tf_choice = input("Wählen (1-4): ").strip()
            
                timeframes = {
                    "1": mt5.TIMEFRAME_M30,
                    "2": mt5.TIMEFRAME_H1,
                    "3": mt5.TIMEFRAME_H4,
                    "4": mt5.TIMEFRAME_D1
                }
            
                if tf_choice in timeframes:
                    old_tf = self.trend_timeframe
                    self.trend_timeframe = timeframes[tf_choice]
                    tf_names = {"1": "M30", "2": "H1", "3": "H4", "4": "D1"}
                    self.log("INFO", f"Trend-Timeframe geändert zu {tf_names[tf_choice]}", "SETTINGS")
                    print(f"Trend-Timeframe auf {tf_names[tf_choice]} gesetzt")
                else:
                    print("Ungültige Auswahl")
        
            elif choice == "3":
                print("\nEntry-Timeframe:")
                print("1. M1 (1 Minute)")
                print("2. M5 (5 Minuten)")
                print("3. M15 (15 Minuten)")
                print("4. M30 (30 Minuten)")
            
                tf_choice = input("Wählen (1-4): ").strip()
            
                timeframes = {
                    "1": mt5.TIMEFRAME_M1,
                    "2": mt5.TIMEFRAME_M5,
                    "3": mt5.TIMEFRAME_M15,
                    "4": mt5.TIMEFRAME_M30
                }
            
                if tf_choice in timeframes:
                    old_tf = self.entry_timeframe
                    self.entry_timeframe = timeframes[tf_choice]
                    tf_names = {"1": "M1", "2": "M5", "3": "M15", "4": "M30"}
                    self.log("INFO", f"Entry-Timeframe geändert zu {tf_names[tf_choice]}", "SETTINGS")
                    print(f"Entry-Timeframe auf {tf_names[tf_choice]} gesetzt")
                else:
                    print("Ungültige Auswahl")
        
            elif choice == "4":
                try:
                    old_period = self.trend_ema_period
                    new_period = int(input(f"EMA Periode (aktuell {self.trend_ema_period}): "))
                    if 20 <= new_period <= 200:
                        self.trend_ema_period = new_period
                        self.log("INFO", f"Trend EMA Periode: {old_period} -> {new_period}", "SETTINGS")
                        print(f"EMA Periode auf {new_period} gesetzt")
                    else:
                        print("EMA Periode muss zwischen 20 und 200 liegen")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "5":
                try:
                    old_threshold = self.trend_strength_threshold
                    new_threshold = float(input(f"Trend-Stärke Schwelle (aktuell {self.trend_strength_threshold}): "))
                    if 0.0001 <= new_threshold <= 0.01:
                        self.trend_strength_threshold = new_threshold
                        self.log("INFO", f"Trend-Stärke Schwelle: {old_threshold} -> {new_threshold}", "SETTINGS")
                        print(f"Trend-Stärke Schwelle auf {new_threshold} gesetzt")
                    else:
                        print("Schwelle muss zwischen 0.0001 und 0.01 liegen")
                except ValueError:
                    print("Ungültige Eingabe")
        
            elif choice == "6":
                old_status = self.require_trend_confirmation
                self.require_trend_confirmation = not self.require_trend_confirmation
                status = "aktiviert" if self.require_trend_confirmation else "deaktiviert"
                self.log("INFO", f"Trend-Bestätigung {status}", "SETTINGS")
                print(f"Trend-Bestätigung {status}")
        
            elif choice == "7":
                if self.mtf_enabled:
                    symbol = input("Symbol für Trend-Test: ").upper()
                    if symbol:
                        self.log("INFO", f"Trend-Test gestartet für {symbol}", "ANALYSIS")
                        trend_data = self.get_higher_timeframe_trend(symbol)
                        if trend_data:
                            print(f"\n{symbol} Trend-Analyse:")
                            print(f"Richtung: {trend_data['direction']}")
                            print(f"Stärke: {trend_data['strength']:.6f}")
                            print(f"Qualität: {trend_data['quality']}")
                            print(f"EMA Level: {trend_data['ema_level']:.5f}")
                            print(f"Preis über EMA: {trend_data['price_above_ema']}")
                            print(f"EMA steigend: {trend_data['ema_rising']}")
                            print(f"Momentum: {trend_data['momentum_direction']}")
                        else:
                            print("Trend-Analyse fehlgeschlagen")
                else:
                    print("Multi-Timeframe ist deaktiviert")
        
            elif choice == "8":
                break
        
            else:
                print("Ungültige Auswahl")
        
            input("\nDrücken Sie Enter zum Fortfahren...")

    def select_finance_model(self):
        finance_models = ["fingpt", "llama3.1:8b", "llama3.2:3b", "mistral:7b"]
        
        for model in finance_models:
            if any(model in available for available in self.available_models):
                self.selected_model = next(m for m in self.available_models if model in m)
                print(f"Modell: {self.selected_model}")
                return True
        
        if self.available_models:
            self.selected_model = self.available_models[0]
            print(f"Standard: {self.selected_model}")
            return True
        return False
    
    def chat_with_model(self, message, context=""):
        if not self.selected_model:
            return "Kein Modell"
        
        system_prompt = f"""Du bist FinGPT für Trading-Analyse mit RSI- und Support/Resistance-Integration.

LIVE-DATEN:
{context}

Berücksichtige bei deiner Analyse:
- RSI-Werte und Signale
- Überkauft/Überverkauft Zonen
- RSI-Divergenzen
- Support und Resistance Levels
- Stärke der S/R Levels
- Abstand zu wichtigen S/R Levels
- Breakout-Potential

Gib klare Trading-Empfehlungen:
- BUY/SELL/WARTEN
- Entry-Preis
- Stop-Loss (unter Support/über Resistance)
- Take-Profit (an nächstem S/R Level)
- RSI- und S/R-Begründung

Antworte auf Deutsch und konkret."""
        
        try:
            payload = {
                "model": self.selected_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "stream": False,
                "options": {"temperature": 0.3}
            }
            
            response = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=60)
            
            if response.status_code == 200:
                return response.json()['message']['content']
            return f"KI-Fehler: {response.status_code}"
                
        except Exception as e:
            return f"Chat-Fehler: {e}"
    
    def enable_trading(self):
        print("\nTRADING AKTIVIEREN")
        print("Echte Trades möglich!")
        
        confirm = input("Trading aktivieren? (ja/nein): ")
        if confirm.lower() != "ja":
            return False
        
        account_info = mt5.account_info()
        if account_info and "demo" not in account_info.server.lower():
            print("LIVE-ACCOUNT!")
            confirm2 = input("LIVE-Trading bestätigen (JA): ")
            if confirm2 != "JA":
                return False
        
        self.trading_enabled = True
        print("Trading aktiviert!")
        return True
    
    def execute_trade(self, symbol, action, lot_size=None, stop_loss=None, take_profit=None):
        """Verbesserte execute_trade Methode mit Risk Management"""
        if not self.trading_enabled:
            return "Trading deaktiviert"
        
        try:
            # Symbol und Tick Info holen
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return f"Symbol {symbol} nicht verfügbar"
            
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return f"Keine Preise für {symbol}"
            
            # Standard Lot Size
            if lot_size is None:
                lot_size = self.default_lot_size
            
            # RISK MANAGEMENT CHECK
            can_trade, reason = self.risk_manager.can_open_position(symbol, action, lot_size)
            if not can_trade:
                self.log("WARNING", f"Trade abgelehnt: {reason}", "RISK")
                return f"❌ Trade abgelehnt: {reason}"
            
            # Automatische Position Size Berechnung falls gewünscht
            if stop_loss:
                current_price = tick.ask if action.upper() == "BUY" else tick.bid
                sl_distance_pips = abs(current_price - stop_loss) / symbol_info.point
                if symbol_info.digits == 3 or symbol_info.digits == 5:
                    sl_distance_pips /= 10
                
                # Berechne optimale Lot Size
                optimal_lot_size = self.risk_manager.calculate_position_size(symbol, sl_distance_pips)
                lot_size = min(lot_size, optimal_lot_size)  # Nimm das kleinere
                
                self.log("INFO", f"Optimierte Lot Size: {optimal_lot_size}, Verwendete: {lot_size}", "RISK")
            
            if action.upper() == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
                # ... deine SL/TP Logik ...
            elif action.upper() == "SELL":
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
                # ... deine SL/TP Logik ...
            else:
                return f"Ungültige Aktion: {action}"
            
            # Trade Request erstellen
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "FinGPT+Risk",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            if stop_loss and stop_loss > 0:
                request["sl"] = round(stop_loss, 5)
            
            if take_profit and take_profit > 0:
                request["tp"] = round(take_profit, 5)
            
            print(f"{action} {lot_size} {symbol} @ {price:.5f}")
            
            # Trade ausführen
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                success_msg = f"✅ {action} {lot_size} {symbol} @ {price:.5f} (#{result.order})"
                
                # Trade beim Risk Manager registrieren
                self.risk_manager.register_trade(symbol, action, lot_size, "SUCCESS")
                
                return success_msg
            else:
                error_msg = f"❌ Trade failed: {result.retcode} - {result.comment}"
                self.risk_manager.register_trade(symbol, action, lot_size, "FAILED")
                return error_msg
                
        except Exception as e:
            error_msg = f"Trade-Fehler: {e}"
            self.log_error("execute_trade", e)
            return error_msg
    
    def partial_close_position(self, position, close_percentage):
        try:
            close_volume = round(position.volume * (close_percentage / 100), 2)
            
            symbol_info = mt5.symbol_info(position.symbol)
            if close_volume < symbol_info.volume_min:
                print(f"Volumen zu klein: {close_volume}")
                return False
            
            remaining_volume = round(position.volume - close_volume, 2)
            if remaining_volume < symbol_info.volume_min:
                print("Schließe komplette Position")
                close_volume = position.volume
            
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": close_volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "deviation": 20,
                "magic": 234000,
                "comment": f"Partial Close {close_percentage}%"
            }
            
            result = mt5.order_send(close_request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"{close_percentage}% geschlossen ({close_volume} Lots)")
                return True
            else:
                print(f"Partial Close fehlgeschlagen: {result.comment}")
                return False
                
        except Exception as e:
            print(f"Partial Close Fehler: {e}")
            return False
    
    def manage_open_positions(self):
        try:
            positions = mt5.positions_get()
            if not positions:
                print("Keine offenen Positionen")
                return
        
            print(f"Position Management - {len(positions)} Positionen")
        
            for position in positions:
                if position.price_open > 0:
                    profit_percent = (position.profit / (position.price_open * position.volume * 1000)) * 100
                
                    print(f"{position.symbol}: {profit_percent:+.1f}% P&L")
                
                    # Partial Close Logik
                    if profit_percent >= self.profit_target_1 and profit_percent < self.profit_target_2:
                        if position.volume > self.default_lot_size * 0.8:
                            print(f"Target 1 erreicht für {position.symbol}")
                            self.partial_close_position(position, self.first_target_percent)
                
                    elif profit_percent >= self.profit_target_2:
                        if position.volume > self.default_lot_size * 0.4:
                            print(f"Target 2 erreicht für {position.symbol}")
                            self.partial_close_position(position, self.second_target_percent)
        
            # Trailing Stop Update nach Partial Close Prüfung
            if self.trailing_stop_enabled:
                print("Aktualisiere Trailing Stops...")
                self.update_trailing_stops()
                        
        except Exception as e:
            print(f"Position Management Fehler: {e}")
    
    def get_open_positions(self):
        if not self.mt5_connected:
            return "MT5 nicht verbunden"
        
        try:
            positions = mt5.positions_get()
            if not positions:
                return "Keine offenen Positionen"
            
            result = "OFFENE POSITIONEN:\n\n"
            total = 0
            
            for pos in positions:
                emoji = "🟢" if pos.profit > 0 else "🔴"
                type_str = "BUY" if pos.type == 0 else "SELL"
                result += f"{emoji} {pos.symbol} {type_str} {pos.volume} | P&L: {pos.profit:.2f}\n"
                total += pos.profit
            
            emoji = "🟢" if total > 0 else "🔴"
            result += f"\n{emoji} GESAMT: {total:.2f}"
            return result
            
        except Exception as e:
            return f"Position-Fehler: {e}"
    
    def enable_auto_trading(self):
        if not self.trading_enabled:
            print("Erst Trading aktivieren!")
            return False
        
        print("\nVOLLAUTOMATISCHES TRADING")
        print("EXTREM RISKANT!")
        
        confirm1 = input("Auto-Trading aktivieren? (GEFÄHRLICH/nein): ")
        if confirm1 != "GEFÄHRLICH":
            return False
        
        confirm2 = input("Risiko verstanden? (ICH_VERSTEHE): ")
        if confirm2 != "ICH_VERSTEHE":
            return False
        
        symbols = input("Symbole (z.B. EURUSD,GBPUSD): ")
        if symbols:
            self.auto_trade_symbols = [s.strip().upper() for s in symbols.split(',')]
        
        interval = input(f"Intervall Sekunden ({self.analysis_interval}): ")
        if interval:
            self.analysis_interval = int(interval)
        
        self.auto_trading = True
        print("Auto-Trading aktiviert!")
        return True
    
    def extract_trade_reasoning(self, ai_response):
        """Extrahiert die Begründung aus der KI-Antwort"""
        try:
            # Suche nach Schlüsselwörtern für Begründungen
            response_lower = ai_response.lower()
            
            reasoning_keywords = [
                'weil', 'aufgrund', 'da', 'durch', 'grund', 'indikator', 'signal',
                'trend', 'support', 'resistance', 'breakout', 'momentum', 'rsi',
                'macd', 'bollinger', 'fibonacci', 'chart', 'pattern', 'formation',
                'überkauft', 'überverkauft', 'overbought', 'oversold', 'widerstand',
                'unterstützung', 'durchbruch', 'prallte', 'bounce', 'rejection'
            ]
            
            # Finde Sätze mit Begründungen
            sentences = ai_response.split('.')
            reasoning_parts = []
            
            for sentence in sentences:
                sentence_lower = sentence.strip().lower()
                if any(keyword in sentence_lower for keyword in reasoning_keywords):
                    # Bereinige und kürze den Satz
                    clean_sentence = sentence.strip()
                    if len(clean_sentence) > 100:
                        clean_sentence = clean_sentence[:97] + "..."
                    reasoning_parts.append(clean_sentence)
            
            if reasoning_parts:
                return " | ".join(reasoning_parts[:2])  # Max 2 Begründungen
            
            # Fallback: Versuche generische Begründung zu finden
            if "buy" in response_lower or "kaufen" in response_lower:
                if "support" in response_lower or "unterstützung" in response_lower:
                    return "Support-Level als Kaufgelegenheit"
                elif "rsi" in response_lower:
                    return "RSI-basierte Kaufgelegenheit"
                elif "trend" in response_lower:
                    return "Aufwärtstrend erkannt"
                elif "breakout" in response_lower or "durchbruch" in response_lower:
                    return "Breakout über Resistance"
                elif "signal" in response_lower:
                    return "Bullisches Signal"
                else:
                    return "Positive Marktbewertung"
            
            elif "sell" in response_lower or "verkaufen" in response_lower:
                if "resistance" in response_lower or "widerstand" in response_lower:
                    return "Resistance-Level als Verkaufsgelegenheit"
                elif "rsi" in response_lower:
                    return "RSI-basierte Verkaufsgelegenheit"
                elif "trend" in response_lower:
                    return "Abwärtstrend erkannt"
                elif "breakout" in response_lower or "durchbruch" in response_lower:
                    return "Breakdown unter Support"
                elif "signal" in response_lower:
                    return "Bearisches Signal"
                else:
                    return "Negative Marktbewertung"
            
            return "KI-Empfehlung basiert auf technischer Analyse"
            
        except Exception:
            return "KI-Analyse durchgeführt"
    
    def extract_recommendation_summary(self, ai_response):
        """Extrahiert eine kurze Zusammenfassung der KI-Empfehlung"""
        try:
            lines = ai_response.split('\n')
            for line in lines:
                line_upper = line.upper().strip()
                if any(word in line_upper for word in ['BUY', 'SELL', 'KAUFEN', 'VERKAUFEN', 'WARTEN', 'HOLD']):
                    return line.strip()[:100]  # Erste 100 Zeichen der Empfehlung
            return ai_response[:100]  # Fallback
        except:
            return "KI-Analyse durchgeführt"

    def display_formatted_analysis(self, symbol, ai_response, live_data):
        """Zeigt die KI-Analyse übersichtlich und mit Emojis formatiert an"""
    
        print("\n" + "═" * 60)
        print(f"🤖 KI-ANALYSE FÜR {symbol}")
        print("═" * 60)
    
        # Aktuelle Marktdaten kurz anzeigen
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                current_price = (tick.bid + tick.ask) / 2
                print(f"💱 Aktueller Preis: {current_price:.5f}")
                print(f"📊 Bid/Ask: {tick.bid:.5f} / {tick.ask:.5f}")
                print("─" * 60)
        except:
            pass
    
        # KI-Antwort strukturiert aufbereiten mit mehr Emojis
        formatted_response = self.format_ai_response_improved(ai_response)
        print(formatted_response)
    
        print("═" * 60)
    
        # Technische Indikatoren Zusammenfassung
        self.display_technical_summary(symbol)

    def format_ai_response(self, response):
        """Formatiert die KI-Antwort schöner"""
        try:
            # Entferne doppelte Leerzeilen und überflüssige Zeichen
            lines = [line.strip() for line in response.split('\n') if line.strip()]
        
            formatted = []
            current_section = ""
        
            for line in lines:
                # Erkenne Überschriften (mit ** oder Doppelpunkt)
                if ('**' in line or 
                    line.endswith(':') or 
                    any(keyword in line.upper() for keyword in ['EMPFEHLUNG', 'ANALYSE', 'BEGRÜNDUNG', 'SIGNAL'])):
                
                    if current_section:
                        formatted.append("")  # Leerzeile vor neuer Sektion
                
                    # Formatiere Überschrift
                    clean_line = line.replace('**', '').strip(':').strip()
                    formatted.append(f"📋 {clean_line.upper()}")
                    formatted.append("─" * 40)
                    current_section = clean_line
                
                else:
                    # Normaler Text mit Icons
                    if any(keyword in line.upper() for keyword in ['BUY', 'KAUFEN']):
                        formatted.append(f"🟢 {line}")
                    elif any(keyword in line.upper() for keyword in ['SELL', 'VERKAUFEN']):
                        formatted.append(f"🔴 {line}")
                    elif any(keyword in line.upper() for keyword in ['WARTEN', 'HOLD', 'NEUTRAL']):
                        formatted.append(f"🟡 {line}")
                    elif any(keyword in line.upper() for keyword in ['STOP', 'SL']):
                        formatted.append(f"🛑 {line}")
                    elif any(keyword in line.upper() for keyword in ['TAKE', 'TP', 'PROFIT']):
                        formatted.append(f"🎯 {line}")
                    elif any(keyword in line.upper() for keyword in ['ENTRY', 'PREIS', 'PRICE']):
                        formatted.append(f"💰 {line}")
                    else:
                        formatted.append(f"   {line}")
        
            return '\n'.join(formatted)
        
        except Exception as e:
            return f"🤖 {response}"  # Fallback bei Formatierungsfehlern

    def format_ai_response_improved(self, response):
        """Verbesserte Formatierung der KI-Antwort mit mehr Emojis und besserer Übersichtlichkeit"""
        try:
            # Entferne doppelte Leerzeilen und überflüssige Zeichen
            lines = [line.strip() for line in response.split('\n') if line.strip()]
        
            formatted = []
            current_section = ""
            section_number = 1
        
            # Überschrift für die verbesserte Formatierung
            formatted.append("✨ VERBESSERTE KI-ANALYSE")
            formatted.append("─" * 40)
        
            for line in lines:
                # Erkenne Überschriften (mit ** oder Doppelpunkt)
                if ('**' in line or 
                    line.endswith(':') or 
                    any(keyword in line.upper() for keyword in ['EMPFEHLUNG', 'ANALYSE', 'BEGRÜNDUNG', 'SIGNAL', 'EINSTIEG', 'STOP', 'TAKE'])):
                
                    if current_section:
                        formatted.append("")  # Leerzeile vor neuer Sektion
                
                    # Formatiere Überschrift mit Nummerierung
                    clean_line = line.replace('**', '').strip(':').strip()
                    section_icons = {
                        'HAUPTSIGNAL': '🎯',
                        'EMPFEHLUNG': '💡',
                        'EINSTIEG': '💰',
                        'ENTRY': '💰',
                        'STOP': '🛑',
                        'TAKE': '🎯',
                        'TP': '🎯',
                        'PROFIT': '🎯',
                        'BEGRÜNDUNG': '📝',
                        'ANALYSE': '🔍',
                        'SIGNAL': '📡'
                    }
                
                    # Wähle passendes Emoji für die Sektion
                    icon = '📌'
                    for keyword, emoji in section_icons.items():
                        if keyword in clean_line.upper():
                            icon = emoji
                            break
                
                    formatted.append(f"{icon} {section_number}. {clean_line.upper()}")
                    formatted.append("─" * 30)
                    current_section = clean_line
                    section_number += 1
                
                else:
                    # Normaler Text mit Icons und bessere Formatierung
                    if any(keyword in line.upper() for keyword in ['BUY', 'KAUFEN']):
                        formatted.append(f"🚀 {line}")
                    elif any(keyword in line.upper() for keyword in ['SELL', 'VERKAUFEN']):
                        formatted.append(f"🔻 {line}")
                    elif any(keyword in line.upper() for keyword in ['WARTEN', 'HOLD', 'NEUTRAL']):
                        formatted.append(f"⏸️ {line}")
                    elif any(keyword in line.upper() for keyword in ['STOP', 'SL']):
                        formatted.append(f"🛑 {line}")
                    elif any(keyword in line.upper() for keyword in ['TAKE', 'TP', 'PROFIT']):
                        formatted.append(f"🎯 {line}")
                    elif any(keyword in line.upper() for keyword in ['ENTRY', 'PREIS', 'PRICE']):
                        formatted.append(f"💰 {line}")
                    elif any(keyword in line.upper() for keyword in ['RSI']):
                        formatted.append(f"📊 {line}")
                    elif any(keyword in line.upper() for keyword in ['MACD']):
                        formatted.append(f"📈 {line}")
                    elif any(keyword in line.upper() for keyword in ['SUPPORT', 'RESISTANCE', 'S/R']):
                        formatted.append(f"📍 {line}")
                    elif any(keyword in line.upper() for keyword in ['TREND']):
                        formatted.append(f"🧭 {line}")
                    else:
                        # Füge Emojis für wichtige Schlüsselwörter hinzu
                        if 'WICHTIG' in line.upper() or 'KRITISCH' in line.upper():
                            formatted.append(f"❗ {line}")
                        elif 'VORSICHT' in line.upper() or 'RISIKO' in line.upper():
                            formatted.append(f"⚠️ {line}")
                        elif 'GUT' in line.upper() or 'STARK' in line.upper():
                            formatted.append(f"✅ {line}")
                        else:
                            formatted.append(f"💬 {line}")
        
            return '\n'.join(formatted)
        
        except Exception as e:
            return f"🤖 Fehler bei Formatierung: {e}\n\nOriginal:\n{response}"  # Fallback bei Formatierungsfehlern

    def display_technical_summary(self, symbol):
        """Zeigt eine übersichtliche technische Zusammenfassung mit Emojis"""
        try:
            print("\n📊 TECHNISCHE INDIKATOREN ZUSAMMENFASSUNG:")
            print("─" * 50)
        
            # RSI
            rsi_value = self.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, rsi_desc = self.get_rsi_signal(rsi_value)
                rsi_icon = "🚀" if rsi_signal == "BUY" else "🔻" if rsi_signal == "SELL" else "⏸️"
                print(f"{rsi_icon} RSI ({self.rsi_period}): {rsi_value:.1f} - {rsi_desc}")
        
            # MACD
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, macd_desc = self.get_macd_signal(macd_data)
                macd_icon = "📈" if macd_signal == "BUY" else "📉" if macd_signal == "SELL" else "⏸️"
                print(f"{macd_icon} MACD: {macd_data['macd']:.6f} - {macd_desc[:40]}...")
        
            # Support/Resistance
            sr_data = self.calculate_support_resistance(symbol)
            if sr_data:
                current_price = sr_data['current_price']
            
                if sr_data['nearest_support']:
                    sup_level, sup_strength = sr_data['nearest_support']
                    distance = abs(current_price - sup_level) / current_price * 10000
                    strength_icon = "💪" if sup_strength > 0.7 else "👍" if sup_strength > 0.4 else "⚠️"
                    print(f"🛡️ Nächster Support: {sup_level:.5f} ({distance:.1f} Pips) {strength_icon}")
            
                if sr_data['nearest_resistance']:
                    res_level, res_strength = sr_data['nearest_resistance']
                    distance = abs(current_price - res_level) / current_price * 10000
                    strength_icon = "💪" if res_strength > 0.7 else "👍" if res_strength > 0.4 else "⚠️"
                    print(f"🏔️ Nächste Resistance: {res_level:.5f} ({distance:.1f} Pips) {strength_icon}")
        
            # Multi-Timeframe Trend (falls aktiviert)
            if self.mtf_enabled:
                trend_data = self.get_higher_timeframe_trend(symbol)
                if trend_data:
                    trend_icon = "🚀" if "BULLISH" in trend_data['direction'] else "🔻" if "BEARISH" in trend_data['direction'] else "⏸️"
                    tf_name = self.timeframe_names.get(self.trend_timeframe, "H1")
                    print(f"{trend_icon} {tf_name} Trend: {trend_data['direction']} ({trend_data['quality']})")
        
            # Zusammenfassung
            print("─" * 50)
            print("📋 GESAMT-ZUSAMMENFASSUNG:")
            print("─" * 30)
            
            # Zähle BUY/SELL-Signale
            buy_signals = 0
            sell_signals = 0
            
            # RSI-Signal zählen
            if rsi_value:
                if rsi_signal == "BUY":
                    buy_signals += 1
                elif rsi_signal == "SELL":
                    sell_signals += 1
            
            # MACD-Signal zählen
            if macd_data:
                if macd_signal == "BUY":
                    buy_signals += 1
                elif macd_signal == "SELL":
                    sell_signals += 1
            
            # Trend-Signal zählen (falls aktiviert)
            trend_signal = None
            if self.mtf_enabled and trend_data:
                if "BULLISH" in trend_data['direction']:
                    buy_signals += 1
                    trend_signal = "BULLISH"
                elif "BEARISH" in trend_data['direction']:
                    sell_signals += 1
                    trend_signal = "BEARISH"
            
            # Gesamtaussage
            if buy_signals > sell_signals:
                overall_icon = "🚀"
                overall_signal = "STARKE KAUFEMPFEHLUNG"
            elif sell_signals > buy_signals:
                overall_icon = "🔻"
                overall_signal = "STARKE VERKAUFEMPFEHLUNG"
            else:
                overall_icon = "⏸️"
                overall_signal = "NEUTRALE MARKTLAGE"
            
            print(f"{overall_icon} {overall_signal}")
            print(f"📈 Kaufsignale: {buy_signals} | 📉 Verkaufsignale: {sell_signals}")
        
        except Exception as e:
            print(f"⚠️ Technische Zusammenfassung Fehler: {e}")

    def parse_ai_recommendation(self, ai_text):
        try:
            text_upper = ai_text.upper()
            
            action = None
            if "BUY" in text_upper or "KAUFEN" in text_upper:
                action = "BUY"
            elif "SELL" in text_upper or "VERKAUFEN" in text_upper:
                action = "SELL"
            elif "WARTEN" in text_upper or "HOLD" in text_upper:
                return None
            
            if not action:
                return None
            
            reasoning = self.extract_trade_reasoning(ai_text)
            
            return {
                "action": action,
                "reasoning": reasoning
            }
            
        except Exception:
            return None
    
    def auto_trade_cycle(self, symbol):
        """Verbesserte auto_trade_cycle mit korrigierter Variable-Reihenfolge"""
        try:
            # 1. ERST SYMBOL UND TICK INFO HOLEN - VOR ALLEN ANDEREN CHECKS!
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                print(f"{symbol}: Keine Marktdaten verfügbar")
                return False
            
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                print(f"{symbol}: Keine Tick-Daten verfügbar")
                return False

            # 2. JETZT ERST BASIS RISK CHECK
            can_trade, reason = self.risk_manager.can_open_position(symbol, "BUY", self.default_lot_size)
            if not can_trade:
                self.log("INFO", f"{symbol}: {reason}", "RISK")
                return False
    
            # 3. MULTI-TIMEFRAME TREND-FILTER
            if self.mtf_enabled and self.require_trend_confirmation:
                trend_data = self.get_higher_timeframe_trend(symbol)
                if not trend_data:
                    print(f"{symbol}: Trend-Analyse fehlgeschlagen")
                    return False
        
                trend_direction = trend_data['direction']
                trend_strength = trend_data['strength']
        
                # Trend-Filter anwenden
                if trend_direction == "NEUTRAL" or trend_strength < self.trend_strength_threshold:
                    print(f"{symbol}: Kein klarer Trend ({trend_direction}, Stärke: {trend_strength:.5f})")
                    return False
    
            # 4. LIVE-DATEN UND KI-ANALYSE
            live_data = self.get_mt5_live_data(symbol)
            if "Fehler" in live_data or "nicht" in live_data:
                print(f"{symbol}: Fehler beim Laden der Marktdaten")
                return False
            
            # RSI, MACD und S/R in Prompt erwähnen
            prompt = f"""Analysiere {symbol} für Trading-Entscheidung. 

    Berücksichtige besonders:
    - RSI-Wert und ob überkauft/überverkauft
    - MACD-Signale (Kreuzungen, Histogram, Nulllinie) 
    - Support/Resistance Levels und deren Stärke
    - Breakouts oder Bounces an S/R Levels
    - Trend-Richtung und Momentum

    Gib eine klare BUY/SELL/WARTEN Empfehlung mit kurzer technischer Begründung."""

            ai_response = self.chat_with_model(prompt, live_data)
            recommendation = self.parse_ai_recommendation(ai_response)
        
            if not recommendation:
                print(f"{symbol}: WARTEN")
                return False
            
            action = recommendation["action"]
            reasoning = recommendation.get("reasoning", "KI-Analyse")
    
            # 5. MULTI-TIMEFRAME BESTÄTIGUNG
            if self.mtf_enabled and self.require_trend_confirmation:
                if action == "BUY" and trend_direction == "BEARISH":
                    print(f"{symbol}: H1-Trend bearish - BUY abgelehnt")
                    return False
                elif action == "SELL" and trend_direction == "BULLISH":
                    print(f"{symbol}: H1-Trend bullish - SELL abgelehnt")
                    return False
    
            # 6. PRÜFE OB BEREITS POSITION OFFEN
            positions = mt5.positions_get(symbol=symbol)
            if positions:
                print(f"{symbol}: Position bereits offen")
                return False
            
            # 7. RSI-FILTER
            rsi_value = self.calculate_rsi(symbol)
            if rsi_value:
                if action == "BUY" and rsi_value > self.rsi_overbought:
                    print(f"{symbol}: RSI überkauft ({rsi_value}) - BUY abgelehnt")
                    return False
                elif action == "SELL" and rsi_value < self.rsi_oversold:
                    print(f"{symbol}: RSI überverkauft ({rsi_value}) - SELL abgelehnt")
                    return False

            # 8. MACD-FILTER
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, _ = self.get_macd_signal(macd_data)
                if action == "BUY" and macd_signal == "SELL":
                    print(f"{symbol}: MACD bearisch - BUY abgelehnt")
                    return False
                elif action == "SELL" and macd_signal == "BUY":
                    print(f"{symbol}: MACD bullisch - SELL abgelehnt")
                    return False
        
                # MACD Histogram-Validierung
                if action == "BUY" and macd_data['histogram'] < 0 and macd_data['histogram_trend'] == "FALLEND":
                    print(f"{symbol}: MACD Histogram fallend - BUY abgelehnt")
                    return False
                elif action == "SELL" and macd_data['histogram'] > 0 and macd_data['histogram_trend'] == "STEIGEND":
                    print(f"{symbol}: MACD Histogram steigend - SELL abgelehnt")
                    return False

            # 9. SUPPORT/RESISTANCE FILTER
            sr_data = self.calculate_support_resistance(symbol)
            if sr_data:
                current_price = tick.ask if action == "BUY" else tick.bid
            
                if action == "BUY" and sr_data['nearest_resistance']:
                    res_level, _ = sr_data['nearest_resistance']
                    distance_to_res = abs(current_price - res_level) / current_price * 10000
                    if distance_to_res < 5:
                        print(f"{symbol}: Zu nah an Resistance ({distance_to_res:.1f} Pips) - BUY abgelehnt")
                        return False
                    
                elif action == "SELL" and sr_data['nearest_support']:
                    sup_level, _ = sr_data['nearest_support']
                    distance_to_sup = abs(current_price - sup_level) / current_price * 10000
                    if distance_to_sup < 5:
                        print(f"{symbol}: Zu nah an Support ({distance_to_sup:.1f} Pips) - SELL abgelehnt")
                        return False

            # 10. STOP-LOSS UND TAKE-PROFIT BERECHNUNG
            current_price = tick.ask if action == "BUY" else tick.bid
            min_distance = symbol_info.trade_stops_level * symbol_info.point * 2

            # Smarte SL/TP basierend auf S/R
            if sr_data and action == "BUY":
                # Stop-Loss unter nächstem Support
                if sr_data['nearest_support']:
                    sup_level, _ = sr_data['nearest_support']
                    suggested_sl = sup_level - (symbol_info.point * 10)
                    stop_loss = max(suggested_sl, current_price - max(min_distance, current_price * 0.01))
                else:
                    stop_loss = current_price - max(min_distance, current_price * 0.01)
                
                # Take-Profit an nächster Resistance
                if sr_data['nearest_resistance']:
                    res_level, _ = sr_data['nearest_resistance']
                    suggested_tp = res_level - (symbol_info.point * 10)
                    take_profit = min(suggested_tp, current_price + max(min_distance, current_price * 0.02))
                else:
                    take_profit = current_price + max(min_distance, current_price * 0.02)
                
            elif sr_data and action == "SELL":
                # Stop-Loss über nächster Resistance
                if sr_data['nearest_resistance']:
                    res_level, _ = sr_data['nearest_resistance']
                    suggested_sl = res_level + (symbol_info.point * 10)
                    stop_loss = min(suggested_sl, current_price + max(min_distance, current_price * 0.01))
                else:
                    stop_loss = current_price + max(min_distance, current_price * 0.01)
                
                # Take-Profit an nächstem Support
                if sr_data['nearest_support']:
                    sup_level, _ = sr_data['nearest_support']
                    suggested_tp = sup_level + (symbol_info.point * 10)
                    take_profit = max(suggested_tp, current_price - max(min_distance, current_price * 0.02))
                else:
                    take_profit = current_price - max(min_distance, current_price * 0.02)
            else:
                # Fallback zu Standard-Levels
                if action == "BUY":
                    stop_loss = current_price - max(min_distance, current_price * 0.01)
                    take_profit = current_price + max(min_distance, current_price * 0.02)
                else:
                    stop_loss = current_price + max(min_distance, current_price * 0.01)
                    take_profit = current_price - max(min_distance, current_price * 0.02)

            # 11. TRADE AUSFÜHREN
            print(f"🔄 Analysiere {symbol}...")
            result = self.execute_trade(symbol, action, self.default_lot_size, stop_loss, take_profit)

            # 12. ERGEBNIS UND BEGRÜNDUNG ANZEIGEN
            if "✅" in result:
                print(f"📊 Begründung: {reasoning}")
                if self.mtf_enabled and 'trend_data' in locals():
                    print(f"📈 H1-Trend: {trend_data['direction']} (Stärke: {trend_data['strength']:.5f})")
                if rsi_value:
                    print(f"📈 RSI: {rsi_value}")
                if macd_data:
                    print(f"📊 MACD: {macd_data['macd']:.6f} (Signal: {macd_data['signal']:.6f})")
                    print(f"📊 Histogram: {macd_data['histogram']:.6f} ({macd_data['histogram_trend']})")
                if sr_data and sr_data['nearest_support']:
                    sup_level, sup_strength = sr_data['nearest_support']
                    print(f"🔵 Support: {sup_level:.5f} (Stärke: {sup_strength})")
                if sr_data and sr_data['nearest_resistance']:
                    res_level, res_strength = sr_data['nearest_resistance']
                    print(f"🔴 Resistance: {res_level:.5f} (Stärke: {res_strength})")

            print(result)
            return "✅" in result

        except Exception as e:
            print(f"{symbol}: Unerwarteter Fehler - {e}")
            self.log_error("auto_trade_cycle", e, f"Symbol: {symbol}")
            return False
    
    def run_auto_trading(self):
        """Verbessertes Auto-Trading mit erweiterte Fehlerbehandlung"""
        print("\n🚀 STARTE AUTO-TRADING")
        print("STOPP: Ctrl+C")
        print(f"Symbole: {self.auto_trade_symbols}")
        print(f"Intervall: {self.analysis_interval}s")
    
        cycle = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
    
        try:
            while self.auto_trading:
                cycle += 1
                print(f"\n📊 ZYKLUS #{cycle} - {datetime.now().strftime('%H:%M:%S')}")
            
                # System Health Check alle 10 Zyklen
                if cycle % 10 == 0:
                    if not self.system_health_check():
                        print("⚠️ System Health Check fehlgeschlagen - Auto-Trading pausiert")
                        time.sleep(60)  # 1 Minute warten
                        continue
            
                # Position Management alle 2 Zyklen
                if cycle % 2 == 0:
                    try:
                        print("🔧 Position Management Check...")
                        self.manage_open_positions()
                    except Exception as e:
                        print(f"⚠️ Position Management Fehler: {e}")
                        self.log_error("position_management", e)
            
                cycle_success = False
            
                # Durch alle Symbole iterieren
                for i, symbol in enumerate(self.auto_trade_symbols):
                    try:
                        print(f"\n[{i+1}/{len(self.auto_trade_symbols)}] 🔍 {symbol}")
                    
                        # Auto-Trade Cycle mit Timeout
                        success = self.auto_trade_cycle_with_timeout(symbol, timeout=30)
                    
                        if success:
                            cycle_success = True
                            consecutive_errors = 0  # Reset error counter bei Erfolg
                    
                        # Kurze Pause zwischen Symbolen
                        time.sleep(2)
                    
                    except Exception as e:
                        consecutive_errors += 1
                        print(f"❌ {symbol}: Fehler - {e}")
                        self.log_error("auto_trade_symbol", e, f"Symbol: {symbol}, Zyklus: {cycle}")
                    
                        # Bei zu vielen Fehlern in Folge Auto-Trading pausieren
                        if consecutive_errors >= max_consecutive_errors:
                            print(f"🛑 Zu viele Fehler in Folge ({consecutive_errors}) - Auto-Trading pausiert für 5 Minuten")
                            time.sleep(300)  # 5 Minuten Pause
                            consecutive_errors = 0
            
                # Zyklus-Zusammenfassung
                status_icon = "✅" if cycle_success else "❌"
                print(f"\n{status_icon} Zyklus #{cycle} abgeschlossen")
            
                # Risk Management Status anzeigen
                if hasattr(self, 'risk_manager') and self.risk_manager and cycle % 5 == 0:
                    try:
                        summary = self.risk_manager.get_risk_summary()
                        print(f"💰 Tages P&L: {summary.get('daily_pnl', 0):.2f}€ | Trades: {summary.get('trades_today', 0)}")
                    except Exception as e:
                        print(f"⚠️ Risk Summary Fehler: {e}")
            
                print(f"⏱️ Warte {self.analysis_interval}s bis zum nächsten Zyklus...")
                time.sleep(self.analysis_interval)
            
        except KeyboardInterrupt:
            print("\n🛑 Auto-Trading durch Benutzer gestoppt!")
            self.auto_trading = False
        except Exception as e:
            print(f"\n💥 Kritischer Auto-Trading Fehler: {e}")
            self.log_error("run_auto_trading", e)
            self.auto_trading = False
        finally:
            print("🔄 Auto-Trading beendet")
    
    def system_health_check(self):
        """System Health Check für Auto-Trading"""
        try:
            checks = {
                'mt5_connection': False,
                'ollama_connection': False,
                'risk_manager': False,
                'memory_usage': False
            }
        
            # 1. MT5 Verbindung prüfen
            if self.mt5_connected:
                test_tick = mt5.symbol_info_tick("EURUSD")
                checks['mt5_connection'] = test_tick is not None
        
            # 2. Ollama Verbindung prüfen
            checks['ollama_connection'] = self.check_ollama_status()
        
            # 3. Risk Manager Status prüfen
            if hasattr(self, 'risk_manager') and self.risk_manager:
                try:
                    summary = self.risk_manager.get_risk_summary()
                    checks['risk_manager'] = summary is not None
                except:
                    checks['risk_manager'] = False
        
            # 4. Memory Usage prüfen (vereinfacht)
            import psutil
            memory_percent = psutil.virtual_memory().percent
            checks['memory_usage'] = memory_percent < 90
        
            # Ergebnis bewerten
            health_score = sum(checks.values()) / len(checks)
        
            if health_score < 0.75:  # Weniger als 75% der Checks bestanden
                print(f"⚠️ System Health: {health_score:.0%}")
                for check, status in checks.items():
                    icon = "✅" if status else "❌"
                    print(f"   {icon} {check}")
                return False
        
            return True
        
        except Exception as e:
            print(f"❌ Health Check Fehler: {e}")
            return False

    def auto_trade_cycle_with_timeout(self, symbol, timeout=30):
        """Auto-Trade Cycle mit Timeout-Schutz"""
        import threading
        import time
    
        result = [False]  # Liste für Referenz-Sharing zwischen Threads
        exception = [None]
    
        def target():
            try:
                result[0] = self.auto_trade_cycle(symbol)
            except Exception as e:
                exception[0] = e
    
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
    
        if thread.is_alive():
            print(f"⏰ {symbol}: Timeout nach {timeout}s - wird übersprungen")
            return False
    
        if exception[0]:
            raise exception[0]
    
        return result[0]

    def enhanced_logging_for_auto_trading(self):
        """Erweiterte Logging-Funktionen für Auto-Trading"""
    
        def log_auto_trade_stats(self, cycle, symbol, action, result):
            """Detailliertes Logging für Auto-Trading Statistiken"""
            timestamp = datetime.now().strftime('%H:%M:%S')
        
            # Erstelle strukturierte Log-Nachricht
            log_data = {
                'timestamp': timestamp,
                'cycle': cycle,
                'symbol': symbol,
                'action': action,
                'result': result,
                'daily_trades': getattr(self, 'daily_trade_count', 0),
                'success_rate': self.calculate_success_rate()
            }
        
            # Log in Datei schreiben
            if self.logger:
                self.logger.info(f"AUTO_TRADE: {json.dumps(log_data)}")
        
            # Konsolen-Output
            result_icon = "✅" if "SUCCESS" in result else "❌"
            print(f"{timestamp} {result_icon} #{cycle} {symbol} {action} - {result}")
    
        def calculate_success_rate(self):
            """Berechnet aktuelle Erfolgsrate"""
            try:
                if not hasattr(self, 'trade_history'):
                    self.trade_history = []
            
                if len(self.trade_history) == 0:
                    return 0.0
            
                successful_trades = sum(1 for trade in self.trade_history[-20:] if trade.get('success', False))
                return (successful_trades / min(20, len(self.trade_history))) * 100
            except:
                return 0.0

    def print_callable_methods(self):
        """Druckt alle aufrufbaren Methoden der Klasse (für Debugging)"""
        methods = [method for method in dir(self) if callable(getattr(self, method)) and not method.startswith("__")]
        
        print(f"\nAufrufbare Methoden der {self.__class__.__name__} Klasse:")
        print("=" * 50)
        
        # Gruppiere Methoden nach Funktionalität
        trading_methods = [m for m in methods if any(keyword in m.lower() for keyword in ['trade', 'order', 'position'])]
        analysis_methods = [m for m in methods if any(keyword in m.lower() for keyword in ['rsi', 'calculate', 'analyze', 'signal'])]
        mt5_methods = [m for m in methods if 'mt5' in m.lower() or 'connect' in m.lower()]
        ui_methods = [m for m in methods if any(keyword in m.lower() for keyword in ['menu', 'print', 'interactive'])]
        other_methods = [m for m in methods if m not in trading_methods + analysis_methods + mt5_methods + ui_methods]
        
        categories = [
            ("📊 Trading Methoden", trading_methods),
            ("📈 Analyse Methoden", analysis_methods), 
            ("🔗 MT5 Methoden", mt5_methods),
            ("🖥️ UI Methoden", ui_methods),
            ("⚙️ Sonstige Methoden", other_methods)
        ]
        
        for category_name, method_list in categories:
            if method_list:
                print(f"\n{category_name}:")
                for method in sorted(method_list):
                    print(f"  - {method}")
        
        print("=" * 50)

    def install_dependencies(self):
        """Überprüft und installiert notwendige Abhängigkeiten"""
        try:
            required_packages = ['MetaTrader5', 'numpy', 'requests']
            missing_packages = []
            
            print("Überprüfe Abhängigkeiten...")
            
            for package in required_packages:
                try:
                    __import__(package)
                    print(f"  ✅ {package}")
                except ImportError:
                    print(f"  ❌ {package}")
                    missing_packages.append(package)
            
            if missing_packages:
                print(f"Fehlende Pakete: {missing_packages}")
                print("Installation mit: pip install " + " ".join(missing_packages))
                return False
            
            print("Alle Abhängigkeiten verfügbar")
            return True
            
        except Exception as e:
            print(f"Dependency-Check Fehler: {e}")
            return False

    def shutdown_system(self):
        """Erweiterte System-Shutdown Prozedur"""
        self.log("INFO", "System-Shutdown eingeleitet", "SYSTEM")
        self.print_header("SYSTEM BEENDEN")
        print("Stoppe alle Prozesse...")

        # Companion stoppen
        if self.companion_enabled:
            self.log("INFO", "Trading Companion wird gestoppt", "COMPANION")
            print("Stoppe Trading Companion...")
            self.stop_trading_companion()

        # Auto-Trading stoppen
        if self.auto_trading:
            self.log("INFO", "Auto-Trading wird gestoppt", "TRADE")
            print("Stoppe Auto-Trading...")
            self.auto_trading = False

        # RL System stoppen (falls vorhanden)
        if getattr(self, 'rl_enabled', False) and hasattr(self, 'rl_manager'):
            try:
                print("Speichere RL-Modell...")
                # Hier könnte RL-spezifische Cleanup-Logik stehen
                self.log("INFO", "RL System gestoppt", "RL")
            except Exception as e:
                print(f"⚠️ RL Shutdown Fehler: {e}")

        # Risk Manager Abschlussbericht
        if hasattr(self, 'risk_manager') and self.risk_manager:
            try:
                print("\n🛡️ Session Abschlussbericht:")
                summary = self.risk_manager.get_risk_summary()
                if summary:
                    print(f"📊 Tages P&L: {summary.get('daily_pnl', 0):.2f}€")
                    print(f"💼 Trades heute: {summary.get('trades_today', 0)}")
                    print(f"📈 Offene Positionen: {summary.get('open_positions', 0)}")
                
                    # Erweiterte Statistiken
                    if getattr(self, 'has_extended_indicators', False):
                        print(f"📊 Analysierte Symbole: {getattr(self, 'analyzed_symbols_count', 0)}")
                        print(f"🎯 Generierte Signale: {getattr(self, 'generated_signals_count', 0)}")
            except Exception as e:
                print(f"⚠️ Risk Manager Abschlussbericht Fehler: {e}")

        # MT5 trennen
        if self.mt5_connected:
            self.log("INFO", "MT5 Verbindung wird getrennt", "MT5")
            print("Trenne MT5...")
            self.disconnect_mt5()

        # Final Log
        features_used = []
        if getattr(self, 'has_extended_indicators', False):
            features_used.append("Erweiterte Indikatoren")
        if getattr(self, 'rl_enabled', False):
            features_used.append("RL Trading")
        if hasattr(self, 'risk_manager') and self.risk_manager:
            features_used.append("Risk Management")
    
        if features_used:
            print(f"\n✅ Genutzte erweiterte Features: {', '.join(features_used)}")
    
        self.log("INFO", "System erfolgreich heruntergefahren", "SYSTEM")
        print("Alle Prozesse beendet. Auf Wiedersehen!")
        return False

def signal_handler(sig, frame):
        """Signal Handler für sauberes Beenden"""
        print("\n🛑 Beende alle Prozesse...")
        # Hier können Sie Cleanup-Code hinzufügen
        try:
            # Global bot instance falls verfügbar
            if 'bot' in globals():
                if hasattr(bot, 'companion_enabled') and bot.companion_enabled:
                    print("🔧 Stoppe Trading Companion...")
                    bot.stop_trading_companion()
            
                if hasattr(bot, 'auto_trading') and bot.auto_trading:
                    print("🔄 Stoppe Auto-Trading...")
                    bot.auto_trading = False
            
                if hasattr(bot, 'mt5_connected') and bot.mt5_connected:
                    print("🔗 Trenne MT5...")
                    bot.disconnect_mt5()
        except Exception as e:
            print(f"⚠️ Cleanup Fehler: {e}")
    
        print("👋 Auf Wiedersehen!")
        sys.exit(0)

def main():
    """Hauptfunktion mit verbesserter Fehlerbehandlung und Risk Management"""
    print("🚀 FinGPT MT5 Setup mit RSI + S/R + Risk Management + Trading Companion")
    print("=" * 65)

    global bot  # Für signal handler
    bot = None

    try:
        bot = MT5FinGPT()
    
        # Abhängigkeiten prüfen
        print("\n📋 SCHRITT 1: Abhängigkeiten")
        if not bot.install_dependencies():
            print("❌ Installieren Sie fehlende Pakete und starten Sie neu")
            return
    
        # Risk Management System Test
        print("\n📋 SCHRITT 2: Risk Management System")
        try:
            if hasattr(bot, 'risk_manager') and bot.risk_manager:
                print("✅ Risk Manager erfolgreich initialisiert")
                
                # Zeige aktuelle Risk Settings
                print(f"   💰 Max Tagesverlust: {bot.risk_manager.max_daily_loss}€")
                print(f"   📊 Max Risiko pro Trade: {bot.risk_manager.max_risk_per_trade}%")
                print(f"   🎯 Max Positionen: {bot.risk_manager.max_total_positions}")
                print(f"   ⏰ Trading Zeiten: {bot.risk_manager.trading_start_hour}:00 - {bot.risk_manager.trading_end_hour}:00")
                
                # Test der Risk Summary
                summary = bot.risk_manager.get_risk_summary()
                if summary:
                    print("✅ Risk Management Funktionen verfügbar")
                else:
                    print("⚠️ Risk Summary Test fehlgeschlagen")
            else:
                print("❌ Risk Manager nicht initialisiert")
                print("💡 Tipp: Prüfen Sie ob risk_manager.py existiert")
        except Exception as e:
            print(f"❌ Risk Management Fehler: {e}")
            print("💡 System läuft weiter, aber ohne Risk Management")

        # Ollama Status prüfen
        print("\n📋 SCHRITT 3: Ollama Server")
        if not bot.check_ollama_status():
            print("❌ Ollama starten: 'ollama serve'")
            print("💡 Tipp: Öffnen Sie ein neues Terminal und führen Sie 'ollama serve' aus")
            return

        # Modelle laden
        print("\n📋 SCHRITT 4: KI-Modelle")
        if not bot.get_available_models():
            print("❌ Keine Ollama-Modelle gefunden")
            print("💡 Tipp: Installieren Sie ein Modell mit 'ollama pull llama3.1:8b'")
            return

        if not bot.select_finance_model():
            print("❌ Kein passendes Finanz-Modell gefunden")
            print("💡 Tipp: Installieren Sie ein empfohlenes Modell")
            return

        # MT5 Verbindung
        print("\n📋 SCHRITT 5: MetaTrader 5")
        if bot.connect_mt5():
            # Test der MT5-Daten
            test = bot.get_mt5_live_data("EURUSD")
            if "nicht" not in test:
                print("✅ MT5-Daten mit RSI + S/R verfügbar!")
                
                # Risk Manager mit MT5 testen (falls verfügbar)
                if hasattr(bot, 'risk_manager') and bot.risk_manager:
                    try:
                        # Test Position Size Berechnung
                        test_lot_size = bot.risk_manager.calculate_position_size("EURUSD", 20.0, 1.0)
                        print(f"✅ Risk Calculator Test: {test_lot_size} Lots für 20 Pips SL")
                        
                        # Test Can Open Position
                        can_trade, reason = bot.risk_manager.can_open_position("EURUSD", "BUY", 0.1)
                        if can_trade:
                            print("✅ Risk Checks: Trading erlaubt")
                        else:
                            print(f"ℹ️ Risk Checks: {reason}")
                            
                    except Exception as e:
                        print(f"⚠️ Risk Calculator Test Fehler: {e}")
                        
            else:
                print("⚠️ MT5 verbunden, aber Datentest fehlgeschlagen")
        else:
            print("⚠️ MT5 nicht verbunden - Trading-Features eingeschränkt")
            print("💡 Risk Management funktioniert trotzdem für Demo-Zwecke")

        # System Status Zusammenfassung
        print("\n📊 SYSTEM STATUS:")
        print("─" * 40)
        
        components = [
            ("🤖 KI-System", "✅" if bot.selected_model else "❌"),
            ("📱 MT5", "✅" if bot.mt5_connected else "❌"), 
            ("🛡️ Risk Manager", "✅" if hasattr(bot, 'risk_manager') and bot.risk_manager else "❌"),
            ("📊 Technische Analyse", "✅"),  # RSI, MACD, S/R sind immer verfügbar
            ("🔧 Trading Companion", "⚠️" if hasattr(bot, 'companion_process') else "❌")
        ]
        
        for component, status in components:
            print(f"{component}: {status}")
        
        print("─" * 40)

        # Zeige Risk Status wenn verfügbar
        if hasattr(bot, 'risk_manager') and bot.risk_manager and bot.mt5_connected:
            try:
                print("\n🛡️ AKTUELLER RISK STATUS:")
                bot.risk_manager.print_risk_status()
            except Exception as e:
                print(f"⚠️ Risk Status Anzeige Fehler: {e}")

        print("\n🎯 SYSTEM BEREIT")
        print("=" * 65)
        

        # Signal Handler registrieren
        signal.signal(signal.SIGINT, signal_handler)

        # Hauptmenü starten
        bot.interactive_menu()

    except KeyboardInterrupt:
        print("\n🛑 Beendet durch Ctrl+C")
        if bot:
            cleanup_bot(bot)
    except ImportError as e:
        print(f"\n❌ Import-Fehler: {e}")
        if "risk_manager" in str(e):
            print("💡 Lösungsvorschlag:")
            print("   1. Erstellen Sie die Datei 'risk_manager.py' im selben Ordner")
            print("   2. Kopieren Sie den RiskManager Code hinein")
            print("   3. Starten Sie das Programm neu")
        else:
            print("💡 Installieren Sie fehlende Pakete mit: pip install <paketname>")
    except Exception as e:
        print(f"\n💥 Unerwarteter Fehler: {e}")
        import traceback
        print("🔍 Fehler-Details:")
        traceback.print_exc()
        if bot:
            cleanup_bot(bot)

def cleanup_bot(bot):
    """Erweiterte Hilfsfunktion für sauberes Beenden mit Risk Manager"""
    try:
        if hasattr(bot, 'companion_enabled') and bot.companion_enabled:
            print("🔧 Stoppe Trading Companion...")
            bot.stop_trading_companion()

        if hasattr(bot, 'auto_trading') and bot.auto_trading:
            print("🔄 Stoppe Auto-Trading...")
            bot.auto_trading = False

        # Risk Manager Abschlussbericht
        if hasattr(bot, 'risk_manager') and bot.risk_manager:
            try:
                print("🛡️ Risk Manager Abschlussbericht:")
                summary = bot.risk_manager.get_risk_summary()
                if summary:
                    print(f"   📊 Tages P&L: {summary.get('daily_pnl', 0):.2f}€")
                    print(f"   💼 Trades heute: {summary.get('trades_today', 0)}")
                    print(f"   📈 Offene Positionen: {summary.get('open_positions', 0)}")
            except Exception as e:
                print(f"⚠️ Risk Manager Abschlussbericht Fehler: {e}")

        if hasattr(bot, 'mt5_connected') and bot.mt5_connected:
            print("🔗 Trenne MT5...")
            bot.disconnect_mt5()
            
    except Exception as e:
        print(f"⚠️ Cleanup Fehler: {e}")

# Verbesserte Signal Handler
def signal_handler(sig, frame):
    """Erweiterte Signal Handler für sauberes Beenden"""
    print("\n🛑 Beende alle Prozesse...")
    try:
        # Global bot instance falls verfügbar
        if 'bot' in globals() and bot:
            # Risk Manager Final Stats
            if hasattr(bot, 'risk_manager') and bot.risk_manager:
                try:
                    summary = bot.risk_manager.get_risk_summary()
                    if summary.get('trades_today', 0) > 0:
                        print(f"📊 Session Summary: {summary.get('trades_today', 0)} Trades, P&L: {summary.get('daily_pnl', 0):.2f}€")
                except:
                    pass
            
            cleanup_bot(bot)
    
    except Exception as e:
        print(f"⚠️ Signal Handler Fehler: {e}")

    print("👋 Auf Wiedersehen!")
    sys.exit(0)

if __name__ == "__main__":
        main()
