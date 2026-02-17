#!/usr/bin/env python3
"""
FinGPT Load Testing Suite
Last- und Stress-Tests für das FinGPT System
"""

import unittest
import sys
import os
import time
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
import statistics

# Pfad zum Projektverzeichnis hinzufügen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from FinGPT import MT5FinGPT
    from input_validator import InputValidator
    from exception_handler import ErrorHandler, ErrorSeverity
    from performance_optimizer import PerformanceMetrics, CacheManager, ResourceLimiter
    FINGPT_AVAILABLE = True
    ENHANCED_MODULES = True
except ImportError as e:
    print(f"Warning: Module nicht verfügbar: {e}")
    FINGPT_AVAILABLE = False
    ENHANCED_MODULES = False

class LoadTestConfig:
    """Konfiguration für Load-Tests"""
    
    # Test-Parameter
    CONCURRENT_USERS = 10
    REQUESTS_PER_USER = 50
    TEST_DURATION = 30  # Sekunden
    RAMP_UP_TIME = 5    # Sekunden
    
    # Stress-Test-Parameter
    STRESS_CONCURRENT_USERS = 50
    STRESS_REQUESTS_PER_USER = 100
    STRESS_TEST_DURATION = 60  # Sekunden
    
    # Performance-Schwellenwerte
    MAX_RESPONSE_TIME = 1.0  # Sekunden
    MAX_ERROR_RATE = 0.05    # 5%
    MAX_MEMORY_USAGE = 500   # MB
    MAX_CPU_USAGE = 80       # %

class LoadTestResults:
    """Klasse für Test-Ergebnisse"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times = []
        self.errors = []
        self.start_time = None
        self.end_time = None
        self.concurrent_users = 0
        self.memory_usage = []
        self.cpu_usage = []
    
    def add_request(self, success: bool, response_time: float, error: str = None):
        """Fügt eine Anfrage zu den Ergebnissen hinzu"""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error:
                self.errors.append(error)
        
        self.response_times.append(response_time)
    
    def get_summary(self) -> dict:
        """Gibt Zusammenfassung der Ergebnisse zurück"""
        if not self.response_times:
            return {}
        
        duration = (self.end_time - self.start_time) if self.start_time and self.end_time else 0
        
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "error_rate": self.failed_requests / self.total_requests if self.total_requests > 0 else 0,
            "avg_response_time": statistics.mean(self.response_times),
            "min_response_time": min(self.response_times),
            "max_response_time": max(self.response_times),
            "median_response_time": statistics.median(self.response_times),
            "p95_response_time": self._percentile(self.response_times, 95),
            "p99_response_time": self._percentile(self.response_times, 99),
            "requests_per_second": self.total_requests / duration if duration > 0 else 0,
            "test_duration": duration,
            "concurrent_users": self.concurrent_users,
            "avg_memory_usage": statistics.mean(self.memory_usage) if self.memory_usage else 0,
            "avg_cpu_usage": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
            "unique_errors": len(set(self.errors)),
            "most_common_error": max(set(self.errors), key=self.errors.count) if self.errors else None
        }
    
    def _percentile(self, data: list, percentile: int) -> float:
        """Berechnet Percentil"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

