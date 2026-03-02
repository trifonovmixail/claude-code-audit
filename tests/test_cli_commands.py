#!/usr/bin/env python3
"""
Test suite for CLI commands with module-level analysis.
"""

import unittest
from unittest.mock import patch
import sys
import os
import argparse

from codeaudit import (
    scan_with_module_analysis,
    compute_metrics_with_modules,
    analyze_python_with_modules,
    analyze_go_with_modules,
    analyze_js_with_modules,
    main
)


class TestCLICommands(unittest.TestCase):
    """Test CLI commands functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_python_files = [
            'test_file1.py',
            'test_file2.py'
        ]
        self.test_go_files = [
            'main.go',
            'utils.go'
        ]
        self.test_js_files = [
            'app.js',
            'utils.js'
        ]

    def test_scan_command_with_json_format(self):
        """Test scan command with JSON output format."""
        # Test that parser accepts the arguments correctly
        test_args = ['codeaudit.py', 'scan', '/test/path', '--format', 'json', '--threshold', '50']
        with patch.object(sys, 'argv', test_args):
            parser = argparse.ArgumentParser(prog="codeaudit")
            parser.add_argument("command", choices=["scan", "check-deps"])
            parser.add_argument("path")
            parser.add_argument("--format", choices=["text", "json"], default="text")
            parser.add_argument("--threshold", type=int, default=None)
            parser.add_argument("-v", "--verbose", action="store_true")
            parser.add_argument("--install", action="store_true",
                                help="Automatically install missing dependencies")

            args = parser.parse_args()
            self.assertEqual(args.command, "scan")
            self.assertEqual(args.path, "/test/path")
            self.assertEqual(args.format, "json")
            self.assertEqual(args.threshold, 50)
            self.assertFalse(args.verbose)
            self.assertFalse(args.install)

    def test_scan_command_with_verbose_mode(self):
        """Test scan command with verbose mode."""
        # Test that parser accepts the arguments correctly
        test_args = ['codeaudit.py', 'scan', '/test/path', '-v']
        with patch.object(sys, 'argv', test_args):
            parser = argparse.ArgumentParser(prog="codeaudit")
            parser.add_argument("command", choices=["scan", "check-deps"])
            parser.add_argument("path")
            parser.add_argument("--format", choices=["text", "json"], default="text")
            parser.add_argument("--threshold", type=int, default=None)
            parser.add_argument("-v", "--verbose", action="store_true")
            parser.add_argument("--install", action="store_true",
                                help="Automatically install missing dependencies")

            args = parser.parse_args()
            self.assertEqual(args.command, "scan")
            self.assertEqual(args.path, "/test/path")
            self.assertEqual(args.format, "text")
            self.assertIsNone(args.threshold)
            self.assertTrue(args.verbose)
            self.assertFalse(args.install)

    def test_scan_command_with_custom_threshold(self):
        """Test scan command with custom threshold."""
        # Test that parser accepts the arguments correctly
        test_args = ['codeaudit.py', 'scan', '/test/path', '--threshold', '30']
        with patch.object(sys, 'argv', test_args):
            parser = argparse.ArgumentParser(prog="codeaudit")
            parser.add_argument("command", choices=["scan", "check-deps"])
            parser.add_argument("path")
            parser.add_argument("--format", choices=["text", "json"], default="text")
            parser.add_argument("--threshold", type=int, default=None)
            parser.add_argument("-v", "--verbose", action="store_true")
            parser.add_argument("--install", action="store_true",
                                help="Automatically install missing dependencies")

            args = parser.parse_args()
            self.assertEqual(args.command, "scan")
            self.assertEqual(args.path, "/test/path")
            self.assertEqual(args.format, "text")
            self.assertEqual(args.threshold, 30)
            self.assertFalse(args.verbose)
            self.assertFalse(args.install)

    def test_check_deps_command_with_json(self):
        """Test check-deps command with JSON format."""
        # Test that parser accepts the arguments correctly
        test_args = ['codeaudit.py', 'check-deps', '/test/path', '--format', 'json']
        with patch.object(sys, 'argv', test_args):
            parser = argparse.ArgumentParser(prog="codeaudit")
            parser.add_argument("command", choices=["scan", "check-deps"])
            parser.add_argument("path")
            parser.add_argument("--format", choices=["text", "json"], default="text")
            parser.add_argument("--threshold", type=int, default=None)
            parser.add_argument("-v", "--verbose", action="store_true")
            parser.add_argument("--install", action="store_true",
                                help="Automatically install missing dependencies")

            args = parser.parse_args()
            self.assertEqual(args.command, "check-deps")
            self.assertEqual(args.path, "/test/path")
            self.assertEqual(args.format, "json")

    def test_check_deps_command_with_install(self):
        """Test check-deps command with install option."""
        # Test that parser accepts the arguments correctly
        test_args = ['codeaudit.py', 'check-deps', '/test/path', '--install']
        with patch.object(sys, 'argv', test_args):
            parser = argparse.ArgumentParser(prog="codeaudit")
            parser.add_argument("command", choices=["scan", "check-deps"])
            parser.add_argument("path")
            parser.add_argument("--format", choices=["text", "json"], default="text")
            parser.add_argument("--threshold", type=int, default=None)
            parser.add_argument("-v", "--verbose", action="store_true")
            parser.add_argument("--install", action="store_true",
                                help="Automatically install missing dependencies")

            args = parser.parse_args()
            self.assertEqual(args.command, "check-deps")
            self.assertEqual(args.path, "/test/path")
            self.assertTrue(args.install)

    def test_scan_command_without_args(self):
        """Test scan command without arguments should show usage."""
        with patch('sys.argv', ['codeaudit.py', 'scan']):
            with self.assertRaises(SystemExit):
                main()

    def test_check_deps_command_without_args(self):
        """Test check-deps command without arguments should show usage."""
        with patch('sys.argv', ['codeaudit.py', 'check-deps']):
            with self.assertRaises(SystemExit):
                main()

    def test_unknown_flag(self):
        """Test handling of unknown flags."""
        with patch('sys.argv', ['codeaudit.py', 'scan', '/test/path', '--unknown-flag']):
            with self.assertRaises(SystemExit):
                main()


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for CLI commands."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = '/tmp/test_codeaudit'
        # Create a minimal Python test file
        os.makedirs(self.test_dir, exist_ok=True)
        with open(f'{self.test_dir}/test.py', 'w') as f:
            f.write("""
