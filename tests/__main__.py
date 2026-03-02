import os
import unittest

TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tests'))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=TESTS_DIR, pattern='test_*.py')

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