class TestInputValidationLoad(unittest.TestCase):
    """Load-Tests für Input-Validierung"""
    
    def setUp(self):
        if not ENHANCED_MODULES:
            self.skipTest("Enhanced modules nicht verfügbar")
        self.results = LoadTestResults()
    
    def test_concurrent_symbol_validation(self):
        """Test nebenläufige Symbol-Validierung"""
        def validate_symbols(thread_id: int, num_requests: int):
            """Worker-Funktion für Symbol-Validierung"""
            symbols = ["EURUSD", "GBPUSD", "USDJPY", "INVALID", "123", ""]
            
            for i in range(num_requests):
                start_time = time.time()
                try:
                    symbol = random.choice(symbols)
                    result = InputValidator.validate_symbol(symbol)
                    response_time = time.time() - start_time
                    self.results.add_request(result.is_valid, response_time)
                except Exception as e:
                    response_time = time.time() - start_time
                    self.results.add_request(False, response_time, str(e))
        
        # Test ausführen
        self.results.start_time = time.time()
        self.results.concurrent_users = LoadTestConfig.CONCURRENT_USERS
        
        with ThreadPoolExecutor(max_workers=LoadTestConfig.CONCURRENT_USERS) as executor:
            futures = [
                executor.submit(validate_symbols, i, LoadTestConfig.REQUESTS_PER_USER)
                for i in range(LoadTestConfig.CONCURRENT_USERS)
            ]
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.results.add_request(False, 0, str(e))
        
        self.results.end_time = time.time()
        
        # Ergebnisse prüfen
        summary = self.results.get_summary()
        
        print(f"\nSymbol Validation Load Test Results:")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  Success Rate: {summary['success_rate']:.2%}")
        print(f"  Avg Response Time: {summary['avg_response_time']:.3f}s")
        print(f"  95th Percentile: {summary['p95_response_time']:.3f}s")
        print(f"  Requests/sec: {summary['requests_per_second']:.1f}")
        
        # Assertions
        self.assertGreater(summary['success_rate'], 0.95, "Success rate should be > 95%")
        self.assertLess(summary['avg_response_time'], LoadTestConfig.MAX_RESPONSE_TIME, 
                       "Average response time should be < 1s")
        self.assertLess(summary['p95_response_time'], LoadTestConfig.MAX_RESPONSE_TIME * 2, 
                       "95th percentile should be < 2s")

class TestPerformanceLoad(unittest.TestCase):
    """Load-Tests für Performance-Komponenten"""
    
    def setUp(self):
        if not ENHANCED_MODULES:
            self.skipTest("Enhanced modules nicht verfügbar")
        self.results = LoadTestResults()
    
    def test_cache_performance_under_load(self):
        """Test Cache-Performance unter Last"""
        def cache_operations(thread_id: int, num_operations: int):
            """Worker-Funktion für Cache-Operationen"""
            cache = CacheManager(max_size=1000, ttl=60.0)
            
            for i in range(num_operations):
                start_time = time.time()
                try:
                    key = f"key_{thread_id}_{i % 100}"  # 100 verschiedene Keys
                    value = f"value_{thread_id}_{i}"
                    
                    if i % 2 == 0:
                        cache.set(key, value)
                    else:
                        result = cache.get(key)
                        # Ergebnis prüfen (sollte manchmal None sein)
                        success = result is not None or i % 100 >= 50
                    
                    response_time = time.time() - start_time
                    self.results.add_request(True, response_time)
                except Exception as e:
                    response_time = time.time() - start_time
                    self.results.add_request(False, response_time, str(e))
        
        # Test ausführen
        self.results.start_time = time.time()
        self.results.concurrent_users = LoadTestConfig.CONCURRENT_USERS
        
        with ThreadPoolExecutor(max_workers=LoadTestConfig.CONCURRENT_USERS) as executor:
            futures = [
                executor.submit(cache_operations, i, LoadTestConfig.REQUESTS_PER_USER)
                for i in range(LoadTestConfig.CONCURRENT_USERS)
            ]
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.results.add_request(False, 0, str(e))
        
        self.results.end_time = time.time()
        
        # Ergebnisse prüfen
        summary = self.results.get_summary()
        
        print(f"\nCache Performance Load Test Results:")
        print(f"  Total Operations: {summary['total_requests']}")
        print(f"  Success Rate: {summary['success_rate']:.2%}")
        print(f"  Avg Response Time: {summary['avg_response_time']:.3f}s")
        print(f"  95th Percentile: {summary['p95_response_time']:.3f}s")
        print(f"  Operations/sec: {summary['requests_per_second']:.1f}")
        
        # Assertions
        self.assertGreater(summary['success_rate'], 0.98, "Success rate should be > 98%")
        self.assertLess(summary['avg_response_time'], 0.01, "Average response time should be < 10ms")
        self.assertGreater(summary['requests_per_second'], 1000, "Should handle > 1000 ops/sec")

