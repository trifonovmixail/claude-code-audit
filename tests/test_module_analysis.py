#!/usr/bin/env python3
import unittest
import tempfile
import os
import sys

# Добавляем путь к основному модулю
sys.path.insert(0, os.path.dirname(__file__) + '/../code-audit')
import codeaudit

class TestModuleAnalysis(unittest.TestCase):

    def setUp(self):
        """Создаем временную директорию для тестов"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Удаляем временную директорию"""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_analyze_python_with_modules(self):
        """Тест анализа Python модулей"""
        # Создаем тестовый Python файл
        test_file = os.path.join(self.test_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("""
def simple_function():
    pass

def complex_function(a, b):
    if a > b:
        return a
    return b

def another_function():
    x = 1
    y = 2
    return x + y
""")

        # Тестируем функцию с модулями
        result = codeaudit.analyze_python_with_modules(self.test_dir)
        assert "modules" in result
        assert isinstance(result["modules"], list)
        assert "functions" in result
        assert isinstance(result["functions"], list)

if __name__ == '__main__':
    unittest.main()