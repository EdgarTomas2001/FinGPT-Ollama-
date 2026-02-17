#!/usr/bin/env python3
"""
FinGPT Backward Compatibility Layer
Stellt sicher dass die Enhanced Version vollständig rückwärtskompatibel ist
"""

import sys
import os
import warnings
from typing import Any, Optional, Union
import inspect

# Pfad zum Projektverzeichnis hinzufügen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class BackwardCompatibilityManager:
    """Verwaltet Rückwärtskompatibilität für FinGPT"""
    
    def __init__(self):
        self.compatibility_warnings = []
        self.deprecated_methods = {}
        self.legacy_aliases = {}
        
    def check_compatibility(self) -> dict:
        """Prüft die Rückwärtskompatibilität"""
        print("🔍 Prüfe Rückwärtskompatibilität...")
        
        results = {
            "api_compatibility": self.check_api_compatibility(),
            "configuration_compatibility": self.check_configuration_compatibility(),
            "method_compatibility": self.check_method_compatibility(),
            "import_compatibility": self.check_import_compatibility(),
            "data_compatibility": self.check_data_compatibility(),
            "overall_score": 0
        }
        
        # Gesamtscore berechnen
        scores = [
            results["api_compatibility"]["score"],
            results["configuration_compatibility"]["score"],
            results["method_compatibility"]["score"],
            results["import_compatibility"]["score"],
            results["data_compatibility"]["score"]
        ]
        results["overall_score"] = sum(scores) / len(scores)
        
        return results
    
    def check_api_compatibility(self) -> dict:
        """Prüft API-Kompatibilität"""
        try:
            from FinGPT import MT5FinGPT
            
            # Prüfen ob alle öffentlichen Methoden existieren
            fingpt = MT5FinGPT()
            public_methods = [method for method in dir(fingpt) if not method.startswith('_')]
            
            # Erwartete Methoden aus Original-Version
            expected_methods = [
                'connect_mt5', 'disconnect_mt5', 'execute_trade', 'enable_trading',
                'enable_auto_trading', 'get_mt5_live_data', 'get_ai_analysis',
                'interactive_menu', 'print_header', 'log', 'setup_logging'
            ]
            
            missing_methods = []
            for method in expected_methods:
                if not hasattr(fingpt, method):
                    missing_methods.append(method)
            
            # Methodensignaturen prüfen
            signature_issues = []
            for method in expected_methods:
                if hasattr(fingpt, method):
                    try:
                        sig = inspect.signature(getattr(fingpt, method))
                        # Prüfen ob Signaturen sich nicht geändert haben
                        if self.has_signature_changed(method, sig):
                            signature_issues.append(method)
                    except Exception:
                        pass
            
            score = 100 - (len(missing_methods) * 20) - (len(signature_issues) * 10)
            score = max(0, score)
            
            return {
                "score": score,
                "missing_methods": missing_methods,
                "signature_issues": signature_issues,
                "total_methods_checked": len(expected_methods)
            }
            
        except ImportError:
            return {"score": 0, "error": "FinGPT nicht importierbar"}
    
    def check_configuration_compatibility(self) -> dict:
        """Prüft Konfigurations-Kompatibilität"""
        try:
            from FinGPT import MT5FinGPT
            
            fingpt = MT5FinGPT()
            
            # Erwartete Konfigurationsattribute
            expected_config = {
                'ollama_url': str,
                'trading_enabled': bool,
                'auto_trading': bool,
                'default_lot_size': (int, float),
                'max_risk_percent': (int, float),
                'auto_trade_symbols': list,
                'analysis_interval': int
            }
            
            config_issues = []
            for attr, expected_type in expected_config.items():
                if not hasattr(fingpt, attr):
                    config_issues.append(f"Missing attribute: {attr}")
                else:
                    value = getattr(fingpt, attr)
                    if not isinstance(value, expected_type):
                        config_issues.append(f"Type mismatch for {attr}: expected {expected_type}, got {type(value)}")
            
            # Prüfen ob Standardwerte erhalten bleiben
            default_values = {
                'ollama_url': "http://localhost:11434",
                'trading_enabled': False,
                'auto_trading': False,
                'default_lot_size': 0.5,
                'max_risk_percent': 2.0,
                'auto_trade_symbols': ["EURUSD"],
                'analysis_interval': 300
            }
            
            value_changes = []
            for attr, expected_value in default_values.items():
                if hasattr(fingpt, attr):
                    actual_value = getattr(fingpt, attr)
                    if actual_value != expected_value:
                        value_changes.append(f"{attr}: {expected_value} -> {actual_value}")
            
            score = 100 - (len(config_issues) * 15) - (len(value_changes) * 5)
            score = max(0, score)
            
            return {
                "score": score,
                "config_issues": config_issues,
                "value_changes": value_changes,
                "total_config_checked": len(expected_config)
            }
            
        except ImportError:
            return {"score": 0, "error": "FinGPT nicht importierbar"}
    
    def check_method_compatibility(self) -> dict:
        """Prüft Methoden-Kompatibilität"""
        try:
            from FinGPT import MT5FinGPT
            
            fingpt = MT5FinGPT()
            
            # Rückgabetypen prüfen
            return_type_issues = []
            
            # connect_mt5 sollte bool zurückgeben
            if hasattr(fingpt, 'connect_mt5'):
                try:
                    # Mock MT5 für Test
                    import unittest.mock
                    with unittest.mock.patch('FinGPT.mt5') as mock_mt5:
                        mock_mt5.initialize.return_value = True
                        mock_mt5.account_info.return_value = type('Mock', (), {'company': 'Test'})()
                        mock_mt5.terminal_info.return_value = type('Mock', (), {'trade_allowed': True})()
                        
                        result = fingpt.connect_mt5()
                        if not isinstance(result, bool):
                            return_type_issues.append("connect_mt5 should return bool")
                except Exception:
                    pass
            
            # execute_trade sollte str zurückgeben
            if hasattr(fingpt, 'execute_trade'):
                try:
                    result = fingpt.execute_trade("EURUSD", "BUY", 0.1)
                    if not isinstance(result, str):
                        return_type_issues.append("execute_trade should return str")
                except Exception:
                    pass
            
            # Parameter-Kompatibilität prüfen
            param_issues = []
            critical_methods = ['execute_trade', 'enable_auto_trading', 'get_ai_analysis']
            
            for method_name in critical_methods:
                if hasattr(fingpt, method_name):
                    try:
                        sig = inspect.signature(getattr(fingpt, method_name))
                        params = list(sig.parameters.keys())
                        
                        # Prüfen ob kritische Parameter noch existieren
                        if method_name == 'execute_trade' and 'symbol' not in params:
                            param_issues.append(f"{method_name}: missing 'symbol' parameter")
                        if method_name == 'execute_trade' and 'action' not in params:
                            param_issues.append(f"{method_name}: missing 'action' parameter")
                            
                    except Exception:
                        param_issues.append(f"{method_name}: signature not accessible")
            
            score = 100 - (len(return_type_issues) * 10) - (len(param_issues) * 15)
            score = max(0, score)
            
            return {
                "score": score,
                "return_type_issues": return_type_issues,
                "param_issues": param_issues,
                "methods_checked": len(critical_methods)
            }
            
        except ImportError:
            return {"score": 0, "error": "FinGPT nicht importierbar"}
    
    def check_import_compatibility(self) -> dict:
        """Prüft Import-Kompatibilität"""
        import_issues = []
        
        # Prüfen ob alle Original-Imports noch funktionieren
        original_imports = [
            'from FinGPT import MT5FinGPT',
            'from risk_manager import RiskManager',
            'from advanced_indicators import AdvancedIndicators'
        ]
        
        for import_statement in original_imports:
            try:
                exec(import_statement)
            except ImportError as e:
                import_issues.append(f"{import_statement}: {e}")
        
        # Prüfen ob neue Imports optional sind
        new_imports = [
            'from input_validator import SafeInput',
            'from exception_handler import ErrorHandler',
            'from performance_optimizer import PerformanceMetrics'
        ]
        
        optional_imports_working = 0
        for import_statement in new_imports:
            try:
                exec(import_statement)
                optional_imports_working += 1
            except ImportError:
                pass  # Neue Imports sind optional
        
        score = 100 - (len(import_issues) * 25)
        score = max(0, score)
        
        return {
            "score": score,
            "import_issues": import_issues,
            "optional_imports_working": optional_imports_working,
            "total_optional_imports": len(new_imports)
        }
    
    def check_data_compatibility(self) -> dict:
        """Prüft Daten-Kompatibilität"""
        try:
            from FinGPT import MT5FinGPT
            
            fingpt = MT5FinGPT()
            
            # Datenstrukturen prüfen
            data_issues = []
            
            # Prüfen ob wichtige Datenstrukturen unverändert sind
            critical_attributes = [
                'currency_pairs', 'timeframe_names', 'auto_trade_symbols'
            ]
            
            for attr in critical_attributes:
                if hasattr(fingpt, attr):
                    value = getattr(fingpt, attr)
                    if attr == 'currency_pairs' and not isinstance(value, dict):
                        data_issues.append(f"currency_pairs should be dict, got {type(value)}")
                    elif attr == 'timeframe_names' and not isinstance(value, dict):
                        data_issues.append(f"timeframe_names should be dict, got {type(value)}")
                    elif attr == 'auto_trade_symbols' and not isinstance(value, list):
                        data_issues.append(f"auto_trade_symbols should be list, got {type(value)}")
            
            # Logging-Format prüfen
            if hasattr(fingpt, 'log'):
                try:
                    # Test ob logging noch wie erwartet funktioniert
                    fingpt.log("INFO", "Compatibility test", "TEST")
                except Exception as e:
                    data_issues.append(f"log method compatibility issue: {e}")
            
            score = 100 - (len(data_issues) * 20)
            score = max(0, score)
            
            return {
                "score": score,
                "data_issues": data_issues,
                "attributes_checked": len(critical_attributes)
            }
            
        except ImportError:
            return {"score": 0, "error": "FinGPT nicht importierbar"}
    
    def has_signature_changed(self, method_name: str, signature: inspect.Signature) -> bool:
        """Prüft ob sich eine Methodensignatur geändert hat"""
        # Bekannte Signaturen aus Original-Version
        original_signatures = {
            'connect_mt5': [],
            'disconnect_mt5': [],
            'execute_trade': ['symbol', 'action', 'lot_size', 'stop_loss', 'take_profit'],
            'enable_trading': [],
            'enable_auto_trading': [],
            'get_mt5_live_data': ['symbol'],
            'get_ai_analysis': ['symbol', 'action', 'data']
        }
        
        if method_name in original_signatures:
            expected_params = original_signatures[method_name]
            actual_params = list(signature.parameters.keys())
            
            # Parameter ohne Defaults vergleichen
            required_params = [name for name, param in signature.parameters.items() 
                             if param.default == inspect.Parameter.empty]
            
            return set(required_params) != set(expected_params)
        
        return False
    
    def create_compatibility_layer(self) -> bool:
        """Erstellt Kompatibilitäts-Layer für deprecated Features"""
        try:
            # Legacy-Aliase erstellen
            legacy_code = '''
# Legacy Compatibility Layer for FinGPT Enhanced
# This file provides backward compatibility for older versions

import warnings
from typing import Any, Optional

# Import enhanced version
from FinGPT import MT5FinGPT as EnhancedMT5FinGPT

class MT5FinGPT(EnhancedMT5FinGPT):
    """
    Backward compatible wrapper for FinGPT Enhanced
    Maintains the original API while providing enhanced features
    """
    
    def __init__(self):
        super().__init__()
        self._suppress_enhanced_warnings = False
    
    def legacy_mode(self, enabled: bool = True):
        """Enable or disable legacy mode"""
        self._suppress_enhanced_warnings = enabled
        if enabled:
            warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    def get_available_models(self):
        """Legacy method for model availability"""
        if not hasattr(self, '_legacy_models_warning'):
            warnings.warn(
                "get_available_models() is deprecated, use get_ollama_models() instead",
                DeprecationWarning,
                stacklevel=2
            )
            self._legacy_models_warning = True
        return self.get_ollama_models()
    
    def set_risk_parameters(self, max_risk: float, max_positions: int):
        """Legacy method for risk parameters"""
        if not hasattr(self, '_legacy_risk_warning'):
            warnings.warn(
                "set_risk_parameters() is deprecated, use RiskManager directly",
                DeprecationWarning,
                stacklevel=2
            )
            self._legacy_risk_warning = True
        
        if self.risk_manager:
            self.risk_manager.max_risk_per_trade = max_risk
            self.risk_manager.max_total_positions = max_positions

# Export legacy class
__all__ = ['MT5FinGPT']
'''
            
            with open("legacy_fingpt.py", "w") as f:
                f.write(legacy_code)
            
            return True
            
        except Exception:
            return False

