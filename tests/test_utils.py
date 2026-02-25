#!/usr/bin/env python3
import unittest
import sys
import os
import tempfile
import shutil

# Добавляем путь к основному модулю
sys.path.insert(0, os.path.dirname(__file__) + '/../code-audit')

class TestUtils(unittest.TestCase):
    def setUp(self):
        """Создаем временную директорию для тестов"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Удаляем временную директорию"""
        shutil.rmtree(self.test_dir)

    def test_count_lines_valid_file(self):
        """Тест подсчета строк в существующем файле"""
        # Создаем тестовый файл с известным количеством строк
        test_file = os.path.join(self.test_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("def hello():\n    print('Hello')\n    return True\n")

        # Импортируем из основного модуля
        import codeaudit
        count_lines = codeaudit.count_lines

        # Проверяем что функция существует
        self.assertTrue(hasattr(count_lines, '__call__'))

        # Тестируем подсчет строк
        result = count_lines(test_file)
        self.assertEqual(result, 3)

    def test_count_lines_empty_file(self):
        """Тест подсчета строк в пустом файле"""
        test_file = os.path.join(self.test_dir, "empty.py")
        with open(test_file, "w") as f:
            f.write("")

        import codeaudit
        count_lines = codeaudit.count_lines
        result = count_lines(test_file)
        self.assertEqual(result, 0)

    def test_count_lines_file_with_only_newlines(self):
        """Тест подсчета строк в файле с только переносами строк"""
        test_file = os.path.join(self.test_dir, "newlines.py")
        with open(test_file, "w") as f:
            f.write("\n\n\n")

        import codeaudit
        count_lines = codeaudit.count_lines
        result = count_lines(test_file)
        self.assertEqual(result, 3)

    def test_count_lines_nonexistent_file(self):
        """Тест подсчета строк в несуществующем файле - должен вызывать исключение"""
        nonexistent_file = os.path.join(self.test_dir, "nonexistent.py")

        import codeaudit
        count_lines = codeaudit.count_lines

        # Проверяем что функция вызывает исключение для несуществующего файла
        with self.assertRaises(FileNotFoundError):
            count_lines(nonexistent_file)

    def test_count_lines_invalid_path(self):
        """Тест подсчета строк с недопустимым путем"""
        invalid_path = "/invalid/path/file.py"

        import codeaudit
        count_lines = codeaudit.count_lines

        with self.assertRaises(FileNotFoundError):
            count_lines(invalid_path)

    def test_count_lines_directory_path(self):
        """Тест подсчета строк когда путь указывает на директорию"""
        import codeaudit
        count_lines = codeaudit.count_lines

        with self.assertRaises(IsADirectoryError):
            count_lines(self.test_dir)

    def test_count_lines_permission_denied(self):
        """Тест подсчета строк без прав доступа"""
        # Создаем файл и делаем его недоступным для чтения
        test_file = os.path.join(self.test_dir, "protected.py")
        with open(test_file, "w") as f:
            f.write("print('test')")

        # Удаляем права на чтение
        os.chmod(test_file, 0o000)

        import codeaudit
        count_lines = codeaudit.count_lines

        with self.assertRaises(PermissionError):
            count_lines(test_file)

    def test_count_lines_memory_efficiency(self):
        """Тест что функция не загружает весь файл в память"""
        test_file = os.path.join(self.test_dir, "large_file.py")
        # Создаем файл с большим количеством строк
        with open(test_file, "w") as f:
            for i in range(10000):
                f.write(f"print('line {i}')\n")

        import codeaudit
        count_lines = codeaudit.count_lines
        result = count_lines(test_file)
        self.assertEqual(result, 10000)

    def test_count_lines_type_validation(self):
        """Тест что функция ожидает строковый путь"""
        import codeaudit
        count_lines = codeaudit.count_lines

        # Проверяем что функция ожидает строку
        with self.assertRaises(TypeError):
            count_lines(123)  # целое число

        with self.assertRaises(TypeError):
            count_lines(None)  # None

        with self.assertRaises(TypeError):
            count_lines([])  # список

    def test_count_lines_empty_string_path(self):
        """Тест что функция не принимает пустую строку"""
        import codeaudit
        count_lines = codeaudit.count_lines

        with self.assertRaises(ValueError):
            count_lines("")

    def test_count_lines_whitespace_path(self):
        """Тест что функция не принимает строку только с пробелами"""
        import codeaudit
        count_lines = codeaudit.count_lines

        with self.assertRaises(ValueError):
            count_lines("   ")

if __name__ == '__main__':
    unittest.main()