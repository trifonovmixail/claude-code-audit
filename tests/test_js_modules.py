import unittest
import tempfile
import os

from codeaudit import analyze_js_with_modules


class TestJSModules(unittest.TestCase):
    def setUp(self):
        # Create temporary JS project for testing
        self.temp_dir = tempfile.mkdtemp()
        self.create_test_js_files()

    def tearDown(self):
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_js_files(self):
        # Create main.js with functions
        main_content = '''// Simple function
function simpleFunction() {
    console.log("Hello");
}

// Complex function with multiple conditions
function complexFunction(x, y) {
    if (x > 0) {
        if (y === "test") {
            return true;
        }
        for (let i = 0; i < x; i++) {
            console.log(i);
        }
    }
    return false;
}

// Arrow function
const arrowFunction = (param) => {
    return param * 2;
};

// Export functions
module.exports = {
    simpleFunction,
    complexFunction,
    arrowFunction
};
'''
        with open(os.path.join(self.temp_dir, "main.js"), 'w') as f:
            f.write(main_content)

    def test_analyze_js_with_modules(self):
        result = analyze_js_with_modules(self.temp_dir)
        self.assertIsInstance(result, dict)
        self.assertIn("modules", result)
        self.assertIn("functions", result)
        self.assertIsInstance(result["modules"], list)
        self.assertIsInstance(result["functions"], list)

        # Should find the main.js file
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
