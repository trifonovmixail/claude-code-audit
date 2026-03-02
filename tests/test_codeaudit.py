#!/usr/bin/env python3
import unittest
import tempfile
import os
import json
import subprocess
import sys
import shutil

import codeaudit


class TestCodeAudit(unittest.TestCase):

    def setUp(self):
        """Создаем временную директорию для тестов"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Удаляем временную директорию"""
        shutil.rmtree(self.test_dir)

    def test_detect_languages_python(self):
        """Тест обнаружения Python файлов"""
        python_file = os.path.join(self.test_dir, "test.py")
        with open(python_file, "w") as f:
            f.write("def test(): pass")

        languages = codeaudit.detect_languages(self.test_dir)
        self.assertIn("python", languages)
        self.assertEqual(len(languages), 1)

    def test_detect_languages_go(self):
        """Тест обнаружения Go файлов"""
        go_file = os.path.join(self.test_dir, "test.go")
        with open(go_file, "w") as f:
            f.write("package main\n\nfunc main() {}")

        languages = codeaudit.detect_languages(self.test_dir)
        self.assertIn("go", languages)
        self.assertEqual(len(languages), 1)

    def test_detect_languages_javascript(self):
        """Тест обнаружения JavaScript файлов"""
        js_file = os.path.join(self.test_dir, "test.js")
        with open(js_file, "w") as f:
            f.write("function test() {}")

        languages = codeaudit.detect_languages(self.test_dir)
        self.assertIn("javascript", languages)
        self.assertEqual(len(languages), 1)

    def test_detect_languages_multiple(self):
        """Тест обнаружения нескольких языков"""
        py_file = os.path.join(self.test_dir, "app.py")
        go_file = os.path.join(self.test_dir, "main.go")
        js_file = os.path.join(self.test_dir, "utils.js")

        with open(py_file, "w") as f: f.write("def main(): pass")
        with open(go_file, "w") as f: f.write("package main\n\nfunc main() {}")
        with open(js_file, "w") as f: f.write("function hello() {}")

        languages = codeaudit.detect_languages(self.test_dir)
        self.assertIn("python", languages)
        self.assertIn("go", languages)
        self.assertIn("javascript", languages)
        self.assertEqual(len(languages), 3)

    def test_detect_languages_empty(self):
        """Тест пустой директории"""
        languages = codeaudit.detect_languages(self.test_dir)
        self.assertEqual(len(languages), 0)

    def test_detect_language_priority(self):
        """Тест определения основного языка (наиболее распространенного)"""
        # Создаем больше Python файлов
        for i in range(3):
            with open(os.path.join(self.test_dir, f"app{i}.py"), "w") as f:
                f.write("def test(): pass")

        # Один Go файл
        with open(os.path.join(self.test_dir, "main.go"), "w") as f:
            f.write("package main\n\nfunc main() {}")

        primary_lang = codeaudit.detect_language(self.test_dir)
        self.assertEqual(primary_lang, "python")

    def test_check_dependencies_all_installed(self):
        """Тест проверки зависимостей когда все установлены"""
        # Создаем тестовые файлы
        with open(os.path.join(self.test_dir, "test.py"), "w") as f:
            f.write("def test(): pass")

        languages = codeaudit.detect_languages(self.test_dir)
        deps_status, missing_deps = codeaudit.check_dependencies(languages)

        # Go должен быть доступен (встроенный)
        self.assertTrue(deps_status["go"]["installed"])

        # Python radon должен быть установлен (проверяем через вызов)
        self.assertTrue(deps_status["python"]["installed"])

        # Отсутствие зависимостей
        self.assertEqual(len(missing_deps), 0)

    def test_percentile_calculation(self):
        """Тест расчета перцентилей"""
        test_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # P50 (медиана) - возвращает элемент по индексу 5 (значение 6)
        p50 = codeaudit.percentile(test_data, 0.5)
        self.assertEqual(p50, 6)

        # P90 - индекс 9 (значение 10)
        p90 = codeaudit.percentile(test_data, 0.9)
        self.assertEqual(p90, 10)

        # P0 (минимум) - индекс 0 (значение 1)
        p0 = codeaudit.percentile(test_data, 0)
        self.assertEqual(p0, 1)

        # Пустые данные
        empty_p50 = codeaudit.percentile([], 0.5)
        self.assertEqual(empty_p50, 0)

    def test_risk_level_calculation(self):
        """Тест расчета уровня риска"""
        self.assertEqual(codeaudit.risk_level(10), "low")
        self.assertEqual(codeaudit.risk_level(20), "medium")  # 20 >= 20
        self.assertEqual(codeaudit.risk_level(30), "medium")
        self.assertEqual(codeaudit.risk_level(49), "medium")
        self.assertEqual(codeaudit.risk_level(50), "high")  # 50 >= 50
        self.assertEqual(codeaudit.risk_level(70), "high")
        self.assertEqual(codeaudit.risk_level(74), "high")
        self.assertEqual(codeaudit.risk_level(75), "critical")  # 75 >= 75
        self.assertEqual(codeaudit.risk_level(80), "critical")
        self.assertEqual(codeaudit.risk_level(100), "critical")