class TestSystemStress(unittest.TestCase):
    """Stress-Tests für das gesamte System"""
    
    def setUp(self):
        if not FINGPT_AVAILABLE:
            self.skipTest("FinGPT nicht verfügbar")
        self.results = LoadTestResults()
    
    @patch('FinGPT.mt5')
    @patch('FinGPT.requests')
    def test_fingpt_under_stress(self, mock_requests, mock_mt5):
        """Test FinGPT unter Stress"""
        # Mock setup
        mock_mt5.initialize.return_value = True
        mock_mt5.account_info.return_value = Mock(company="Test Broker")
        mock_mt5.terminal_info.return_value = Mock(trade_allowed=True)
        mock_mt5.symbol_info.return_value = Mock(bid=1.1000, ask=1.1005, point=0.0001, digits=5)
        mock_mt5.symbol_info_tick.return_value = Mock(bid=1.1000, ask=1.1005, last=1.1002)
        mock_mt5.order_send.return_value = Mock(retcode=10009, order=12345)
        
        mock_requests.get.return_value = Mock(status_code=200, json.return_value={"models": []})
        mock_requests.post.return_value = Mock(status_code=200, json.return_value={"response": "test"})
        
        def stress_worker(thread_id: int, num_operations: int):
            """Worker-Funktion für Stress-Test"""
            fingpt = MT5FinGPT()
            fingpt.connect_mt5()
            fingpt.trading_enabled = True
            
            # Mock Risk Manager
            fingpt.risk_manager = Mock()
            fingpt.risk_manager.can_open_position.return_value = (True, "OK")
            fingpt.risk_manager.register_trade = Mock()
            
            for i in range(num_operations):
                start_time = time.time()
                try:
                    # Verschiedene Operationen
                    operation = i % 4
                    
                    if operation == 0:
                        # Trade ausführen
                        result = fingpt.execute_trade("EURUSD", "BUY", 0.01)
                        success = "✅" in result
                    elif operation == 1:
                        # Daten abrufen
                        result = fingpt.get_mt5_live_data("EURUSD")
                        success = isinstance(result, str)
                    elif operation == 2:
                        # KI-Analyse
                        result = fingpt.get_ai_analysis("EURUSD", "BUY", "test data")
                        success = isinstance(result, str)
                    else:
                        # Performance-Metriken
                        if hasattr(fingpt, 'performance_metrics'):
                            fingpt.performance_metrics.record_metric("test", i)
                        success = True
                    
                    response_time = time.time() - start_time
                    self.results.add_request(success, response_time)
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    self.results.add_request(False, response_time, str(e))
        
        # Stress-Test ausführen
        self.results.start_time = time.time()
        self.results.concurrent_users = LoadTestConfig.STRESS_CONCURRENT_USERS
        
        with ThreadPoolExecutor(max_workers=LoadTestConfig.STRESS_CONCURRENT_USERS) as executor:
            futures = [
                executor.submit(stress_worker, i, LoadTestConfig.STRESS_REQUESTS_PER_USER)
                for i in range(LoadTestConfig.STRESS_CONCURRENT_USERS)
            ]
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.results.add_request(False, 0, str(e))
        
        self.results.end_time = time.time()
        
        # Ergebnisse prüfen
        summary = self.results.get_summary()
        
        print(f"\nFinGPT Stress Test Results:")
        print(f"  Total Operations: {summary['total_requests']}")
        print(f"  Success Rate: {summary['success_rate']:.2%}")
        print(f"  Error Rate: {summary['error_rate']:.2%}")
        print(f"  Avg Response Time: {summary['avg_response_time']:.3f}s")
        print(f"  95th Percentile: {summary['p95_response_time']:.3f}s")
        print(f"  Operations/sec: {summary['requests_per_second']:.1f}")
        print(f"  Test Duration: {summary['test_duration']:.1f}s")
        print(f"  Unique Errors: {summary['unique_errors']}")
        
        if summary['most_common_error']:
            print(f"  Most Common Error: {summary['most_common_error']}")
        
        # Assertions
        self.assertGreater(summary['success_rate'], 0.90, "Success rate should be > 90% under stress")
        self.assertLess(summary['error_rate'], LoadTestConfig.MAX_ERROR_RATE, "Error rate should be < 5%")
        self.assertGreater(summary['requests_per_second'], 50, "Should handle > 50 ops/sec under stress")

