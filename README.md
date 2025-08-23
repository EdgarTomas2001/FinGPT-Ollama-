# 🤖 FinGPT Trading System

Ein vollautomatisches, KI-gestütztes Trading-System für **MetaTrader 5 (MT5)**, entwickelt in **Python**.  
FinGPT kombiniert klassische Indikatoren (RSI, MACD, Support/Resistance) mit **Ollama LLMs** für smarte Signale, integriert Risk-Management und bietet eine modulare Architektur mit übersichtlichem Menü.

---

## ✨ Features

- **📊 Technische Indikatoren**
  - RSI (konfigurierbar: Periode, Timeframe, Overbought/Oversold)
  - MACD (12/26/9 Standard, flexibel einstellbar)
  - Automatische Support-/Resistance-Erkennung
  - Multi-Timeframe-Analyse (Trend + Entry Filter)

- **💹 Risk Management**
  - Dynamische Lot-Berechnung nach Risiko %
  - Trailing Stops (Start, Abstand, Schrittweite frei konfigurierbar)
  - Partial Close System (mehrere Gewinnziele, Lot-Reduktion)
  - Magic Number für klare Trade-Zuordnung

- **🤖 KI-Integration (Ollama)**
  - Modelle: `fingpt`, `llama3`, `mistral` (Fallback-System)
  - Signal Parsing (BUY/SELL/HOLD mit Confidence Score)
  - Kontext: Indikatoren + Chartstruktur
  - Deutsche Ausgaben + Erklärungen

- **⚙️ Auto-Trading Engine**
  - Filter-Pipeline: Trend → RSI → MACD → S/R → KI
  - Automatisches Order-Management mit SL/TP
  - Symbol-Rotation + Fehler-Isolation (kein Gesamt-Crash)
  - Konfigurierbare Intervalle (z. B. alle 300 Sekunden)

- **📂 Benutzeroberfläche**
  - Menü mit 16 Hauptoptionen (Daten, KI-Analyse, Auto-Trading, Indikator-Settings, usw.)
  - Trading Companion Integration (separates Subprozess-Skript)
  - Sicherheitsfeatures: Bestätigung für Live/Auto-Trading

- **📝 Logging**
  - Kategorien: SYSTEM, TRADE, AI, SETTINGS, ERROR, MENU
  - Ausgaben mit Emojis für bessere Lesbarkeit
  - Persistente Logfiles: `logs/fingpt_YYYYMMDD.log`
  - Extra-Funktionen: `log_trade()`, `log_ai_analysis()`, `log_error()`

---

## 🚀 Installation

### Voraussetzungen
- Python 3.9+
- MetaTrader 5 (mit aktivem Account – Demo oder Live)
- [Ollama](https://ollama.ai/) mit passenden LLMs (z. B. Llama 3, Mistral, FinGPT)
- Pakete:
  ```bash
  pip install MetaTrader5 numpy requests

<img width="972" height="840" alt="image" src="https://github.com/user-attachments/assets/a41749bc-52f1-4b93-b002-69ef90c0425d" />
<img width="827" height="911" alt="image" src="https://github.com/user-attachments/assets/c4245e66-2036-4e70-88c2-bf81b4ca85d6" />
<img width="967" height="571" alt="image" src="https://github.com/user-attachments/assets/bcbfd5bf-0b08-4f25-bd7b-402683ab5a33" />