class TestCodeAuditCLI(unittest.TestCase):
    """Интеграционные тесты CLI"""

    def setUp(self):
        """Создаем временную директорию для тестов"""
        self.test_dir = tempfile.mkdtemp()
        # Ищем скрипт codeaudit.py в code-audit директории
        script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code-audit'))
        self.script_path = os.path.join(script_dir, 'codeaudit.py')

        # Создаем копию скрипта для тестов чтобы избежать проблем с путями
        self.test_script_path = os.path.join(self.test_dir, 'codeaudit.py')
        with open(self.script_path, 'r') as src:
            with open(self.test_script_path, 'w') as dst:
                dst.write(src.read())

    def tearDown(self):
        """Удаляем временную директорию"""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_cli_check_deps_text_format(self):
        """Тест CLI check-deps в текстовом формате"""
        # Создаем тестовый Python файл
        with open(os.path.join(self.test_dir, "test.py"), "w") as f:
            f.write("def test(): pass")

        # Запускаем команду
        result = subprocess.run([
            sys.executable, self.test_script_path,
            "check-deps", self.test_dir
        ], capture_output=True, text=True)

        # Проверяем что команда завершилась успешно
        self.assertEqual(result.returncode, 0)
        self.assertIn("Found languages:", result.stdout)
        self.assertIn("DEPENDENCY STATUS:", result.stdout)

    def test_cli_check_deps_json_format(self):
        """Тест CLI check-deps в JSON формате"""
        # Создаем тестовый Python файл
        with open(os.path.join(self.test_dir, "test.py"), "w") as f:
            f.write("def test(): pass")

        # Запускаем команду
        result = subprocess.run([
            sys.executable, self.test_script_path,
            "check-deps", self.test_dir,
            "--format", "json"
        ], capture_output=True, text=True)

        # Проверяем что команда завершилась успешно
        self.assertEqual(result.returncode, 0)

        # Проверяем JSON вывод
        output = json.loads(result.stdout)
        self.assertIn("languages_found", output)
        self.assertIn("dependencies", output)
        self.assertIn("missing_dependencies", output)
        self.assertIn("all_dependencies_installed", output)

    def test_cli_scan_simple(self):
        """Тест CLI scan на простом Python коде"""
        # Создаем отдельную директорию для тестовых файлов
        # (чтобы не анализировать скопированный codeaudit.py)
        test_files_dir = os.path.join(self.test_dir, "test_files")
        os.makedirs(test_files_dir)

        with open(os.path.join(test_files_dir, "simple.py"), "w") as f:
            f.write("def hello():\n    print('Hello')\n")

        # Запускаем команду
        result = subprocess.run([
            sys.executable, self.test_script_path,
            "scan", test_files_dir,
            "--format", "json"
        ], capture_output=True, text=True)

        # Проверяем что команда завершилась успешно
        self.assertEqual(result.returncode, 0)

        # Проверяем что вывод валидный JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            # Если JSON не валидный, выводим что было
            print(f"STDERR: {result.stderr}")
            print(f"STDOUT: {result.stdout}")
            raise

        # Проверяем наличие ожидаемых полей в выводе
        self.assertIn("language", output)
        self.assertIn("status", output)
        self.assertIn("rp", output)
        self.assertIn("risk_level", output)
        self.assertEqual(output["language"], "python")


if __name__ == '__main__':
    unittest.main()