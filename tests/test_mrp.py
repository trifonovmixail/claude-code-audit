import unittest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'code-audit'))
import codeaudit

class TestMRPCalculation(unittest.TestCase):
    def test_calculate_mrp_basic(self):
        module_data = {
            "total_complexity": 150,
            "max_complexity": 30,
            "loc": 1200
        }
        result = codeaudit.calculate_mrp(module_data)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    def test_calculate_mrp_zero_loc(self):
        module_data = {
            "total_complexity": 100,
            "max_complexity": 20,
            "loc": 0
        }
        result = codeaudit.calculate_mrp(module_data)
        self.assertIsInstance(result, int)

    def test_calculate_mrp_boundary_values(self):
        # Test with very large LOC
        module_data = {
            "total_complexity": 5000,
            "max_complexity": 100,
            "loc": 10000
        }
        result = codeaudit.calculate_mrp(module_data)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)