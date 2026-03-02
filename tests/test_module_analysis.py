import unittest
import tempfile
import os
import shutil
from unittest.mock import patch, Mock
import json

import codeaudit


class TestModuleAnalysis(unittest.TestCase):

    def setUp(self):
        """Создаем временную директорию для тестов"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Удаляем временную директорию"""
        shutil.rmtree(self.test_dir)

    def test_analyze_python_with_modules_basic(self):
        """Тест анализа Python модулей - базовый функционал"""
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

        # Проверяем структуру результата
        self.assertIn("modules", result)
        self.assertIsInstance(result["modules"], list)
        self.assertIn("functions", result)
        self.assertIsInstance(result["functions"], list)

        # Проверяем данные модулей
        self.assertEqual(len(result["modules"]), 1)
        module = result["modules"][0]
        self.assertEqual(module["file"], test_file)
        self.assertGreater(module["loc"], 0)
        self.assertEqual(module["function_count"], 3)
        self.assertEqual(module["total_complexity"], 4)  # 1 + 2 + 1
        self.assertEqual(module["avg_complexity"], 4/3)  # 4 total / 3 functions
        self.assertEqual(module["max_complexity"], 2)

        # Проверяем данные функций
        self.assertEqual(len(result["functions"]), 3)
        function_names = [f["function"] for f in result["functions"]]
        self.assertIn("simple_function", function_names)
        self.assertIn("complex_function", function_names)
        self.assertIn("another_function", function_names)

    def test_analyze_python_with_modules_multiple_files(self):
        """Тест анализа с несколькими файлами"""
        # Создаем два Python файла
        file1 = os.path.join(self.test_dir, "module1.py")
        file2 = os.path.join(self.test_dir, "module2.py")

        with open(file1, "w") as f:
            f.write("""
def func1():
    pass

def func2():
    if True:
        return
""")

        with open(file2, "w") as f:
            f.write("""
def func3():
    pass
""")

        result = codeaudit.analyze_python_with_modules(self.test_dir)

        # Проверяем, что есть два модуля
        self.assertEqual(len(result["modules"]), 2)

        # Проверяем, что все функции присутствуют
        self.assertEqual(len(result["functions"]), 3)

    def test_analyze_python_with_modules_empty_file(self):
        """Тест анализа пустого Python файла"""
        test_file = os.path.join(self.test_dir, "empty.py")
        with open(test_file, "w") as f:
            f.write("# Empty file\n")

        # Радон может не найти функции в пустом файле
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({test_file: []})

        with patch('subprocess.run', return_value=mock_result):

            result = codeaudit.analyze_python_with_modules(self.test_dir)

            self.assertEqual(len(result["modules"]), 0)
            self.assertEqual(len(result["functions"]), 0)

    def test_analyze_python_with_modules_no_functions(self):
        """Тест анализа файла без функций"""
        test_file = os.path.join(self.test_dir, "no_functions.py")
        with open(test_file, "w") as f:
            f.write("x = 1\ny = 2\n")

        # Радон может не найти функции в файле без функций
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({test_file: []})

        with patch('subprocess.run', return_value=mock_result):

            result = codeaudit.analyze_python_with_modules(self.test_dir)

            self.assertEqual(len(result["modules"]), 0)
            self.assertEqual(len(result["functions"]), 0)

    @patch('subprocess.run')
    def test_analyze_python_with_modules_radon_error(self, mock_run):
        """Тест обработки ошибки radon"""
        mock_run.return_value = Mock(returncode=1, stderr="Radon not installed")

        with self.assertRaises(RuntimeError):
            codeaudit.analyze_python_with_modules(self.test_dir)

    @patch('subprocess.run')
    def test_analyze_python_with_modules_invalid_json(self, mock_run):
        """Тест обработки невалидного JSON от radon"""
        mock_run.return_value = Mock(returncode=0, stdout="invalid json")

        with self.assertRaises(RuntimeError):
            codeaudit.analyze_python_with_modules(self.test_dir)

    @patch('codeaudit.count_lines')
    def test_analyze_python_with_modules_count_lines_error(self, mock_count_lines):
        """Тест ошибки при подсчете строк"""
        test_file = os.path.join(self.test_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("def func(): pass\n")

        mock_count_lines.side_effect = FileNotFoundError("File not found")

        # Create a proper mock result for subprocess.run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({test_file: [{"name": "func", "complexity": 1}]})

        with patch('subprocess.run', return_value=mock_result):
            # Функция должна обработать ошибку и вернуть None для LOC
            result = codeaudit.analyze_python_with_modules(self.test_dir)

            self.assertEqual(len(result["modules"]), 1)
            self.assertIsNone(result["modules"][0]["loc"])

    def test_analyze_python_with_modules_zero_division_protection(self):
        """Тест защиты от деления на ноль"""
        test_file = os.path.join(self.test_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("x = 1\n")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({test_file: []})

        with patch('subprocess.run', return_value=mock_result):

            # Вызываем analyze_python для получения данных
            functions_data = codeaudit.analyze_python(self.test_dir)

            # Проверяем, что нет деления на ноль
            # Эта проверка косвенная, т.к. при отсутствии функций модули не создаются
            self.assertEqual(len(functions_data), 0)

    def test_analyze_python_with_modules_complex_functions(self):
        """Тест анализа сложных функций"""
        test_file = os.path.join(self.test_dir, "complex.py")
        with open(test_file, "w") as f:
            f.write("""
def simple_func():
    pass

def complex_func(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x - y
    else:
        return 0

def nested_func(a, b, c):
    if a:
        for i in range(b):
            if i % 2 == 0:
                print(i)
            else:
                continue
    return c
""")

        result = codeaudit.analyze_python_with_modules(self.test_dir)

        # Находим сложную функцию
        complex_func = next(f for f in result["functions"] if f["function"] == "complex_func")
        self.assertEqual(complex_func["complexity"], 3)  # 1 + 2 вложенных условия

        # Находим вложенную функцию
        nested_func = next(f for f in result["functions"] if f["function"] == "nested_func")
        self.assertEqual(nested_func["complexity"], 4)  # 1 + 3 вложенных условия

    def test_analyze_python_with_modules_edge_cases(self):
        """Тест граничных случаев"""
        # Файл с только комментарием
        test_file = os.path.join(self.test_dir, "comment_only.py")
        with open(test_file, "w") as f:
            f.write("# This is just a comment\n")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({test_file: []})

        with patch('subprocess.run', return_value=mock_result):

            result = codeaudit.analyze_python_with_modules(self.test_dir)

            self.assertEqual(len(result["modules"]), 0)
            self.assertEqual(len(result["functions"]), 0)


if __name__ == '__main__':
    unittest.main()