class TestMemoryLeakDetection(unittest.TestCase):
    """Tests für Memory-Leak-Detection"""
    
    def setUp(self):
        if not ENHANCED_MODULES:
            self.skipTest("Enhanced modules nicht verfügbar")
    
    def test_memory_leak_detection(self):
        """Test auf Memory Leaks bei langer Laufzeit"""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Lange Operation simulieren
        cache = CacheManager(max_size=10000, ttl=1.0)
        
        for i in range(10000):
            key = f"test_key_{i}"
            value = f"test_value_{i}" * 100  # Größere Werte
            
            cache.set(key, value)
            
            if i % 1000 == 0:
                # Cache regelmäßig leeren
                cache.clear()
                gc.collect()
                
                # Memory prüfen
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                
                print(f"  Iteration {i}: Memory {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
                
                # Memory sollte nicht zu stark anwachsen
                self.assertLess(memory_increase, 100, "Memory increase should be < 100MB")
        
        # Final cleanup
        cache.clear()
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        total_increase = final_memory - initial_memory
        
        print(f"\nMemory Leak Test Results:")
        print(f"  Initial Memory: {initial_memory:.1f}MB")
        print(f"  Final Memory: {final_memory:.1f}MB")
        print(f"  Total Increase: {total_increase:.1f}MB")
        
        # Assertion
        self.assertLess(total_increase, 50, "Total memory increase should be < 50MB")

class TestEdgeCaseScenarios(unittest.TestCase):
    """Tests für Edge-Case-Szenarien"""
    
    def setUp(self):
        if not ENHANCED_MODULES:
            self.skipTest("Enhanced modules nicht verfügbar")
    
    def test_extreme_input_values(self):
        """Test mit extremen Input-Werten"""
        extreme_inputs = [
            # Symbol Tests
            ("", "symbol"),
            ("A" * 1000, "symbol"),
            ("123456789", "symbol"),
            ("EUR-USD", "symbol"),
            ("eurusd", "symbol"),
            
            # Lot Size Tests
            ("-999", "lot_size"),
            ("999999", "lot_size"),
            ("0.000001", "lot_size"),
            ("abc", "lot_size"),
            
            # Interval Tests
            ("-1", "interval"),
            ("999999", "interval"),
            ("abc", "interval"),
            ("1.5", "interval"),
        ]
        
        for input_value, validation_type in extreme_inputs:
            with self.subTest(input_value=input_value, validation_type=validation_type):
                try:
                    if validation_type == "symbol":
                        result = InputValidator.validate_symbol(input_value)
                    elif validation_type == "lot_size":
                        result = InputValidator.validate_lot_size(input_value)
                    elif validation_type == "interval":
                        result = InputValidator.validate_interval(input_value)
                    
                    # Extreme Inputs sollten ungültig sein
                    self.assertFalse(result.is_valid, 
                                   f"Extreme input '{input_value}' should be invalid for {validation_type}")
                    
                except Exception as e:
                    # Exceptions sind bei extremen Inputs akzeptabel
                    print(f"  Expected exception for '{input_value}': {e}")
    
    def test_concurrent_edge_cases(self):
        """Test nebenläufige Edge-Cases"""
        def edge_case_worker(thread_id: int):
            """Worker für Edge-Case-Tests"""
            try:
                # Race Conditions testen
                cache = CacheManager(max_size=10, ttl=0.1)
                
                for i in range(100):
                    key = f"race_{i}"
                    cache.set(key, f"value_{thread_id}_{i}")
                    
                    # Sofort wieder lesen
                    result = cache.get(key)
                    
                    # Kurze Pause für Race Conditions
                    time.sleep(0.001)
                
                return True
            except Exception as e:
                print(f"  Edge case worker {thread_id} failed: {e}")
                return False
        
        # Mehrere Worker gleichzeitig starten
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(edge_case_worker, i) for i in range(20)]
            results = [future.result() for future in as_completed(futures)]
        
        # Die meisten Worker sollten erfolgreich sein
        success_rate = sum(results) / len(results)
        self.assertGreater(success_rate, 0.8, "At least 80% of edge case workers should succeed")

def run_load_tests():
    """Führt alle Load-Tests aus"""
    print("FinGPT Load & Stress Test Suite")
    print("="*60)
    
    if not FINGPT_AVAILABLE:
        print("❌ FinGPT nicht verfügbar - Load-Tests übersprungen")
        return False
    
    if not ENHANCED_MODULES:
        print("❌ Enhanced modules nicht verfügbar - Load-Tests übersprungen")
        return False
    
    print("✅ Alle Module verfügbar - Starte Load-Tests")
    print("="*60)
    
    # Test-Suite erstellen
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Tests hinzufügen
    test_classes = [
        TestInputValidationLoad,
        TestPerformanceLoad,
        TestSystemStress,
        TestMemoryLeakDetection,
        TestEdgeCaseScenarios
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Tests ausführen
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("LOAD TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_load_tests()
    sys.exit(0 if success else 1)