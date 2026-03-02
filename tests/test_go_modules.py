import unittest
import tempfile
import os

from codeaudit import analyze_go_with_modules


class TestGoModules(unittest.TestCase):
    def setUp(self):
        # Create temporary Go project for testing
        self.temp_dir = tempfile.mkdtemp()
        self.create_test_go_files()

    def tearDown(self):
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_go_files(self):
        # Create main.go with functions
        main_content = '''package main

import "fmt"

func simpleFunction() {
    fmt.Println("Hello")
}

func complexFunction(x int, y string) bool {
    if x > 0 {
        if y == "test" {
            return true
        }
    }
    return false
}

func main() {
    simpleFunction()
    complexFunction(1, "test")
}
'''
        with open(os.path.join(self.temp_dir, "main.go"), 'w') as f:
            f.write(main_content)

    def test_analyze_go_with_modules(self):
        result = analyze_go_with_modules(self.temp_dir)
        self.assertIsInstance(result, dict)
        self.assertIn("modules", result)
        self.assertIn("functions", result)
        self.assertIsInstance(result["modules"], list)
        self.assertIsInstance(result["functions"], list)

        # Should find the main.go file
        if result["modules"]:
            module = result["modules"][0]
            self.assertIn("file", module)
            self.assertIn("loc", module)
            self.assertIn("total_complexity", module)
            self.assertIn("avg_complexity", module)
            self.assertIn("function_count", module)
            self.assertIn("max_complexity", module)

        # Should find functions
        if result["functions"]:
            func = result["functions"][0]
            self.assertIn("function", func)
            self.assertIn("file", func)
            self.assertIn("complexity", func)


if __name__ == '__main__':
    unittest.main()
