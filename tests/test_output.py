# tests/test_output.py
import unittest
import tempfile
import os

from codeaudit import scan_with_module_analysis


class TestOutputStructure(unittest.TestCase):
    def setUp(self):
        # Create temporary project for testing
        self.temp_dir = tempfile.mkdtemp()
        self.create_test_files()

    def tearDown(self):
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_files(self):
        # Create a simple Python file for testing
        py_content = '''def simple_function():
    return True

def complex_function(x, y):
    if x > 0:
        for i in range(y):
            print(i)
    return False
'''
        with open(os.path.join(self.temp_dir, "test.py"), 'w') as f:
            f.write(py_content)

    def test_json_output_structure(self):
        result = scan_with_module_analysis(self.temp_dir, "python")

        # Check required top-level fields
        self.assertIn("language", result)
        self.assertIn("status", result)
        self.assertIn("risk_level", result)
        self.assertIn("rp", result)
        self.assertIn("function_rp", result)
        self.assertIn("module_rp", result)

        # Check new structure fields
        self.assertIn("top_function_complexities", result)
        self.assertIn("top_file_complexities", result)
        self.assertIn("instructions", result)
        self.assertIn("summary", result)

        # Check top_function_complexities structure
        if result["top_function_complexities"]:
            func = result["top_function_complexities"][0]
            self.assertIn("function", func)
            self.assertIn("file", func)
            self.assertIn("complexity", func)

        # Check top_file_complexities structure
        if result["top_file_complexities"]:
            module = result["top_file_complexities"][0]
            self.assertIn("file", module)
            self.assertIn("loc", module)
            self.assertIn("total_complexity", module)
            self.assertIn("avg_complexity", module)
            self.assertIn("function_count", module)
            self.assertIn("max_complexity", module)
            self.assertIn("module_rp", module)

        # Check instructions are list
        self.assertIsInstance(result["instructions"], list)
        self.assertLessEqual(len(result["instructions"]), 10)

        # Check summary is string
        self.assertIsInstance(result["summary"], str)
        self.assertLessEqual(len(result["summary"]), 150)

        # Check status and risk level
        valid_statuses = ["ok", "warning", "critical"]
        valid_risk_levels = ["low", "medium", "high", "critical"]
        self.assertIn(result["status"], valid_statuses)
        self.assertIn(result["risk_level"], valid_risk_levels)

        # Check RP values
        self.assertGreaterEqual(result["rp"], 0)
        self.assertLessEqual(result["rp"], 100)
        self.assertGreaterEqual(result["function_rp"], 0)
        self.assertLessEqual(result["function_rp"], 100)
        self.assertGreaterEqual(result["module_rp"], 0)
        self.assertLessEqual(result["module_rp"], 100)


if __name__ == '__main__':
    unittest.main()
