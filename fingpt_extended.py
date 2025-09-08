#!/usr/bin/env python3
"""
FinGPT Extended - Integration der erweiterten technischen Indikatoren
Erweitert das bestehende FinGPT-System um zusätzliche Analyse-Funktionen
"""

from advanced_indicators import AdvancedIndicators, IndicatorIntegration
import MetaTrader5 as mt5
from datetime import datetime
import time

class FinGPTExtended:
    """
    Erweiterte Version des FinGPT-Systems mit zusätzlichen Indikatoren
    """
    
    def __init__(self, original_fingpt):
        """
        Initialisiert die erweiterte Version
        
        Args:
            original_fingpt: Die ursprüngliche FinGPT-Instanz
        """
        self.fingpt = original_fingpt
        self.advanced_indicators = AdvancedIndicators(logger=original_fingpt.logger)
        self.integration = IndicatorIntegration(original_fingpt)
        
        # Erweitere das ursprüngliche Menü
        self.extend_original_menu()
        
        self.log("INFO", "FinGPT Extended initialisiert")
    
    def log(self, level, message, category="EXTENDED"):
        """Logging über das ursprüngliche System"""
        self.fingpt.log(level, message, category)
    
    def extend_original_menu(self):
        """
        Erweitert das ursprüngliche Menü um neue Optionen
        """
        # Neue Menü-Handler für erweiterte Funktionen
        self.extended_menu_options = {
            "18": ("🔬", "Erweiterte Indikatoren"),
            "19": ("📊", "Vollständige technische Analyse"),
            "20": ("🎯", "Signal-Generator (Alle Indikatoren)"),
            "21": ("⚙️", "Erweiterte Indikator-Einstellungen"),
            "22": ("🤖", "KI-Analyse mit allen Indikatoren"),
            "23": ("📈", "Multi-Indikator Scanner"),
            "24": ("📋", "Indikator-Vergleich"),
        }
    
    def enhanced_interactive_menu(self):
        """
        Erweiterte Version des interaktiven Menüs
        """
        while True:
            # Zeige ursprünglichen Header
            self.fingpt.print_header("FinGPT EXTENDED TRADING SYSTEM")
            self.fingpt.print_status_bar()
            
            print("\n📋 HAUPTMENÜ (Erweitert):")
            print("─" * 35)
            
            # Ursprüngliche Menü-Items (1-17)
            original_items = [
                ("1", "📊", "Live-Daten anzeigen"),
                ("2", "🤖", "KI-Analyse (Basis)"),
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
            
            # Zeige ursprüngliche Optionen
            for num, icon, desc in original_items:
                print(f" {num:>2}. {icon} {desc}")
            
            print("\n📊 ERWEITERTE FUNKTIONEN:")
            print("─" * 35)
            
            # Erweiterte Optionen
            for num, (icon, desc) in self.extended_menu_options.items():
                print(f" {num:>2}. {icon} {desc}")
            
            print("─" * 50)
            
            choice = input("🎯 Ihre Wahl (1-24): ").strip()
            
            # Handle erweiterte Optionen
            if choice in self.extended_menu_options:
                if not self.handle_extended_menu_choice(choice):
                    break
            # Handle ursprüngliche Optionen
            elif choice in [str(i) for i in range(1, 18)]:
                if not self.fingpt.handle_menu_choice(choice):
                    break
            else:
                print("❌ Ungültige Auswahl")
                input("\n📝 Drücken Sie Enter zum Fortfahren...")
    
    def handle_extended_menu_choice(self, choice):
        """
        Behandelt die erweiterten Menü-Optionen
        """
        self.log("INFO", f"Erweiterte Option {choice} gewählt", "MENU")
        
        if choice == "18":
            # Erweiterte Indikatoren anzeigen
            self.show_advanced_indicators()
            
        elif choice == "19":
            # Vollständige technische Analyse
            self.full_technical_analysis()
            
        elif choice == "20":
            # Signal-Generator
            self.advanced_signal_generator()
            
        elif choice == "21":
            # Erweiterte Indikator-Einstellungen
            self.advanced_indicator_settings()
            
        elif choice == "22":
            # KI-Analyse mit allen Indikatoren
            self.enhanced_ai_analysis()
            
        elif choice == "23":
            # Multi-Indikator Scanner
            self.multi_indicator_scanner()
            
        elif choice == "24":
            # Indikator-Vergleich
            self.indicator_comparison()
        
        input("\n📝 Drücken Sie Enter zum Fortfahren...")
        return True
    
    def show_advanced_indicators(self):
        """
        Zeigt alle erweiterten Indikatoren für ein Symbol
        """
        self.fingpt.print_header("ERWEITERTE INDIKATOREN")
        
        symbol = input("💱 Symbol eingeben: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
        
        print(f"\n🔄 Berechne erweiterte Indikatoren für {symbol}...")
        
        try:
            # Hole alle erweiterten Indikatoren
            analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
            
            if analysis:
                # Zeige formatierten Bericht
                self.advanced_indicators.print_analysis_report(symbol, analysis)
            else:
                print("❌ Keine Indikator-Daten verfügbar")
                
        except Exception as e:
            print(f"❌ Fehler bei der Indikator-Berechnung: {e}")
    
    def full_technical_analysis(self):
        """
        Führt eine vollständige technische Analyse durch (Basis + Erweitert)
        """
        self.fingpt.print_header("VOLLSTÄNDIGE TECHNISCHE ANALYSE")
        
        symbol = input("💱 Symbol für vollständige Analyse: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
        
        print(f"\n🔄 Führe vollständige Analyse für {symbol} durch...")
        print("─" * 60)
        
        try:
            # 1. Basis-Analyse (Original FinGPT)
            print("📊 BASIS INDIKATOREN:")
            print("─" * 30)
            
            # RSI
            rsi_value = self.fingpt.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, rsi_desc = self.fingpt.get_rsi_signal(rsi_value)
                icon = "🟢" if rsi_signal == "BUY" else "🔴" if rsi_signal == "SELL" else "🟡"
                print(f"{icon} RSI: {rsi_value} - {rsi_desc}")
            
            # MACD
            macd_data = self.fingpt.calculate_macd(symbol)
            if macd_data:
                macd_signal, macd_desc = self.fingpt.get_macd_signal(macd_data)
                icon = "🟢" if macd_signal == "BUY" else "🔴" if macd_signal == "SELL" else "🟡"
                print(f"{icon} MACD: {macd_desc}")
            
            # Support/Resistance
            sr_data = self.fingpt.calculate_support_resistance(symbol)
            if sr_data:
                current_price = sr_data['current_price']
                sr_signal, sr_desc = self.fingpt.get_sr_signal(sr_data, current_price)
                icon = "🟢" if sr_signal == "BUY" else "🔴" if sr_signal == "SELL" else "🟡"
                print(f"{icon} S/R: {sr_desc}")
            
            print("\n📈 ERWEITERTE INDIKATOREN:")
            print("─" * 30)
            
            # 2. Erweiterte Analyse
            advanced_analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
            
            if advanced_analysis:
                self.advanced_indicators.print_analysis_report(symbol, advanced_analysis)
            
            # 3. Gesamtsignal erstellen
            print("\n🎯 GESAMTBEWERTUNG:")
            print("─" * 30)
            
            trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
            
            signal_icon = "🚀" if trading_signal['signal'] == "STRONG_BUY" else \
                         "🟢" if trading_signal['signal'] == "BUY" else \
                         "💥" if trading_signal['signal'] == "STRONG_SELL" else \
                         "🔴" if trading_signal['signal'] == "SELL" else "🟡"
            
            print(f"{signal_icon} SIGNAL: {trading_signal['signal']}")
            print(f"🎯 KONFIDENZ: {trading_signal['confidence']}")
            print(f"📊 INDIKATOR-ANZAHL: {trading_signal['total_indicators']}")
            
            if trading_signal['buy_ratio'] > 0:
                print(f"🟢 Bullisch: {trading_signal['buy_ratio']:.1%}")
            if trading_signal['sell_ratio'] > 0:
                print(f"🔴 Bearisch: {trading_signal['sell_ratio']:.1%}")
            
            print("\n📋 UNTERSTÜTZENDE SIGNALE:")
            for signal in trading_signal['supporting_signals']:
                print(f"  ✅ {signal}")
            
            if trading_signal['conflicting_signals']:
                print("\n⚠️ NEUTRALE/KONFLIKT SIGNALE:")
                for signal in trading_signal['conflicting_signals']:
                    print(f"  ⚠️ {signal}")
                    
        except Exception as e:
            print(f"❌ Vollständige Analyse Fehler: {e}")
    
    def advanced_signal_generator(self):
        """
        Generiert Trading-Signale basierend auf allen Indikatoren
        """
        self.fingpt.print_header("SIGNAL-GENERATOR (ALLE INDIKATOREN)")
        
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
        """Generiert Signal für einzelnes Symbol"""
        try:
            print(f"\n🔄 Generiere Signal für {symbol}...")
            
            trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
            
            print(f"\n{'='*50}")
            print(f"🎯 TRADING-SIGNAL: {symbol}")
            print(f"{'='*50}")
            
            # Haupt-Signal
            signal_icon = "🚀" if trading_signal['signal'] == "STRONG_BUY" else \
                         "🟢" if trading_signal['signal'] == "BUY" else \
                         "💥" if trading_signal['signal'] == "STRONG_SELL" else \
                         "🔴" if trading_signal['signal'] == "SELL" else "🟡"
            
            print(f"{signal_icon} SIGNAL: {trading_signal['signal']}")
            print(f"🎯 KONFIDENZ: {trading_signal['confidence']}")
            print(f"📊 ANALYSIERTE INDIKATOREN: {trading_signal['total_indicators']}")
            print(f"⏰ ZEITSTEMPEL: {trading_signal['timestamp']}")
            
            # Verhältnis anzeigen
            if trading_signal.get('buy_ratio', 0) > 0 or trading_signal.get('sell_ratio', 0) > 0:
                print(f"\n📈 SIGNAL-VERTEILUNG:")
                print(f"🟢 Bullisch: {trading_signal.get('buy_ratio', 0):.1%}")
                print(f"🔴 Bearisch: {trading_signal.get('sell_ratio', 0):.1%}")
            
            # Unterstützende Signale
            if trading_signal.get('supporting_signals'):
                print(f"\n✅ UNTERSTÜTZENDE SIGNALE:")
                for i, signal in enumerate(trading_signal['supporting_signals'], 1):
                    print(f"{i}. {signal}")
            
            # Konflikt-Signale
            if trading_signal.get('conflicting_signals'):
                print(f"\n⚠️ NEUTRALE SIGNALE:")
                for i, signal in enumerate(trading_signal['conflicting_signals'], 1):
                    print(f"{i}. {signal}")
            
            # Trading-Empfehlung
            print(f"\n💡 TRADING-EMPFEHLUNG:")
            if trading_signal['signal'] in ['STRONG_BUY', 'BUY']:
                print(f"📈 Kaufgelegenheit erkannt")
                print(f"🎯 Empfohlene Aktion: Position eröffnen")
            elif trading_signal['signal'] in ['STRONG_SELL', 'SELL']:
                print(f"📉 Verkaufsgelegenheit erkannt")
                print(f"🎯 Empfohlene Aktion: Short-Position oder bestehende Position schließen")
            else:
                print(f"⏸️ Abwarten empfohlen")
                print(f"🎯 Empfohlene Aktion: Weitere Bestätigung abwarten")
            
            print(f"{'='*50}")
            
        except Exception as e:
            print(f"❌ Signal-Generierung Fehler: {e}")
    
    def generate_multiple_signals(self, symbols):
        """Generiert Signale für multiple Symbole"""
        try:
            print(f"\n🔄 Generiere Signale für {len(symbols)} Symbole...")
            
            all_signals = []
            
            for symbol in symbols:
                print(f"📊 Analysiere {symbol}...")
                try:
                    trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
                    all_signals.append(trading_signal)
                    time.sleep(1)  # Kurze Pause zwischen Analysen
                except Exception as e:
                    print(f"⚠️ Fehler bei {symbol}: {e}")
            
            # Sortiere nach Signal-Stärke
            def signal_priority(signal):
                priorities = {
                    'STRONG_BUY': 5,
                    'BUY': 4,
                    'NEUTRAL': 3,
                    'SELL': 2,
                    'STRONG_SELL': 1,
                    'ERROR': 0
                }
                return priorities.get(signal['signal'], 0)
            
            all_signals.sort(key=signal_priority, reverse=True)
            
            # Zeige Zusammenfassung
            print(f"\n{'='*60}")
            print(f"📊 MULTI-SYMBOL SIGNAL-ÜBERSICHT")
            print(f"{'='*60}")
            
            for signal in all_signals:
                symbol = signal['symbol']
                main_signal = signal['signal']
                confidence = signal['confidence']
                
                signal_icon = "🚀" if main_signal == "STRONG_BUY" else \
                             "🟢" if main_signal == "BUY" else \
                             "💥" if main_signal == "STRONG_SELL" else \
                             "🔴" if main_signal == "SELL" else \
                             "🟡" if main_signal == "NEUTRAL" else "❌"
                
                conf_icon = "🎯" if confidence == "HOCH" else "📊" if confidence == "MITTEL" else "📉"
                
                print(f"{signal_icon} {symbol:8} | {main_signal:12} | {conf_icon} {confidence:8} | Indikatoren: {signal.get('total_indicators', 0)}")
            
            # Top-Gelegenheiten hervorheben
            strong_signals = [s for s in all_signals if s['signal'] in ['STRONG_BUY', 'STRONG_SELL']]
            
            if strong_signals:
                print(f"\n🎯 TOP TRADING-GELEGENHEITEN:")
                print("─" * 40)
                
                for signal in strong_signals[:3]:  # Top 3
                    symbol = signal['symbol']
                    main_signal = signal['signal']
                    buy_ratio = signal.get('buy_ratio', 0)
                    sell_ratio = signal.get('sell_ratio', 0)
                    
                    ratio = buy_ratio if main_signal in ['STRONG_BUY', 'BUY'] else sell_ratio
                    
                    print(f"🏆 {symbol}: {main_signal} ({ratio:.1%} Übereinstimmung)")
                    
                    # Zeige Top-Signale
                    if signal.get('supporting_signals'):
                        top_signals = signal['supporting_signals'][:2]
                        for supporting in top_signals:
                            print(f"   ✅ {supporting}")
            
            print(f"{'='*60}")
            
        except Exception as e:
            print(f"❌ Multi-Signal Fehler: {e}")
    
    def advanced_indicator_settings(self):
        """
        Einstellungen für erweiterte Indikatoren
        """
        while True:
            self.fingpt.print_header("ERWEITERTE INDIKATOR-EINSTELLUNGEN")
            
            print(f"📊 Aktuelle Einstellungen:")
            print("─" * 40)
            print(f"Williams %R Periode: {self.advanced_indicators.williams_r_period}")
            print(f"Williams %R Überkauft: {self.advanced_indicators.williams_r_overbought}")
            print(f"Williams %R Überverkauft: {self.advanced_indicators.williams_r_oversold}")
            print(f"CCI Periode: {self.advanced_indicators.cci_period}")
            print(f"CCI Überkauft: {self.advanced_indicators.cci_overbought}")
            print(f"CCI Überverkauft: {self.advanced_indicators.cci_oversold}")
            print(f"Awesome Oscillator Fast: {self.advanced_indicators.ao_fast_period}")
            print(f"Awesome Oscillator Slow: {self.advanced_indicators.ao_slow_period}")
            print(f"Ichimoku Tenkan: {self.advanced_indicators.ichimoku_tenkan}")
            print(f"Ichimoku Kijun: {self.advanced_indicators.ichimoku_kijun}")
            print(f"VWAP Periode: {self.advanced_indicators.vwap_period}")
            print(f"MFI Periode: {self.advanced_indicators.mfi_period}")
            print(f"ADX Periode: {self.advanced_indicators.adx_period}")
            
            print("\n📋 EINSTELLUNGEN:")
            print("─" * 25)
            print(" 1. Williams %R Einstellungen")
            print(" 2. CCI Einstellungen")
            print(" 3. Awesome Oscillator Einstellungen")
            print(" 4. Ichimoku Einstellungen")
            print(" 5. VWAP Einstellungen")
            print(" 6. MFI Einstellungen")
            print(" 7. ADX Einstellungen")
            print(" 8. Alle auf Standard zurücksetzen")
            print(" 9. Zurück")
            
            choice = input("\n🎯 Ihre Wahl (1-9): ").strip()
            
            if choice == "1":
                self.configure_williams_r()
            elif choice == "2":
                self.configure_cci()
            elif choice == "3":
                self.configure_awesome_oscillator()
            elif choice == "4":
                self.configure_ichimoku()
            elif choice == "5":
                self.configure_vwap()
            elif choice == "6":
                self.configure_mfi()
            elif choice == "7":
                self.configure_adx()
            elif choice == "8":
                self.reset_advanced_settings()
            elif choice == "9":
                break
            else:
                print("❌ Ungültige Auswahl")
            
            if choice != "9":
                input("\n📝 Drücken Sie Enter zum Fortfahren...")
    
    def configure_williams_r(self):
        """Williams %R Einstellungen"""
        print("\n📊 WILLIAMS %R EINSTELLUNGEN")
        print("─" * 30)
        
        try:
            period = input(f"Periode (aktuell {self.advanced_indicators.williams_r_period}): ")
            if period:
                period = int(period)
                if 5 <= period <= 50:
                    self.advanced_indicators.williams_r_period = period
                    print(f"✅ Williams %R Periode auf {period} gesetzt")
                else:
                    print("❌ Periode muss zwischen 5 und 50 liegen")
            
            overbought = input(f"Überkauft Level (aktuell {self.advanced_indicators.williams_r_overbought}): ")
            if overbought:
                overbought = float(overbought)
                if -50 <= overbought <= -10:
                    self.advanced_indicators.williams_r_overbought = overbought
                    print(f"✅ Überkauft Level auf {overbought} gesetzt")
                else:
                    print("❌ Überkauft Level muss zwischen -50 und -10 liegen")
            
            oversold = input(f"Überverkauft Level (aktuell {self.advanced_indicators.williams_r_oversold}): ")
            if oversold:
                oversold = float(oversold)
                if -100 <= oversold <= -50:
                    self.advanced_indicators.williams_r_oversold = oversold
                    print(f"✅ Überverkauft Level auf {oversold} gesetzt")
                else:
                    print("❌ Überverkauft Level muss zwischen -100 und -50 liegen")
                    
        except ValueError:
            print("❌ Ungültige Eingabe")
    
    def configure_cci(self):
        """CCI Einstellungen"""
        print("\n📊 CCI EINSTELLUNGEN")
        print("─" * 20)
        
        try:
            period = input(f"Periode (aktuell {self.advanced_indicators.cci_period}): ")
            if period:
                period = int(period)
                if 10 <= period <= 50:
                    self.advanced_indicators.cci_period = period
                    print(f"✅ CCI Periode auf {period} gesetzt")
                else:
                    print("❌ Periode muss zwischen 10 und 50 liegen")
            
            overbought = input(f"Überkauft Level (aktuell {self.advanced_indicators.cci_overbought}): ")
            if overbought:
                overbought = float(overbought)
                if 50 <= overbought <= 200:
                    self.advanced_indicators.cci_overbought = overbought
                    print(f"✅ Überkauft Level auf {overbought} gesetzt")
                else:
                    print("❌ Überkauft Level muss zwischen 50 und 200 liegen")
            
            oversold = input(f"Überverkauft Level (aktuell {self.advanced_indicators.cci_oversold}): ")
            if oversold:
                oversold = float(oversold)
                if -200 <= oversold <= -50:
                    self.advanced_indicators.cci_oversold = oversold
                    print(f"✅ Überverkauft Level auf {oversold} gesetzt")
                else:
                    print("❌ Überverkauft Level muss zwischen -200 und -50 liegen")
                    
        except ValueError:
            print("❌ Ungültige Eingabe")
    
    def configure_awesome_oscillator(self):
        """Awesome Oscillator Einstellungen"""
        print("\n📊 AWESOME OSCILLATOR EINSTELLUNGEN")
        print("─" * 40)
        
        try:
            fast = input(f"Fast Period (aktuell {self.advanced_indicators.ao_fast_period}): ")
            if fast:
                fast = int(fast)
                if 3 <= fast <= 10:
                    self.advanced_indicators.ao_fast_period = fast
                    print(f"✅ Fast Period auf {fast} gesetzt")
                else:
                    print("❌ Fast Period muss zwischen 3 und 10 liegen")
            
            slow = input(f"Slow Period (aktuell {self.advanced_indicators.ao_slow_period}): ")
            if slow:
                slow = int(slow)
                if 20 <= slow <= 50:
                    self.advanced_indicators.ao_slow_period = slow
                    print(f"✅ Slow Period auf {slow} gesetzt")
                else:
                    print("❌ Slow Period muss zwischen 20 und 50 liegen")
                    
        except ValueError:
            print("❌ Ungültige Eingabe")
    
    def configure_ichimoku(self):
        """Ichimoku Einstellungen"""
        print("\n📊 ICHIMOKU EINSTELLUNGEN")
        print("─" * 25)
        
        try:
            tenkan = input(f"Tenkan-sen Period (aktuell {self.advanced_indicators.ichimoku_tenkan}): ")
            if tenkan:
                tenkan = int(tenkan)
                if 5 <= tenkan <= 15:
                    self.advanced_indicators.ichimoku_tenkan = tenkan
                    print(f"✅ Tenkan-sen auf {tenkan} gesetzt")
                else:
                    print("❌ Tenkan-sen muss zwischen 5 und 15 liegen")
            
            kijun = input(f"Kijun-sen Period (aktuell {self.advanced_indicators.ichimoku_kijun}): ")
            if kijun:
                kijun = int(kijun)
                if 20 <= kijun <= 35:
                    self.advanced_indicators.ichimoku_kijun = kijun
                    print(f"✅ Kijun-sen auf {kijun} gesetzt")
                else:
                    print("❌ Kijun-sen muss zwischen 20 und 35 liegen")
            
            senkou_b = input(f"Senkou Span B Period (aktuell {self.advanced_indicators.ichimoku_senkou_b}): ")
            if senkou_b:
                senkou_b = int(senkou_b)
                if 40 <= senkou_b <= 70:
                    self.advanced_indicators.ichimoku_senkou_b = senkou_b
                    print(f"✅ Senkou Span B auf {senkou_b} gesetzt")
                else:
                    print("❌ Senkou Span B muss zwischen 40 und 70 liegen")
                    
        except ValueError:
            print("❌ Ungültige Eingabe")
    
    def configure_vwap(self):
        """VWAP Einstellungen"""
        print("\n📊 VWAP EINSTELLUNGEN")
        print("─" * 20)
        
        try:
            period = input(f"Periode (aktuell {self.advanced_indicators.vwap_period}): ")
            if period:
                period = int(period)
                if 10 <= period <= 50:
                    self.advanced_indicators.vwap_period = period
                    print(f"✅ VWAP Periode auf {period} gesetzt")
                else:
                    print("❌ Periode muss zwischen 10 und 50 liegen")
                    
        except ValueError:
            print("❌ Ungültige Eingabe")
    
    def configure_mfi(self):
        """MFI Einstellungen"""
        print("\n📊 MONEY FLOW INDEX EINSTELLUNGEN")
        print("─" * 35)
        
        try:
            period = input(f"Periode (aktuell {self.advanced_indicators.mfi_period}): ")
            if period:
                period = int(period)
                if 10 <= period <= 30:
                    self.advanced_indicators.mfi_period = period
                    print(f"✅ MFI Periode auf {period} gesetzt")
                else:
                    print("❌ Periode muss zwischen 10 und 30 liegen")
            
            overbought = input(f"Überkauft Level (aktuell {self.advanced_indicators.mfi_overbought}): ")
            if overbought:
                overbought = float(overbought)
                if 70 <= overbought <= 90:
                    self.advanced_indicators.mfi_overbought = overbought
                    print(f"✅ Überkauft Level auf {overbought} gesetzt")
                else:
                    print("❌ Überkauft Level muss zwischen 70 und 90 liegen")
            
            oversold = input(f"Überverkauft Level (aktuell {self.advanced_indicators.mfi_oversold}): ")
            if oversold:
                oversold = float(oversold)
                if 10 <= oversold <= 30:
                    self.advanced_indicators.mfi_oversold = oversold
                    print(f"✅ Überverkauft Level auf {oversold} gesetzt")
                else:
                    print("❌ Überverkauft Level muss zwischen 10 und 30 liegen")
                    
        except ValueError:
            print("❌ Ungültige Eingabe")
    
    def configure_adx(self):
        """ADX Einstellungen"""
        print("\n📊 ADX EINSTELLUNGEN")
        print("─" * 20)
        
        try:
            period = input(f"Periode (aktuell {self.advanced_indicators.adx_period}): ")
            if period:
                period = int(period)
                if 10 <= period <= 25:
                    self.advanced_indicators.adx_period = period
                    print(f"✅ ADX Periode auf {period} gesetzt")
                else:
                    print("❌ Periode muss zwischen 10 und 25 liegen")
            
            threshold = input(f"Trend Threshold (aktuell {self.advanced_indicators.adx_trend_threshold}): ")
            if threshold:
                threshold = float(threshold)
                if 15 <= threshold <= 35:
                    self.advanced_indicators.adx_trend_threshold = threshold
                    print(f"✅ Trend Threshold auf {threshold} gesetzt")
                else:
                    print("❌ Trend Threshold muss zwischen 15 und 35 liegen")
                    
        except ValueError:
            print("❌ Ungültige Eingabe")
    
    def reset_advanced_settings(self):
        """Setzt alle erweiterten Einstellungen zurück"""
        confirm = input("Alle erweiterten Indikator-Einstellungen zurücksetzen? (ja/nein): ")
        if confirm.lower() == "ja":
            # Standard-Werte wiederherstellen
            self.advanced_indicators.williams_r_period = 14
            self.advanced_indicators.williams_r_overbought = -20
            self.advanced_indicators.williams_r_oversold = -80
            self.advanced_indicators.cci_period = 20
            self.advanced_indicators.cci_overbought = 100
            self.advanced_indicators.cci_oversold = -100
            self.advanced_indicators.ao_fast_period = 5
            self.advanced_indicators.ao_slow_period = 34
            self.advanced_indicators.ichimoku_tenkan = 9
            self.advanced_indicators.ichimoku_kijun = 26
            self.advanced_indicators.ichimoku_senkou_b = 52
            self.advanced_indicators.vwap_period = 20
            self.advanced_indicators.mfi_period = 14
            self.advanced_indicators.mfi_overbought = 80
            self.advanced_indicators.mfi_oversold = 20
            self.advanced_indicators.adx_period = 14
            self.advanced_indicators.adx_trend_threshold = 25
            
            print("✅ Alle Einstellungen auf Standard zurückgesetzt")
        else:
            print("ℹ️ Keine Änderungen vorgenommen")
    
    def enhanced_ai_analysis(self):
        """
        KI-Analyse mit allen verfügbaren Indikatoren
        """
        self.fingpt.print_header("KI-ANALYSE (ALLE INDIKATOREN)")
        
        symbol = input("💱 Symbol für erweiterte KI-Analyse: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
        
        print(f"\n🔄 Führe erweiterte KI-Analyse für {symbol} durch...")
        print("─" * 60)
        
        try:
            # Verwende die erweiterte AI-Analyse aus der Integration
            ai_response = self.integration.enhanced_ai_analysis(symbol, include_advanced=True)
            
            print("🤖 KI-ANALYSE ERGEBNIS:")
            print("─" * 30)
            print(ai_response)
            
        except Exception as e:
            print(f"❌ Erweiterte KI-Analyse Fehler: {e}")
    
    def multi_indicator_scanner(self):
        """
        Scanner der mehrere Symbole mit allen Indikatoren analysiert
        """
        self.fingpt.print_header("MULTI-INDIKATOR SCANNER")
        
        symbols_input = input("💱 Symbole scannen (kommagetrennt, leer für Standard): ").upper()
        
        if symbols_input:
            symbols = [s.strip() for s in symbols_input.split(',')]
        else:
            symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
        
        print(f"\n🔄 Scanne {len(symbols)} Symbole mit allen Indikatoren...")
        print("─" * 60)
        
        opportunities = []
        
        try:
            for symbol in symbols:
                print(f"📊 Scanne {symbol}...")
                
                try:
                    # Erstelle Trading-Signal mit allen Indikatoren
                    trading_signal = self.integration.create_trading_signal(symbol, use_advanced=True)
                    
                    # Bewerte Signal-Qualität
                    if trading_signal['signal'] in ['STRONG_BUY', 'STRONG_SELL']:
                        score = 5
                    elif trading_signal['signal'] in ['BUY', 'SELL']:
                        score = 3
                    else:
                        score = 1
                    
                    # Konfidenz-Bonus
                    if trading_signal['confidence'] == 'HOCH':
                        score += 2
                    elif trading_signal['confidence'] == 'MITTEL':
                        score += 1
                    
                    trading_signal['score'] = score
                    opportunities.append(trading_signal)
                    
                    time.sleep(0.5)  # Kurze Pause
                    
                except Exception as e:
                    print(f"⚠️ Fehler bei {symbol}: {e}")
            
            # Sortiere nach Score
            opportunities.sort(key=lambda x: x['score'], reverse=True)
            
            # Zeige Ergebnisse
            print(f"\n{'='*70}")
            print(f"📊 SCANNER ERGEBNISSE - TOP GELEGENHEITEN")
            print(f"{'='*70}")
            
            print(f"{'Symbol':<8} {'Signal':<12} {'Konfidenz':<10} {'Score':<6} {'Indikatoren':<12}")
            print("─" * 70)
            
            for opp in opportunities:
                symbol = opp['symbol']
                signal = opp['signal']
                confidence = opp['confidence']
                score = opp['score']
                indicators = opp.get('total_indicators', 0)
                
                signal_icon = "🚀" if signal == "STRONG_BUY" else \
                             "🟢" if signal == "BUY" else \
                             "💥" if signal == "STRONG_SELL" else \
                             "🔴" if signal == "SELL" else "🟡"
                
                print(f"{symbol:<8} {signal_icon}{signal:<11} {confidence:<10} {score:<6} {indicators:<12}")
            
            # Highlight Top 3
            top_opportunities = [opp for opp in opportunities if opp['score'] >= 5]
            
            if top_opportunities:
                print(f"\n🏆 TOP TRADING-GELEGENHEITEN (Score ≥ 5):")
                print("─" * 50)
                
                for i, opp in enumerate(top_opportunities[:3], 1):
                    symbol = opp['symbol']
                    signal = opp['signal']
                    score = opp['score']
                    
                    print(f"{i}. {symbol}: {signal} (Score: {score})")
                    
                    # Zeige Top-Signale
                    if opp.get('supporting_signals'):
                        for sig in opp['supporting_signals'][:2]:
                            print(f"   ✅ {sig}")
            else:
                print("\n⏸️ Keine starken Trading-Gelegenheiten gefunden")
                print("💡 Alle Signale sind neutral oder widersprüchlich")
            
            print(f"{'='*70}")
            
        except Exception as e:
            print(f"❌ Scanner Fehler: {e}")
    
    def indicator_comparison(self):
        """
        Vergleicht verschiedene Indikatoren für ein Symbol
        """
        self.fingpt.print_header("INDIKATOR-VERGLEICH")
        
        symbol = input("💱 Symbol für Indikator-Vergleich: ").upper()
        if not symbol:
            print("❌ Kein Symbol eingegeben")
            return
        
        print(f"\n🔄 Vergleiche alle Indikatoren für {symbol}...")
        print("─" * 60)
        
        try:
            # Sammle alle Indikator-Signale
            indicators_data = {}
            
            # Basis-Indikatoren
            rsi_value = self.fingpt.calculate_rsi(symbol)
            if rsi_value:
                rsi_signal, rsi_desc = self.fingpt.get_rsi_signal(rsi_value)
                indicators_data['RSI'] = {
                    'signal': rsi_signal,
                    'value': rsi_value,
                    'description': rsi_desc,
                    'type': 'Momentum'
                }
            
            macd_data = self.fingpt.calculate_macd(symbol)
            if macd_data:
                macd_signal, macd_desc = self.fingpt.get_macd_signal(macd_data)
                indicators_data['MACD'] = {
                    'signal': macd_signal,
                    'value': f"{macd_data['macd']:.6f}",
                    'description': macd_desc,
                    'type': 'Trend/Momentum'
                }
            
            sr_data = self.fingpt.calculate_support_resistance(symbol)
            if sr_data:
                current_price = sr_data['current_price']
                sr_signal, sr_desc = self.fingpt.get_sr_signal(sr_data, current_price)
                indicators_data['Support/Resistance'] = {
                    'signal': sr_signal,
                    'value': f"{current_price:.5f}",
                    'description': sr_desc,
                    'type': 'Price Action'
                }
            
            # Erweiterte Indikatoren
            advanced_analysis = self.advanced_indicators.get_comprehensive_analysis(symbol)
            
            for indicator, data in advanced_analysis.items():
                if indicator == 'williams_r':
                    indicators_data['Williams %R'] = {
                        'signal': data['signal'],
                        'value': f"{data['value']}%",
                        'description': data['description'],
                        'type': 'Momentum'
                    }
                
                elif indicator == 'cci':
                    indicators_data['CCI'] = {
                        'signal': data['signal'],
                        'value': str(data['value']),
                        'description': data['description'],
                        'type': 'Momentum'
                    }
                
                elif indicator == 'awesome_oscillator':
                    indicators_data['Awesome Oscillator'] = {
                        'signal': data['signal'],
                        'value': f"{data['value']:.6f}",
                        'description': data['description'],
                        'type': 'Momentum'
                    }
                
                elif indicator == 'ichimoku':
                    indicators_data['Ichimoku'] = {
                        'signal': data['overall_signal'],
                        'value': data['price_vs_cloud'],
                        'description': data['description'],
                        'type': 'Trend/Support/Resistance'
                    }
                
                elif indicator == 'vwap':
                    indicators_data['VWAP'] = {
                        'signal': data['signal'],
                        'value': f"{data['vwap']:.5f}",
                        'description': data['description'],
                        'type': 'Volume/Price'
                    }
                
                elif indicator == 'mfi':
                    indicators_data['Money Flow Index'] = {
                        'signal': data['signal'],
                        'value': str(data['value']),
                        'description': data['description'],
                        'type': 'Volume/Momentum'
                    }
                
                elif indicator == 'adx':
                    indicators_data['ADX'] = {
                        'signal': data['signal'],
                        'value': str(data['adx']),
                        'description': data['description'],
                        'type': 'Trend Strength'
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


def main_extended():
    """
    Hauptfunktion für das erweiterte FinGPT-System
    """
    print("🚀 FinGPT EXTENDED - Mit erweiterten technischen Indikatoren")
    print("=" * 70)
    
    try:
        # Importiere das ursprüngliche FinGPT
        from FinGPT import MT5FinGPT
        
        # Erstelle ursprüngliche Instanz
        print("📋 Initialisiere ursprüngliches FinGPT System...")
        original_fingpt = MT5FinGPT()
        
        # Teste MT5 Verbindung
        if not original_fingpt.connect_mt5():
            print("⚠️ MT5 nicht verbunden - Einige Funktionen sind eingeschränkt")
        
        # Teste Ollama
        if not original_fingpt.check_ollama_status():
            print("⚠️ Ollama nicht verfügbar - KI-Funktionen eingeschränkt")
        else:
            original_fingpt.get_available_models()
            original_fingpt.select_finance_model()
        
        print("\n📊 Initialisiere erweiterte Indikatoren...")
        
        # Erstelle erweiterte Version
        extended_fingpt = FinGPTExtended(original_fingpt)
        
        print("\n✅ FinGPT Extended bereit!")
        print("📊 Verfügbare erweiterte Indikatoren:")
        print("   • Williams %R")
        print("   • Commodity Channel Index (CCI)")
        print("   • Awesome Oscillator")
        print("   • Ichimoku Cloud")
        print("   • Volume Weighted Average Price (VWAP)")
        print("   • Money Flow Index (MFI)")
        print("   • Average Directional Index (ADX)")
        
        print(f"\n{'='*70}")
        
        # Starte erweiterte Benutzeroberfläche
        extended_fingpt.enhanced_interactive_menu()
        
    except ImportError as e:
        print(f"❌ Import-Fehler: {e}")
        print("💡 Stellen Sie sicher, dass FinGPT.py und advanced_indicators.py verfügbar sind")
    except Exception as e:
        print(f"❌ Initialisierung fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()


# Zusätzliche Utility-Funktionen
class IndicatorBacktester:
    """
    Einfacher Backtester für die erweiterten Indikatoren
    """
    
    def __init__(self, advanced_indicators):
        self.indicators = advanced_indicators
    
    def backtest_indicator(self, symbol, indicator_name, timeframe=mt5.TIMEFRAME_H1, bars=100):
        """
        Einfacher Backtest für einen Indikator
        """
        try:
            print(f"🔄 Backtesting {indicator_name} für {symbol}...")
            
            # Hole historische Daten
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if not rates or len(rates) < 50:
                return None
            
            signals = []
            prices = []
            
            # Simuliere Indikator-Signale über Zeit
            for i in range(20, len(rates)):  # Start nach 20 Bars für Indikator-Berechnung
                # Hole Daten bis zu diesem Punkt
                current_rates = rates[:i+1]
                
                # Berechne aktuellen Preis
                current_price = current_rates[-1]['close']
                prices.append(current_price)
                
                # Hier würde die spezifische Indikator-Berechnung stehen
                # Vereinfacht für Demo
                signal = "NEUTRAL"  # Placeholder
                signals.append(signal)
            
            # Einfache Performance-Berechnung
            buy_signals = [i for i, s in enumerate(signals) if s == "BUY"]
            sell_signals = [i for i, s in enumerate(signals) if s == "SELL"]
            
            results = {
                'total_signals': len([s for s in signals if s != "NEUTRAL"]),
                'buy_signals': len(buy_signals),
                'sell_signals': len(sell_signals),
                'accuracy': 0.0,  # Würde echte Berechnung erfordern
                'profit_factor': 0.0  # Würde echte Berechnung erfordern
            }
            
            return results
            
        except Exception as e:
            print(f"❌ Backtest Fehler: {e}")
            return None


if __name__ == "__main__":
    main_extended()