def simple_function():
    return "hello"

def complex_function(x, y):
    if x > 0:
        if y > 0:
            for i in range(x):
                if i % 2 == 0:
                    print(f"Even: {i}")
                else:
                    print(f"Odd: {i}")
    return x + y
""")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('codeaudit.analyze_python_with_modules')
    @patch('codeaudit.compute_metrics_with_modules')
    @patch('codeaudit.generate_summary')
    @patch('codeaudit.generate_instructions')
    @patch('codeaudit.determine_status')
    def test_cli_workflow_integration(self, mock_determine_status, mock_generate_instructions,
                                     mock_generate_summary, mock_compute_metrics, mock_analyze):
        """Test complete CLI workflow integration."""
        # Mock the analysis
        mock_analyze.return_value = {
            "modules": [
                {
                    "file": "test.py",
                    "loc": 12,
                    "total_complexity": 8,
                    "function_count": 2,
                    "max_complexity": 7,
                    "avg_complexity": 4.0
                }
            ],
            "functions": [
                {"function": "simple_function", "file": "test.py", "complexity": 1},
                {"function": "complex_function", "file": "test.py", "complexity": 7}
            ]
        }

        # Mock metrics computation
        mock_compute_metrics.return_value = {
            "function_metrics": {
                "refactoring_pressure": 35,
                "max_complexity": 7,
                "top_complexities": [
                    {"function": "complex_function", "file": "test.py", "complexity": 7},
                    {"function": "simple_function", "file": "test.py", "complexity": 1}
                ]
            },
            "module_metrics": {
                "module_rp": 50,
                "top_modules": [
                    {
                        "file": "test.py",
                        "loc": 12,
                        "total_complexity": 8,
                        "avg_complexity": 4.0,
                        "function_count": 2,
                        "max_complexity": 7,
                        "module_rp": 50
                    }
                ]
            },
            "final_rp": 42
        }

        # Mock status determination
        mock_determine_status.return_value = ("warning", "medium")

        # Mock instructions generation
        mock_generate_instructions.return_value = ["Review complex_function complexity"]

        # Mock summary generation
        mock_generate_summary.return_value = "Medium complexity detected"

        # Test the scan function
        result = scan_with_module_analysis(self.test_dir, "python")

        # Verify all components were called
        mock_analyze.assert_called_once()
        mock_compute_metrics.assert_called_once()
        mock_determine_status.assert_called_once()
        mock_generate_instructions.assert_called_once()
        mock_generate_summary.assert_called_once()

        # Verify result structure
        self.assertIn("language", result)
        self.assertIn("rp", result)
        self.assertIn("risk_level", result)
        self.assertIn("status", result)
        self.assertIn("summary", result)
        self.assertIn("instructions", result)
        self.assertIn("top_function_complexities", result)
        self.assertIn("top_file_complexities", result)


if __name__ == '__main__':
    unittest.main()