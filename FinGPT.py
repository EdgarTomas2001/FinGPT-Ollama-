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
        
        # Logging Setup - ZUERST!
        self.setup_logging()
        self.log("INFO", "FinGPT System wird initialisiert...")
        
        # RISK MANAGER - NACH LOGGING!
        try:
            from risk_manager import RiskManager
            self.risk_manager = RiskManager(logger=self.logger)  # DIESE ZEILE FEHLTE!
            self.log("INFO", "Risk Manager erfolgreich initialisiert", "RISK")
        except ImportError as e:
            self.log("ERROR", f"Risk Manager Import Fehler: {e}", "RISK")
            self.risk_manager = None
        except Exception as e:
            self.log("ERROR", f"Risk Manager Initialisierung Fehler: {e}", "RISK")
            self.risk_manager = None
        
        #Timeframe Names
        self.timeframe_names = {
            mt5.TIMEFRAME_M1: "M1",
            mt5.TIMEFRAME_M5: "M5", 
            mt5.TIMEFRAME_M15: "M15",
            mt5.TIMEFRAME_M30: "M30",
            mt5.TIMEFRAME_H1: "H1",
            mt5.TIMEFRAME_H4: "H4",
            mt5.TIMEFRAME_D1: "D1"
        }
        
        # Trading Companion Integration
        self.companion_process = None
        self.companion_enabled = False
        self.auto_start_companion = False
        
        # RSI Settings
        self.rsi_period = 14
        self.rsi_timeframe = mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        # Support/Resistance Settings
        self.sr_lookback_period = 50
        self.sr_min_touches = 2
        self.sr_tolerance = 0.0002
        self.sr_strength_threshold = 3
        
        # MACD Settings
        self.macd_fast_period = 12
        self.macd_slow_period = 26
        self.macd_signal_period = 9
        self.macd_timeframe = mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None
        
        # Multi-Timeframe Settings
        self.mtf_enabled = True
        self.trend_timeframe = mt5.TIMEFRAME_H1 if MT5_AVAILABLE else None
        self.entry_timeframe = mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None
        self.trend_ema_period = 50
        self.trend_strength_threshold = 0.0010  # 10 Pips Mindest-Trendbewegung
        self.require_trend_confirmation = True
        
        # Partial Close Settings
        self.partial_close_enabled = True
        self.first_target_percent = 50
        self.second_target_percent = 25
        self.profit_target_1 = 1.5
        self.profit_target_2 = 3.0
        
        # UI Verbesserungen
        self.companion_output_queue = queue.Queue()
        self.ui_lock = threading.Lock()
        self.companion_silent_mode = False
        self.last_menu_display = 0
        
        # Trailing Stop Settings
        self.trailing_stop_enabled = True
        self.trailing_stop_distance_pips = 20
        self.trailing_stop_step_pips = 5
        self.trailing_stop_start_profit_pips = 15
        
        # ABSCHLUSS
        self.log("INFO", "FinGPT System mit Multi-Timeframe initialisiert")
        
        # DEBUG - Prüfe Risk Manager Status
        if self.risk_manager:
            self.log("INFO", "✅ Risk Manager ist verfügbar", "DEBUG")
        else:
            self.log("WARNING", "❌ Risk Manager ist NICHT verfügbar", "DEBUG")
       
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

    def print_header(self, title, width=55):
        """Schöne Header-Darstellung"""
        print("\n" + "═" * width)
        print(f"{title:^{width}}")
        print("═" * width)
    
    def print_status_bar(self):
        """Zeigt aktuellen Status an - erweitert mit Risk Management"""
        with self.ui_lock:
            # Risk Manager Status prüfen
            risk_status = "❌"
            if hasattr(self, 'risk_manager') and self.risk_manager:
                try:
                    # Teste ob Risk Manager funktional ist
                    summary = self.risk_manager.get_risk_summary()
                    if summary is not None:
                        risk_status = "✅"
                        # Zusätzliche Checks
                        daily_pnl = summary.get('daily_pnl', 0)
                        if daily_pnl <= self.risk_manager.max_daily_loss * 0.8:  # 80% des Limits
                            risk_status = "🟡"  # Warnung
                        elif daily_pnl <= self.risk_manager.max_daily_loss:
                            risk_status = "🔴"  # Kritisch
                except:
                    risk_status = "⚠️"  # Fehler
        
            status_items = [
                f"📱 MT5: {'✅' if self.mt5_connected else '❌'}",
                f"🤖 KI: {'✅' if self.selected_model else '❌'}",
                f"💰 Trading: {'✅' if self.trading_enabled else '❌'}",
                f"🔄 Auto: {'✅' if self.auto_trading else '❌'}",
                f"🛡️ Risk: {risk_status}",  # Neuer Risk Status
                f"🔧 Companion: {'✅' if self.companion_enabled else '❌'}"
            ]
        
            print("\n┌" + "─" * 65 + "┐")
            print(f"│ {' | '.join(status_items):<63} │")
            print("└" + "─" * 65 + "┘")
    
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
        """Verbesserte interaktive Benutzeroberfläche"""
    
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
                # Temporär den Companion-Thread pausieren
                import time
                time.sleep(0.1)  # Kurz warten bis laufende Ausgaben fertig sind
        
            # Schöne Header-Darstellung
            self.print_header("FinGPT TRADING SYSTEM")
        
            # Status-Leiste
            self.print_status_bar()
        
            # Hauptmenü
            print("\n📋 HAUPTMENÜ:")
            print("─" * 25)
        
            menu_items = [
                ("1", "📊", "Live-Daten anzeigen"),
                ("2", "🤖", "KI-Analyse"),
                ("3", "💰", "Trade ausführen"),
                ("4", "📈", "Offene Positionen"),
                ("5", "🔓", "Trading aktivieren/deaktivieren"),
                ("6", "🔄", "Auto-Trading"),
                ("7", "⚙️", "Position Management"),
                ("8", "🎯", "Partial Close Einstellungen"),
                ("9", "📉", "RSI Einstellungen"),
                ("10", "📊", "Support/Resistance Einstellungen"),
                ("11", "🔧", "Trading Companion"),
                ("12", "🔗", "MT5 Verbindung"),
                ("13", "📊", "MACD Einstellungen"),
                ("14", "🎯", "Trailing Stop Einstellungen"),
                ("15", "📈", "Multi-Timeframe Einstellungen"),
                ("16", "🛡️", "Risk Management"),
                ("17", "❌", "Beenden")
            ]
        
            for num, icon, desc in menu_items:
                print(f" {num:>2}. {icon} {desc}")
        
            print("─" * 45)
        
            # EINGABE MIT THREAD-SCHUTZ
            choice = ""
            try:
                # Input ohne Thread-Interferenz
                choice = input("🎯 Ihre Wahl (1-17): ").strip()
            except KeyboardInterrupt:
                choice = "17"  # Beenden bei Ctrl+C
        
            # Menü-Handler aufrufen
            if not self.handle_menu_choice(choice):
                break
    
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
                print("Erst Trading aktivieren!")
            elif self.auto_trading:
                self.auto_trading = False
                self.log("INFO", "Auto-Trading gestoppt", "TRADE")
                print("Auto-Trading gestoppt")
            else:
                self.log("INFO", "Auto-Trading Setup gestartet", "TRADE")
                if self.enable_auto_trading():
                    self.log("INFO", "Auto-Trading aktiviert und gestartet", "TRADE")
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
        """Zeigt die KI-Analyse schön formatiert an"""
    
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
    
        # KI-Antwort strukturiert aufbereiten
        formatted_response = self.format_ai_response(ai_response)
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

    def display_technical_summary(self, symbol):
        """Zeigt eine kompakte technische Zusammenfassung"""
        try:
            print("\n📊 TECHNISCHE INDIKATOREN ZUSAMMENFASSUNG:")
            print("─" * 50)
        
            # RSI
            rsi_value = self.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, rsi_desc = self.get_rsi_signal(rsi_value)
                rsi_icon = "🟢" if rsi_signal == "BUY" else "🔴" if rsi_signal == "SELL" else "🟡"
                print(f"{rsi_icon} RSI ({self.rsi_period}): {rsi_value} - {rsi_desc}")
        
            # MACD
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, macd_desc = self.get_macd_signal(macd_data)
                macd_icon = "🟢" if macd_signal == "BUY" else "🔴" if macd_signal == "SELL" else "🟡"
                print(f"{macd_icon} MACD: {macd_data['macd']:.6f} - {macd_desc[:50]}...")
        
            # Support/Resistance
            sr_data = self.calculate_support_resistance(symbol)
            if sr_data:
                current_price = sr_data['current_price']
            
                if sr_data['nearest_support']:
                    sup_level, sup_strength = sr_data['nearest_support']
                    distance = abs(current_price - sup_level) / current_price * 10000
                    print(f"🔵 Nächster Support: {sup_level:.5f} ({distance:.1f} Pips, Stärke: {sup_strength})")
            
                if sr_data['nearest_resistance']:
                    res_level, res_strength = sr_data['nearest_resistance']
                    distance = abs(current_price - res_level) / current_price * 10000
                    print(f"🔴 Nächste Resistance: {res_level:.5f} ({distance:.1f} Pips, Stärke: {res_strength})")
        
            # Multi-Timeframe Trend (falls aktiviert)
            if self.mtf_enabled:
                trend_data = self.get_higher_timeframe_trend(symbol)
                if trend_data:
                    trend_icon = "🟢" if "BULLISH" in trend_data['direction'] else "🔴" if "BEARISH" in trend_data['direction'] else "🟡"
                    tf_name = self.timeframe_names.get(self.trend_timeframe, "H1")
                    print(f"{trend_icon} {tf_name} Trend: {trend_data['direction']} ({trend_data['quality']})")
        
            print("─" * 50)
        
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
        """Verbesserte auto_trade_cycle mit Risk Checks"""
        try:
            # Basis Risk Check vor Analyse
            can_trade, reason = self.risk_manager.can_open_position(symbol, "BUY", self.default_lot_size)
            if not can_trade:
                self.log("INFO", f"{symbol}: {reason}", "RISK")
                return False
        
            # Multi-Timeframe Trend-Filter
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
        
            live_data = self.get_mt5_live_data(symbol)
            # RSI, MACD und S/R in Prompt erwähnen
            prompt = f"Analysiere {symbol} für Trading-Entscheidung. Berücksichtige besonders den RSI-Wert, MACD-Signale (Kreuzungen, Histogram, Nulllinie), ob das Symbol überkauft oder überverkauft ist, und die wichtigen Support/Resistance Levels. Achte auf Breakouts, Bounces an S/R Levels, RSI-Divergenzen und MACD-Momentum. Erkläre deine Begründung mit technischen Indikatoren, RSI-Signalen, MACD-Analyse, S/R-Levels, Trends oder Chartmustern. Gib klare BUY/SELL/WARTEN Empfehlung mit Begründung."
            ai_response = self.chat_with_model(prompt, live_data)
            recommendation = self.parse_ai_recommendation(ai_response)
            if not recommendation:
                print(f"{symbol}: WARTEN")
                return False
            action = recommendation["action"]
            reasoning = recommendation.get("reasoning", "KI-Analyse")
        
            # Multi-Timeframe Bestätigung
            if self.mtf_enabled and self.require_trend_confirmation:
                if action == "BUY" and trend_direction == "BEARISH":
                    print(f"{symbol}: H1-Trend bearish - BUY abgelehnt")
                    return False
                elif action == "SELL" and trend_direction == "BULLISH":
                    print(f"{symbol}: H1-Trend bullish - SELL abgelehnt")
                    return False
        
            positions = mt5.positions_get(symbol=symbol)
            if positions:
                print(f"{symbol}: Position bereits offen")
                return False
            # RSI-Filter für Auto-Trading
            rsi_value = self.calculate_rsi(symbol)
            sr_data = self.calculate_support_resistance(symbol)
            if rsi_value:
                rsi_signal, _ = self.get_rsi_signal(rsi_value)
                # Prüfe RSI-Bestätigung
                if action == "BUY" and rsi_value > self.rsi_overbought:
                    print(f"{symbol}: RSI überkauft ({rsi_value}) - BUY abgelehnt")
                    return False
                elif action == "SELL" and rsi_value < self.rsi_oversold:
                    print(f"{symbol}: RSI überverkauft ({rsi_value}) - SELL abgelehnt")
                    return False
    
            # MACD-Filter für Auto-Trading
            macd_data = self.calculate_macd(symbol)
            if macd_data:
                macd_signal, _ = self.get_macd_signal(macd_data)
                # Prüfe MACD-Bestätigung
                if action == "BUY" and macd_signal == "SELL":
                    print(f"{symbol}: MACD bearisch ({macd_data['macd']:.6f}) - BUY abgelehnt")
                    return False
                elif action == "SELL" and macd_signal == "BUY":
                    print(f"{symbol}: MACD bullisch ({macd_data['macd']:.6f}) - SELL abgelehnt")
                    return False
        
                # Zusätzliche MACD-Validierung: Histogram-Richtung
                if action == "BUY" and macd_data['histogram'] < 0 and macd_data['histogram_trend'] == "FALLEND":
                    print(f"{symbol}: MACD Histogram fallend - BUY abgelehnt")
                    return False
                elif action == "SELL" and macd_data['histogram'] > 0 and macd_data['histogram_trend'] == "STEIGEND":
                    print(f"{symbol}: MACD Histogram steigend - SELL abgelehnt")
                    return False
    
            # Support/Resistance Filter
            if sr_data:
                sr_signal, sr_desc = self.get_sr_signal(sr_data, tick.ask if action == "BUY" else tick.bid)
                # Zusätzliche S/R Validierung
                if action == "BUY" and sr_data['nearest_resistance']:
                    res_level, _ = sr_data['nearest_resistance']
                    distance_to_res = abs(tick.ask - res_level) / tick.ask * 10000  # in Pips
                    if distance_to_res < 5:  # Zu nah an Resistance
                        print(f"{symbol}: Zu nah an Resistance ({distance_to_res:.1f} Pips) - BUY abgelehnt")
                        return False
                elif action == "SELL" and sr_data['nearest_support']:
                    sup_level, _ = sr_data['nearest_support']
                    distance_to_sup = abs(tick.bid - sup_level) / tick.bid * 10000  # in Pips
                    if distance_to_sup < 5:  # Zu nah an Support
                        print(f"{symbol}: Zu nah an Support ({distance_to_sup:.1f} Pips) - SELL abgelehnt")
                        return False
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                print(f"{symbol}: Keine Marktdaten")
                return False
            current = tick.ask if action == "BUY" else tick.bid
            min_distance = symbol_info.trade_stops_level * symbol_info.point * 2

            # Smarte Stop-Loss und Take-Profit basierend auf S/R
            if sr_data and action == "BUY":
                # Stop-Loss unter nächstem Support
                if sr_data['nearest_support']:
                    sup_level, _ = sr_data['nearest_support']
                    suggested_sl = sup_level - (symbol_info.point * 10)  # 10 Pips Puffer
                    stop_loss = max(suggested_sl, current - max(min_distance, current * 0.01))
                else:
                    stop_loss = current - max(min_distance, current * 0.01)
                # Take-Profit an nächster Resistance
                if sr_data['nearest_resistance']:
                    res_level, _ = sr_data['nearest_resistance']
                    suggested_tp = res_level - (symbol_info.point * 10)  # 10 Pips vor Resistance
                    take_profit = min(suggested_tp, current + max(min_distance, current * 0.02))
                else:
                    take_profit = current + max(min_distance, current * 0.02)
            elif sr_data and action == "SELL":
                # Stop-Loss über nächster Resistance
                if sr_data['nearest_resistance']:
                    res_level, _ = sr_data['nearest_resistance']
                    suggested_sl = res_level + (symbol_info.point * 10)  # 10 Pips Puffer
                    stop_loss = min(suggested_sl, current + max(min_distance, current * 0.01))
                else:
                    stop_loss = current + max(min_distance, current * 0.01)
                # Take-Profit an nächstem Support
                if sr_data['nearest_support']:
                    sup_level, _ = sr_data['nearest_support']
                    suggested_tp = sup_level + (symbol_info.point * 10)  # 10 Pips vor Support
                    take_profit = max(suggested_tp, current - max(min_distance, current * 0.02))
                else:
                    take_profit = current - max(min_distance, current * 0.02)
            else:
                # Fallback zu Standard-Levels
                if action == "BUY":
                    stop_loss = current - max(min_distance, current * 0.01)
                    take_profit = current + max(min_distance, current * 0.02)
                else:
                    stop_loss = current + max(min_distance, current * 0.01)
                    take_profit = current - max(min_distance, current * 0.02)
    
            print(f"Analysiere {symbol}...")
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                print(f"{symbol}: Keine Marktdaten verfügbar")
                return False
    
            result = self.execute_trade(symbol, action, self.default_lot_size, stop_loss, take_profit)
    
            # Zeige Begründung nach erfolgreichem Trade
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
            print(f"{symbol}: {e}")
            return False
    
    def run_auto_trading(self):
        print("\nSTARTE AUTO-TRADING")
        print("STOPP: Ctrl+C")
        print(f"Symbole: {self.auto_trade_symbols}")
        print(f"Intervall: {self.analysis_interval}s")
        
        cycle = 0
        try:
            while self.auto_trading:
                cycle += 1
                print(f"\nZYKLUS #{cycle} - {datetime.now().strftime('%H:%M:%S')}")
                
                if cycle % 2 == 0:
                    print("Position Management Check...")
                    self.manage_open_positions()
                
                for symbol in self.auto_trade_symbols:
                    self.auto_trade_cycle(symbol)
                    time.sleep(5)
                
                print(f"Warte {self.analysis_interval}s...")
                time.sleep(self.analysis_interval)
                
        except KeyboardInterrupt:
            print("\nAuto-Trading gestoppt!")
            self.auto_trading = False
        except Exception as e:
            print(f"\nAuto-Trading Fehler: {e}")
            self.auto_trading = False
    
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
        
        # Kurze Bedienungsanleitung
        print("\n💡 SCHNELLSTART:")
        print("1️⃣ Option 5: Trading aktivieren")
        print("2️⃣ Option 16: Risk Management konfigurieren") 
        print("3️⃣ Option 2: KI-Analyse testen")
        print("4️⃣ Option 3: Manueller Trade (mit Risk Checks)")
        print("5️⃣ Option 6: Auto-Trading (Vorsicht!)")

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