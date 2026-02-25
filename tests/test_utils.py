#!/usr/bin/env python3
import unittest
import sys
import os

# Добавляем путь к основному модулю
sys.path.insert(0, os.path.dirname(__file__) + '/../code-audit')

class TestUtils(unittest.TestCase):
    def test_count_lines(self):
        # Импортируем из основного модуля и проверяем функцию
        import codeaudit
        # Проверяем, что функция count_lines существует в модуле
        self.assertTrue(hasattr(codeaudit, 'count_lines'))

        # Получаем функцию
        count_lines = getattr(codeaudit, 'count_lines')

        # Тестируем
        result = count_lines("test_file.py")
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

if __name__ == '__main__':
    unittest.main()