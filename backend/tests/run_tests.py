import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def run_all_tests():
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(Path(__file__).parent), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    print("\n" + "=" * 60)
    print(" PRISM LAB RAG SUBSYSTEM — TEST SUITE EXECUTION")
    print("=" * 60)
    result = runner.run(suite)
    print("=" * 60)
    if result.wasSuccessful():
        print(" ALL PRISM RAG TESTS PASSED SUCCESSFULLY!")
        print("=" * 60 + "\n")
        return 0
    else:
        print(f" TESTS FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
