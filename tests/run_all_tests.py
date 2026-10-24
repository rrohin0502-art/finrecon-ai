import unittest
import sys
from pathlib import Path

# Fix Windows console UTF-8 output encoding
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tests.test_normalizer import TestNormalizer
from tests.test_deterministic import TestDeterministicMatcher
from tests.test_fuzzy import TestFuzzyMatcher
from tests.test_fee_deduction import TestFeeDeductionMatcher
from tests.test_batch_resolver import TestBatchResolver
from tests.test_anomaly_detector import TestAnomalyDetector

def run_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestNormalizer))
    suite.addTests(loader.loadTestsFromTestCase(TestDeterministicMatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestFuzzyMatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestFeeDeductionMatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestBatchResolver))
    suite.addTests(loader.loadTestsFromTestCase(TestAnomalyDetector))

    print("\n" + "=" * 65)
    print("[*] FinRecon-AI: Executing Comprehensive Test Suite")
    print("=" * 65 + "\n")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 65)
    if result.wasSuccessful():
        print(f"[OK] ALL {result.testsRun} TESTS PASSED SUCCESSFULLY!")
        print("=" * 65 + "\n")
        return 0
    else:
        print(f"[FAIL] TEST SUITE FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
        print("=" * 65 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(run_suite())