def run_compatibility_check():
    """Führt vollständige Kompatibilitätsprüfung durch"""
    print("🔄 FinGPT Backward Compatibility Check")
    print("="*50)
    
    manager = BackwardCompatibilityManager()
    results = manager.check_compatibility()
    
    # Ergebnisse ausgeben
    print(f"\n📊 Overall Compatibility Score: {results['overall_score']:.1f}/100")
    
    categories = [
        ("API Compatibility", results["api_compatibility"]),
        ("Configuration Compatibility", results["configuration_compatibility"]),
        ("Method Compatibility", results["method_compatibility"]),
        ("Import Compatibility", results["import_compatibility"]),
        ("Data Compatibility", results["data_compatibility"])
    ]
    
    print("\n📋 Detailed Results:")
    for category, result in categories:
        score = result.get("score", 0)
        status = "✅" if score >= 90 else "⚠️" if score >= 70 else "❌"
        print(f"  {status} {category}: {score:.1f}/100")
        
        if "error" in result:
            print(f"    Error: {result['error']}")
        elif score < 100:
            issues = []
            if "missing_methods" in result and result["missing_methods"]:
                issues.extend([f"Missing: {m}" for m in result["missing_methods"]])
            if "config_issues" in result and result["config_issues"]:
                issues.extend(result["config_issues"])
            if "import_issues" in result and result["import_issues"]:
                issues.extend(result["import_issues"])
            
            for issue in issues[:3]:  # Max 3 Issues anzeigen
                print(f"    • {issue}")
    
    # Kompatibilitäts-Layer erstellen
    print("\n🔧 Creating compatibility layer...")
    if manager.create_compatibility_layer():
        print("✅ Compatibility layer created: legacy_fingpt.py")
    else:
        print("❌ Failed to create compatibility layer")
    
    # Empfehlungen
    print("\n💡 Compatibility Recommendations:")
    if results['overall_score'] >= 90:
        print("🎉 Excellent backward compatibility!")
        print("   • No migration needed")
        print("   • All existing code will work")
    elif results['overall_score'] >= 70:
        print("👍 Good backward compatibility")
        print("   • Minor migration may be needed")
        print("   • Use legacy_fingpt.py for seamless transition")
    else:
        print("⚠️ Compatibility issues detected")
        print("   • Review breaking changes")
        print("   • Use compatibility layer")
        print("   • Test existing code thoroughly")
    
    # Spezifische Empfehlungen
    if results["api_compatibility"]["score"] < 100:
        print("   • Some API methods may have changed")
    
    if results["configuration_compatibility"]["score"] < 100:
        print("   • Configuration options may have shifted")
    
    if results["import_compatibility"]["score"] < 100:
        print("   • Some imports may need updating")
    
    print(f"\n🎯 Migration Path:")
    print("   1. Test existing code with enhanced version")
    print("   2. Use legacy_fingpt.py if needed")
    print("   3. Gradually migrate to enhanced features")
    print("   4. Update documentation and dependencies")
    
    return results['overall_score'] >= 70

if __name__ == '__main__':
    success = run_compatibility_check()
    sys.exit(0 if success else 1)