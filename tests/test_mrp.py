import unittest
import sys
import os

import codeaudit


class TestMRPCalculation(unittest.TestCase):
    def test_calculate_mrp_basic(self):
        """Test basic MRP calculation with valid inputs"""
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
        """Test MRP calculation with zero LOC"""
        module_data = {
            "total_complexity": 100,
            "max_complexity": 20,
            "loc": 0
        }
        result = codeaudit.calculate_mrp(module_data)
        self.assertIsInstance(result, int)
        # With zero LOC, complexity_density should be 0, so result should be 8
        expected = int(0.4 * 0 + 0.4 * 20 + 0.2 * 0)
        self.assertEqual(result, expected)

    def test_calculate_mrp_boundary_values(self):
        """Test MRP with extreme values"""
        # Test with very large LOC
        module_data = {
            "total_complexity": 5000,
            "max_complexity": 100,
            "loc": 10000
        }
        result = codeaudit.calculate_mrp(module_data)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    def test_calculate_mrp_formula_component_verification(self):
        """Test each component of the MRP formula separately"""
        # Test complexity density component
        module_data = {
            "total_complexity": 200,
            "max_complexity": 0,
            "loc": 1000
        }
        result = codeaudit.calculate_mrp(module_data)
        # complexity_density = (200/1000)*100 = 20
        # MRP = 0.4*20 + 0.4*0 + 0.2*5 = 9 (after int conversion)
        expected = 9
        self.assertEqual(result, expected)

        # Test max_complexity component
        module_data = {
            "total_complexity": 0,
            "max_complexity": 50,
            "loc": 1000
        }
        result = codeaudit.calculate_mrp(module_data)
        # complexity_density = 0
        # MRP = 0.4*0 + 0.4*50 + 0.2*5 = 21 (after int conversion)
        expected = 21
        self.assertEqual(result, expected)

        # Test LOC factor component
        module_data = {
            "total_complexity": 0,
            "max_complexity": 0,
            "loc": 3000
        }
        result = codeaudit.calculate_mrp(module_data)
        # complexity_density = 0
        # loc_factor for 3000 LOC = 10
        # MRP = 0.4*0 + 0.4*0 + 0.2*10 = 2
        expected = 2
        self.assertEqual(result, expected)

    def test_calculate_mrp_invalid_types(self):
        """Test MRP with invalid input types"""
        # Test with non-dict input
        with self.assertRaises(TypeError):
            codeaudit.calculate_mrp("not a dict")

        with self.assertRaises(TypeError):
            codeaudit.calculate_mrp(123)

        with self.assertRaises(TypeError):
            codeaudit.calculate_mrp(None)

    def test_calculate_mrp_missing_keys(self):
        """Test MRP with missing required keys"""
        # Test missing total_complexity
        module_data = {
            "max_complexity": 30,
            "loc": 1200
        }
        result = codeaudit.calculate_mrp(module_data)
        # Should use default value 0 for missing total_complexity
        expected = int(0.4 * 0 + 0.4 * 30 + 0.2 * 5)  # LOC factor applies
        self.assertEqual(result, expected)

        # Test missing max_complexity
        module_data = {
            "total_complexity": 150,
            "loc": 1200
        }
        result = codeaudit.calculate_mrp(module_data)
        # Should use default value 0 for missing max_complexity
        expected = int(0.4 * 12.5 + 0.4 * 0 + 0.2 * 5)  # LOC factor applies
        self.assertEqual(result, expected)

        # Test missing loc
        module_data = {
            "total_complexity": 150,
            "max_complexity": 30
        }
        result = codeaudit.calculate_mrp(module_data)
        # Should use default value 0 for missing loc
        expected = int(0.4 * 0 + 0.4 * 30 + 0.2 * 0)
        self.assertEqual(result, expected)

    def test_calculate_mrp_negative_values(self):
        """Test MRP with negative values"""
        # Test negative total_complexity (should be clamped to 0)
        module_data = {
            "total_complexity": -100,
            "max_complexity": 30,
            "loc": 1200
        }
        result = codeaudit.calculate_mrp(module_data)
        # total_complexity is clamped to 0, so:
        # complexity_density = 0, max_complexity = 30, loc_factor = 5
        # MRP = 0.4*0 + 0.4*30 + 0.2*5 = 13
        expected = 13
        self.assertEqual(result, expected)

        # Test negative max_complexity (should be clamped to 0)
        module_data = {
            "total_complexity": 150,
            "max_complexity": -20,
            "loc": 1200
        }
        result = codeaudit.calculate_mrp(module_data)
        # max_complexity is clamped to 0, so:
        # complexity_density = 12.5, max_complexity = 0, loc_factor = 5
        # MRP = 0.4*12.5 + 0.4*0 + 0.2*5 = 6.0 (after int conversion)
        expected = 6
        self.assertEqual(result, expected)

    def test_calculate_mrp_boundary_loc_values(self):
        """Test LOC factor boundaries"""
        # Test just below 1000 (no LOC factor)
        module_data = {
            "total_complexity": 1000,
            "max_complexity": 50,
            "loc": 999
        }
        result = codeaudit.calculate_mrp(module_data)
        expected = int(0.4 * 100.1 + 0.4 * 50 + 0.2 * 0)
        self.assertEqual(result, expected)

        # Test exactly 1000 (LOC factor = 5)
        module_data = {
            "total_complexity": 1000,
            "max_complexity": 50,
            "loc": 1000
        }
        result = codeaudit.calculate_mrp(module_data)
        expected = int(0.4 * 100 + 0.4 * 50 + 0.2 * 5)
        self.assertEqual(result, expected)

        # Test just below 2000 (LOC factor = 5)
        module_data = {
            "total_complexity": 2000,
            "max_complexity": 50,
            "loc": 1999
        }
        result = codeaudit.calculate_mrp(module_data)
        expected = int(0.4 * 100.05 + 0.4 * 50 + 0.2 * 5)
        self.assertEqual(result, expected)

        # Test exactly 2000 (LOC factor = 10)
        module_data = {
            "total_complexity": 2000,
            "max_complexity": 50,
            "loc": 2000
        }
        result = codeaudit.calculate_mrp(module_data)
        expected = int(0.4 * 100 + 0.4 * 50 + 0.2 * 10)
        self.assertEqual(result, expected)

        # Test exactly 5000 (LOC factor = 15)
        module_data = {
            "total_complexity": 5000,
            "max_complexity": 50,
            "loc": 5000
        }
        result = codeaudit.calculate_mrp(module_data)
        expected = int(0.4 * 100 + 0.4 * 50 + 0.2 * 15)
        self.assertEqual(result, expected)

    def test_calculate_mrp_maximum_possible_value(self):
        """Test MRP with maximum possible values"""
        module_data = {
            "total_complexity": 10000,
            "max_complexity": 100,
            "loc": 1  # Very small LOC to maximize complexity_density
        }
        result = codeaudit.calculate_mrp(module_data)
        # complexity_density = (10000/1)*100 = 1000000
        # MRP = 0.4*1000000 + 0.4*100 + 0.2*0 = 400040 (should be clamped to 100)
        self.assertEqual(result, 100)

    def test_calculate_mrp_with_none_values(self):
        """Test MRP with None values"""
        module_data = {
            "total_complexity": None,
            "max_complexity": None,
            "loc": None
        }
        result = codeaudit.calculate_mrp(module_data)
        # Should use default values (0) for None
        expected = 0
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
