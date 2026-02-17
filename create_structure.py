"""
FinGPT Modular Architecture
Modulare Code-Struktur für verbesserte Wartbarkeit und Erweiterbarkeit
"""

import os
import sys
from pathlib import Path

# Projekt-Struktur erstellen
PROJECT_STRUCTURE = {
    "core": ["__init__.py", "bot.py", "config.py", "logger.py"],
    "trading": ["__init__.py", "executor.py", "validator.py", "manager.py"],
    "data": ["__init__.py", "collector.py", "processor.py", "cache.py"],
    "ai": ["__init__.py", "analyzer.py", "model.py", "predictor.py"],
    "utils": ["__init__.py", "helpers.py", "validators.py", "formatters.py"],
    "exceptions": ["__init__.py", "trading_errors.py", "data_errors.py", "api_errors.py"],
    "config": ["__init__.py", "settings.py", "defaults.py"],
    "tests": ["__init__.py", "test_core.py", "test_trading.py", "test_data.py"]
}

def create_project_structure(base_path: str = "."):
    """Erstellt die modulare Projektstruktur"""
    base = Path(base_path)
    
    for folder, files in PROJECT_STRUCTURE.items():
        folder_path = base / "fingpt" / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # __init__.py Dateien erstellen
        init_file = folder_path / "__init__.py"
        if not init_file.exists():
            init_file.touch()
        
        # Spezifische Dateien erstellen
        for file in files:
            file_path = folder_path / file
            if not file_path.exists():
                file_path.touch()

if __name__ == "__main__":
    create_project_structure()
    print("Modulare Projektstruktur erstellt")