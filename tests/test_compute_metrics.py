import unittest

class TestComputeMetrics(unittest.TestCase):
    def test_compute_metrics_with_modules(self):
        from codeaudit.codeaudit import compute_metrics_with_modules

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

        result = compute_metrics_with_modules(modules_data, functions_data)

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
        from codeaudit.codeaudit import compute_metrics_with_modules

        # Test with empty data
        result = compute_metrics_with_modules([], [])
        self.assertIn("function_metrics", result)
        self.assertIn("module_metrics", result)
        self.assertIn("final_rp", result)
        self.assertEqual(result["final_rp"], 0)