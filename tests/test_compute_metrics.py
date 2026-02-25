import unittest
import sys
import os

# Add the code-audit directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code-audit'))
import codeaudit

class TestComputeMetrics(unittest.TestCase):
    def test_compute_metrics_with_modules(self):
        # Sample module data
        modules_data = [
            {
                "file": "app.py",
                "loc": 1200,
                "total_complexity": 150,
                "avg_complexity": 15,
                "function_count": 10,
                "max_complexity": 25
            },
            {
                "file": "utils.py",
                "loc": 800,
                "total_complexity": 80,
                "avg_complexity": 10,
                "function_count": 8,
                "max_complexity": 20
            }
        ]

        # Sample function data
        functions_data = [
            {"function": "main", "file": "app.py", "complexity": 25},
            {"function": "helper", "file": "app.py", "complexity": 10},
            {"function": "util_func", "file": "utils.py", "complexity": 20},
            {"function": "process_data", "file": "utils.py", "complexity": 8}
        ]

        result = codeaudit.compute_metrics_with_modules(modules_data, functions_data)

        # Check required fields
        self.assertIn("function_metrics", result)
        self.assertIn("module_metrics", result)
        self.assertIn("final_rp", result)

        # Check function metrics
        func_metrics = result["function_metrics"]
        self.assertIn("refactoring_pressure", func_metrics)
        self.assertIn("top_complexities", func_metrics)

        # Check module metrics
        mod_metrics = result["module_metrics"]
        self.assertIn("module_rp", mod_metrics)
        self.assertIn("top_modules", mod_metrics)

        # Check final RP
        self.assertIsInstance(result["final_rp"], int)
        self.assertGreaterEqual(result["final_rp"], 0)
        self.assertLessEqual(result["final_rp"], 100)

        # Check that final RP uses weighted average
        func_rp = func_metrics["refactoring_pressure"]
        mod_rp = mod_metrics["module_rp"]
        expected_final_rp = int(0.7 * func_rp + 0.3 * mod_rp)
        self.assertEqual(result["final_rp"], expected_final_rp)

    def test_compute_metrics_empty_data(self):
        # Test with empty data
        result = codeaudit.compute_metrics_with_modules([], [])
        self.assertIn("function_metrics", result)
        self.assertIn("module_metrics", result)
        self.assertIn("final_rp", result)
        self.assertEqual(result["final_rp"], 0)

    def test_input_validation_invalid_modules_data(self):
        """Test invalid modules_data input"""
        invalid_modules = "not a list"
        valid_functions = [{"function": "test", "file": "test.py", "complexity": 10}]

        with self.assertRaises((TypeError, ValueError)):
            codeaudit.compute_metrics_with_modules(invalid_modules, valid_functions)

    def test_input_validation_invalid_functions_data(self):
        """Test invalid functions_data input"""
        valid_modules = [{"file": "test.py", "loc": 100, "total_complexity": 50, "function_count": 5, "max_complexity": 20}]
        invalid_functions = "not a list"

        with self.assertRaises((TypeError, ValueError)):
            codeaudit.compute_metrics_with_modules(valid_modules, invalid_functions)

    def test_input_validation_none_data(self):
        """Test None input data"""
        with self.assertRaises((TypeError, ValueError)):
            codeaudit.compute_metrics_with_modules(None, None)

    def test_compute_metrics_function_weight_constant(self):
        """Test that function weight constant is used"""
        # This test will be implemented after adding constants
        pass

    def test_compute_metrics_module_weight_constant(self):
        """Test that module weight constant is used"""
        # This test will be implemented after adding constants
        pass

    def test_error_handling_calculate_mrp_failure(self):
        """Test error handling when calculate_mrp fails"""
        # Test with invalid module data that should cause calculate_mrp to fail
        invalid_modules = [{"file": "test.py", "loc": "invalid", "total_complexity": "invalid", "function_count": 5, "max_complexity": 20}]
        valid_functions = [{"function": "test", "file": "test.py", "complexity": 10}]

        # Should handle the error gracefully
        try:
            result = codeaudit.compute_metrics_with_modules(invalid_modules, valid_functions)
            # Should return a valid structure even with errors
            self.assertIn("function_metrics", result)
            self.assertIn("module_metrics", result)
            self.assertIn("final_rp", result)
        except Exception as e:
            self.fail(f"compute_metrics_with_modules should handle errors gracefully, but raised: {e}")

if __name__ == '__main__':
    unittest.main()