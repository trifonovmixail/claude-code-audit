#!/usr/bin/env python3

import os
import sys
import json
import argparse
import tempfile
import subprocess
from pathlib import Path


# -----------------------
# LANGUAGE DETECTION
# -----------------------

def detect_languages(path):
    """Обнаруживает все языки в проекте"""
    languages = set()

    for root, _, files in os.walk(path):
        for f in files:
            ext = Path(f).suffix.lower()
            if ext == ".py":
                languages.add("python")
            elif ext == ".go":
                languages.add("go")
            elif ext in (".js", ".ts"):
                languages.add("javascript")

    return list(languages)


def detect_language(path):
    """Обнаруживает основной язык (для обратной совместимости)"""
    languages = detect_languages(path)
    if not languages:
        return None

    # Возвращаем самый распространенный язык
    lang_counts = {}
    for root, _, files in os.walk(path):
        for f in files:
            ext = Path(f).suffix.lower()
            if ext == ".py":
                lang_counts["python"] = lang_counts.get("python", 0) + 1
            elif ext == ".go":
                lang_counts["go"] = lang_counts.get("go", 0) + 1
            elif ext in (".js", ".ts"):
                lang_counts["javascript"] = lang_counts.get("javascript", 0) + 1

    return max(lang_counts, key=lang_counts.get) if lang_counts else None


# -----------------------
# ANALYZERS
# -----------------------

def analyze_python(path):
    result = subprocess.run(
        ["radon", "cc", "-j", path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    data = json.loads(result.stdout)
    complexities = []

    for file_path, objs in data.items():
        for obj in objs:
            complexity = obj.get("complexity", 0)
            if not isinstance(complexity, int):
                continue  # фильтруем неправильные значения
            complexities.append({
                "function": obj.get("name", "<unknown>"),
                "file": file_path,
                "complexity": complexity
            })

    return complexities


def analyze_python_with_modules(path):
    """
    Analyze Python code with module-level metrics.

    Returns:
        dict: A dictionary containing modules and functions data

    Raises:
        RuntimeError: If radon fails to analyze the code
        ValueError: If no valid functions are found
    """
    try:
        # Get function-level analysis using existing function
        functions_data = analyze_python(path)
    except RuntimeError as e:
        raise RuntimeError(f"Radon analysis failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from radon: {str(e)}")

    if not functions_data:
        return {
            "modules": [],
            "functions": []
        }

    # Use dictionary for O(1) module lookups instead of list with O(n) lookups
    modules_dict = {}

    for func_data in functions_data:
        file_path = func_data["file"]

        if file_path not in modules_dict:
            # Create new module entry with error handling for count_lines
            try:
                loc = count_lines(file_path)
            except (FileNotFoundError, PermissionError, OSError) as e:
                # Log error and use None for LOC when file is inaccessible
                loc = None
                # In a real implementation, you might want to log this
                # import warnings
                # warnings.warn(f"Failed to count lines for {file_path}: {str(e)}")

            modules_dict[file_path] = {
                "file": file_path,
                "loc": loc,
                "total_complexity": 0,
                "function_count": 0,
                "max_complexity": 0
            }

        # Update module data
        module = modules_dict[file_path]
        module["function_count"] += 1
        module["total_complexity"] += func_data["complexity"]
        module["max_complexity"] = max(module["max_complexity"], func_data["complexity"])

    # Calculate average complexity for each module with zero division protection
    modules_data = []
    for file_path, module in modules_dict.items():
        if module["function_count"] > 0:
            module["avg_complexity"] = module["total_complexity"] / module["function_count"]
        else:
            module["avg_complexity"] = 0

        modules_data.append(module)

    return {
        "modules": modules_data,
        "functions": functions_data
    }


def analyze_go(path: str, timeout: int = 60) -> list:
    """
    Go complexity analyzer с top_complexities.

    Args:
        path (str): Path to the Go project directory to analyze
        timeout (int): Timeout in seconds for Go analysis (default: 60)

    Returns:
        list: List of dictionaries containing function complexity data

    Raises:
        TypeError: If path is not a string
        ValueError: If path is empty or doesn't exist
        TimeoutError: If Go analysis exceeds timeout
        RuntimeError: If Go analysis fails
    """
    import tempfile
    import textwrap
    import json
    import subprocess
    import os

    # Input validation
    if not isinstance(path, str):
        raise TypeError(f"path must be a string, got {type(path).__name__}")

    if not path.strip():
        raise ValueError("path cannot be empty or whitespace")

    if not os.path.exists(path):
        raise ValueError(f"Path does not exist: {path}")

    if not os.path.isdir(path):
        raise ValueError(f"Path is not a directory: {path}")

    # Check if Go is available
    try:
        subprocess.run(["go", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("Go is not installed or not available in PATH")

    go_code = textwrap.dedent("""
        package main

        import (
            "encoding/json"
            "fmt"
            "go/ast"
            "go/parser"
            "go/token"
            "os"
            "path/filepath"
            "time"
        )

        type FuncComplexity struct {
            Function   string `json:"function"`
            File       string `json:"file"`
            Complexity int    `json:"complexity"`
        }

        func cyclomatic(fn *ast.FuncDecl) int {
            c := 1
            ast.Inspect(fn, func(n ast.Node) bool {
                switch n.(type) {
                case *ast.IfStmt, *ast.ForStmt, *ast.RangeStmt, *ast.CaseClause,
                     *ast.SwitchStmt, *ast.TypeSwitchStmt, *ast.CommClause:
                    c++
                }
                return true
            })
            return c
        }

        func main() {
            if len(os.Args) < 2 {
                fmt.Println("Usage: analyzer <path>")
                os.Exit(1)
            }

            start := time.Now()
            root := os.Args[1]
            var results []FuncComplexity
            fset := token.NewFileSet()

            filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
                if err != nil { return nil }
                if filepath.Ext(path) != ".go" || filepath.Base(path) == "_test.go" {
                    return nil
                }

                // Check if we've exceeded timeout (approximately)
                if time.Since(start).Seconds() > 50 { // Leave some buffer
                    return fmt.Errorf("analysis timeout")
                }

                node, err := parser.ParseFile(fset, path, nil, 0)
                if err != nil {
                    // Parse errors shouldn't stop the analysis
                    return nil
                }

                for _, decl := range node.Decls {
                    if fn, ok := decl.(*ast.FuncDecl); ok {
                        results = append(results, FuncComplexity{
                            Function: fn.Name.Name,
                            File: path,
                            Complexity: cyclomatic(fn),
                        })
                    }
                }
                return nil
            })

            json.NewEncoder(os.Stdout).Encode(results)
        }
    """)

    # Run with timeout
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            go_file = os.path.join(tmpdir, "analyzer.go")
            with open(go_file, "w") as f:
                f.write(go_code)

            process = subprocess.Popen(
                ["go", "run", go_file, path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                raise TimeoutError(f"Go analysis timed out after {timeout} seconds")

            if process.returncode != 0:
                raise RuntimeError(f"Go analysis failed: {stderr}")

            return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from Go analyzer: {e}")


def analyze_go_with_modules(path: str, timeout: int = 60) -> dict:
    """
    Analyze Go code with module-level metrics.

    Args:
        path (str): Path to the Go project directory to analyze
        timeout (int): Timeout in seconds for Go analysis (default: 60)

    Returns:
        dict: A dictionary containing modules and functions data

    Raises:
        TypeError: If path is not a string
        ValueError: If path is empty, doesn't exist, or is not a directory
        TimeoutError: If Go analysis exceeds timeout
        RuntimeError: If Go analysis fails for other reasons
    """
    # Input validation
    if not isinstance(path, str):
        raise TypeError(f"path must be a string, got {type(path).__name__}")

    if not path.strip():
        raise ValueError("path cannot be empty or whitespace")

    if not os.path.exists(path):
        raise ValueError(f"Path does not exist: {path}")

    if not os.path.isdir(path):
        raise ValueError(f"Path is not a directory: {path}")

    try:
        # Get function-level analysis using existing function with timeout
        import signal
        import tempfile
        import subprocess
        from pathlib import Path

        # Create a timeout wrapper for subprocess
        def run_with_timeout(cmd, timeout_seconds, cwd=None):
            """Run subprocess with timeout"""
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=cwd
                )
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                return process.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                process.kill()
                raise TimeoutError(f"Go analysis timed out after {timeout_seconds} seconds")

        # First check if there are any Go files in the directory
        go_files = list(Path(path).rglob("*.go"))
        if not go_files:
            return {
                "modules": [],
                "functions": [],
                "warning": "No Go files found in the specified path"
            }

        try:
            # Get function-level analysis using existing function
            functions_data = analyze_go(path)
        except TimeoutError:
            raise TimeoutError(f"Go analysis timed out after {timeout} seconds")
        except RuntimeError as e:
            raise RuntimeError(f"Go analysis failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from Go analyzer: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during Go analysis: {str(e)}")

    except TimeoutError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error running Go analysis: {str(e)}")

    if not functions_data:
        return {
            "modules": [],
            "functions": [],
            "warning": "No valid functions found in Go files"
        }

    # Validate functions data structure
    for func_data in functions_data:
        if not isinstance(func_data, dict):
            raise ValueError(f"Invalid function data structure: {type(func_data)}")
        if "file" not in func_data or "complexity" not in func_data:
            raise ValueError("Function data missing required fields (file, complexity)")

    # Use dictionary for O(1) module lookups instead of list with O(n) lookups
    modules_dict = {}

    for func_data in functions_data:
        file_path = func_data["file"]

        if file_path not in modules_dict:
            # Create new module entry with comprehensive error handling for count_lines
            try:
                loc = count_lines(file_path)
            except FileNotFoundError:
                # File was processed during Go analysis but no longer exists
                loc = None
            except PermissionError:
                # No permission to read the file
                loc = None
            except IsADirectoryError:
                # Path is a directory, not a file
                loc = None
            except UnicodeDecodeError:
                # File encoding issues
                loc = None
            except OSError as e:
                # Other file system errors
                loc = None

            modules_dict[file_path] = {
                "file": file_path,
                "loc": loc,
                "total_complexity": 0,
                "function_count": 0,
                "max_complexity": 0
            }

        # Update module data
        module = modules_dict[file_path]
        module["function_count"] += 1
        module["total_complexity"] += func_data["complexity"]
        module["max_complexity"] = max(module["max_complexity"], func_data["complexity"])

    # Calculate average complexity for each module with zero division protection
    modules_data = []
    for file_path, module in modules_dict.items():
        if module["function_count"] > 0:
            module["avg_complexity"] = module["total_complexity"] / module["function_count"]
        else:
            module["avg_complexity"] = 0

        # Add file existence status
        module["file_exists"] = os.path.exists(file_path)

        modules_data.append(module)

    return {
        "modules": modules_data,
        "functions": functions_data
    }


def analyze_js(path):
    """
    Универсальный JS-анализатор для modern JS/TS.
    Создает временный Node.js скрипт с acorn для подсчета цикломатической сложности.
    """
    js_code = r"""
const fs = require('fs');
const path = require('path');
const acorn = require('acorn');
const walk = require('acorn-walk');

function cyclomatic(node) {
    let c = 1;
    walk.simple(node, {
        IfStatement() { c++; },
        ForStatement() { c++; },
        WhileStatement() { c++; },
        ForOfStatement() { c++; },
        ForInStatement() { c++; },
        ConditionalExpression() { c++; },
        LogicalExpression(n) { if (n.operator === '&&' || n.operator === '||') c++; },
        SwitchCase(n) { if (n.test) c++; },
        CatchClause() { c++; }
    });
    return c;
}

function analyzeFile(filePath) {
    const code = fs.readFileSync(filePath, 'utf-8');
    let results = [];
    let ast;
    try {
        ast = acorn.parse(code, { ecmaVersion: 2026, sourceType: "module" });
    } catch(e) {
        console.error(`⚠️ Ошибка разбора ${filePath}: ${e.message}`);
        return results;
    }

    walk.simple(ast, {
        FunctionDeclaration(node) {
            results.push({
                function: node.id ? node.id.name : "<anonymous>",
                file: filePath,
                complexity: cyclomatic(node)
            });
        },
        FunctionExpression(node) {
            results.push({
                function: "<anonymous>",
                file: filePath,
                complexity: cyclomatic(node)
            });
        },
        ArrowFunctionExpression(node) {
            results.push({
                function: "<arrow>",
                file: filePath,
                complexity: cyclomatic(node)
            });
        }
    });

    return results;
}

function walkDir(dir) {
    let all = [];
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (let entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            all = all.concat(walkDir(fullPath));
        } else if (entry.isFile() && fullPath.endsWith('.js')) {
            all = all.concat(analyzeFile(fullPath));
        }
    }
    return all;
}

const targetDir = process.argv[2];
if (!targetDir) {
    console.error("Usage: node js_complexity.js <path>");
    process.exit(1);
}

const output = walkDir(targetDir);
console.log(JSON.stringify(output));
"""
    # получаем глобальный путь npm
    npm_global_root = subprocess.check_output(["npm", "root", "-g"], text=True).strip()

    env = os.environ.copy()
    # добавляем глобальный npm путь в NODE_PATH
    env["NODE_PATH"] = npm_global_root

    with tempfile.TemporaryDirectory() as tmpdir:
        js_file = os.path.join(tmpdir, "js_complexity.js")
        with open(js_file, "w", encoding="utf-8") as f:
            f.write(js_code)

        try:
            result = subprocess.run(
                ["node", js_file, path],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ JS-анализ не удался: {e.stderr}")
            return []


def analyze_js_with_modules(path: str) -> dict:
    """
    Analyze JavaScript code with module-level metrics.

    Args:
        path (str): Path to the JavaScript project directory to analyze

    Returns:
        dict: A dictionary containing modules and functions data

    Raises:
        TypeError: If path is not a string
        ValueError: If path is empty, doesn't exist, or is not a directory
    """
    import tempfile
    import json
    import subprocess
    import os

    # Input validation
    if not isinstance(path, str):
        raise TypeError(f"path must be a string, got {type(path).__name__}")

    if not path.strip():
        raise ValueError("path cannot be empty or whitespace")

    if not os.path.exists(path):
        raise ValueError(f"Path does not exist: {path}")

    if not os.path.isdir(path):
        raise ValueError(f"Path is not a directory: {path}")

    # Get functions data using existing analyze_js function
    functions_data = analyze_js(path)

    # Process functions data to create module metrics
    modules_dict = {}

    for func_data in functions_data:
        file_path = func_data["file"]

        if file_path not in modules_dict:
            # Create new module entry with comprehensive error handling for count_lines
            try:
                loc = count_lines(file_path)
            except FileNotFoundError:
                # File was processed during JS analysis but no longer exists
                loc = None
            except PermissionError:
                # No permission to read the file
                loc = None
            except IsADirectoryError:
                # Path is a directory, not a file
                loc = None
            except UnicodeDecodeError:
                # File encoding issues
                loc = None
            except OSError as e:
                # Other file system errors
                loc = None

            modules_dict[file_path] = {
                "file": file_path,
                "loc": loc,
                "total_complexity": 0,
                "function_count": 0,
                "max_complexity": 0
            }

        # Update module data
        module = modules_dict[file_path]
        module["function_count"] += 1
        module["total_complexity"] += func_data["complexity"]
        module["max_complexity"] = max(module["max_complexity"], func_data["complexity"])

    # Calculate average complexity for each module with zero division protection
    modules_data = []
    for file_path, module in modules_dict.items():
        if module["function_count"] > 0:
            module["avg_complexity"] = module["total_complexity"] / module["function_count"]
        else:
            module["avg_complexity"] = 0

        # Add file existence status
        module["file_exists"] = os.path.exists(file_path)

        modules_data.append(module)

    return {
        "modules": modules_data,
        "functions": functions_data
    }


def calculate_mrp(module_data: dict) -> int:
    """
    Calculate Module Refactoring Pressure (MRP)

    MRP is a metric that combines three factors to determine how much refactoring
    pressure a module is under:
    1. Complexity Density (40%): (total_complexity / loc) * 100
    2. Max Complexity (40%): highest complexity in the module
    3. LOC Factor (20%): bonus based on lines of code size

    Args:
        module_data (dict): Dictionary containing module metrics with keys:
            - total_complexity (int): Sum of all function complexities in module
            - max_complexity (int): Highest complexity in module
            - loc (int): Lines of code in module

    Returns:
        int: MRP score clamped between 0 and 100

    Raises:
        TypeError: If module_data is not a dictionary
        ValueError: If module_data contains invalid values
    """
    # Input validation
    if not isinstance(module_data, dict):
        raise TypeError(f"module_data must be a dictionary, got {type(module_data).__name__}")

    # Get values with error handling
    def safe_get_value(key: str, default: int = 0) -> int:
        """Safely get value from dictionary with validation"""
        value = module_data.get(key, default)

        # Handle None values
        if value is None:
            return default

        # Validate type
        if not isinstance(value, (int, float)):
            raise TypeError(f"Value for '{key}' must be a number, got {type(value).__name__}")

        # Convert to int if float
        value = int(value)

        # Handle negative values by clamping to 0
        return max(0, value)

    # Extract and validate inputs
    total_complexity = safe_get_value("total_complexity")
    max_complexity = safe_get_value("max_complexity")
    loc = safe_get_value("loc")

    # Calculate complexity density with zero division protection
    if loc > 0:
        complexity_density = (total_complexity / loc) * 100
    else:
        complexity_density = 0

    # Calculate LOC factor with documented thresholds
    loc_factor = 0
    if 1000 <= loc < 2000:
        loc_factor = 5
    elif 2000 <= loc < 5000:
        loc_factor = 10
    elif loc >= 5000:
        loc_factor = 15

    # MRP formula with documented weights
    # Weight explanations:
    # - 40% complexity_density: Measures how complex code is relative to its size
    # - 40% max_complexity: Identifies functions that need immediate attention
    # - 20% loc_factor: Rewards well-structured large modules
    mrp = 0.4 * complexity_density + 0.4 * max_complexity + 0.2 * loc_factor

    # Convert to int after calculation
    mrp = int(mrp)

    # Clamp between 0 and 100 to ensure valid percentage
    return max(0, min(100, mrp))




# -----------------------
# UTILS
# -----------------------

def count_lines(file_path: str) -> int:
    """
    Count lines of code in a file.

    This function is memory efficient and doesn't load the entire file into memory.
    It raises exceptions for invalid inputs and file access errors.

    Args:
        file_path (str): Path to the file to count lines in

    Returns:
        int: Number of lines in the file

    Raises:
        TypeError: If file_path is not a string
        FileNotFoundError: If the file doesn't exist
        IsADirectoryError: If the path points to a directory
        PermissionError: If the file cannot be read due to permissions
        OSError: For other file-related errors

    Examples:
        >>> count_lines("example.py")
        42
    """
    # Input validation
    if not isinstance(file_path, str):
        raise TypeError(f"file_path must be a string, got {type(file_path).__name__}")

    if not file_path.strip():
        raise ValueError("file_path cannot be empty or whitespace")

    # Check if file exists and is accessible
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if os.path.isdir(file_path):
        raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")

    # Count lines efficiently without loading entire file into memory
    try:
        line_count = 0
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line_count += 1
        return line_count
    except PermissionError:
        raise PermissionError(f"Permission denied when reading file: {file_path}")
    except UnicodeDecodeError:
        raise ValueError(f"File is not valid UTF-8 encoded: {file_path}")
    except OSError as e:
        raise OSError(f"Error reading file {file_path}: {e}")


# -----------------------
# METRICS
# -----------------------

def percentile(data, p):
    if not data:
        return 0
    data = sorted(data)
    index = int(len(data) * p)
    index = min(index, len(data) - 1)
    return data[index]


def compute_metrics(complexities):
    """
    Compute metrics from function complexity data.

    Args:
        complexities: List of dictionaries containing function complexity data

    Returns:
        dict: Dictionary with computed metrics including refactoring pressure
    """
    # Filter only valid dictionaries
    clean_complexities = [
        c for c in complexities
        if isinstance(c, dict) and "complexity" in c and isinstance(c["complexity"], int)
    ]

    if not clean_complexities:
        return {
            "functions": 0,
            "p50_complexity": 0,
            "p90_complexity": 0,
            "max_complexity": 0,
            "refactoring_pressure": 0,
            "top_complexities": []
        }

    complexity_values = [c["complexity"] for c in clean_complexities]

    p50 = percentile(complexity_values, 0.5)
    p90 = percentile(complexity_values, 0.9)
    max_c = max(complexity_values)

    # Use calculate_mrp for module-level refactoring pressure calculation
    # This provides a more accurate measure of refactoring pressure
    module_data = {
        "total_complexity": sum(complexity_values),
        "max_complexity": max_c,
        "loc": len(clean_complexities) * 50  # Estimate LOC based on function count
    }
    rp = calculate_mrp(module_data)

    # Top 20 most complex functions
    top_complexities = sorted(
        [c for c in complexities if isinstance(c, dict) and "complexity" in c],
        key=lambda x: x["complexity"],  # sort strictly by number
        reverse=True
    )[:20]

    return {
        "functions": len(clean_complexities),
        "p50_complexity": p50,
        "p90_complexity": p90,
        "max_complexity": max_c,
        "refactoring_pressure": rp,
        "top_complexities": top_complexities
    }


def risk_level(rp):
    if rp < 20:
        return "low"
    if rp < 50:
        return "medium"
    if rp < 75:
        return "high"
    return "critical"


# -----------------------
# DEPENDENCY MANAGEMENT
# -----------------------

def check_python_deps():
    """Проверяет наличие radon"""
    try:
        result = subprocess.run(["radon", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False


def check_js_deps():
    """Проверяет наличие acorn и acorn-walk"""
    try:
        # Проверяем через npm list
        result = subprocess.run(
            ["npm", "list", "-g", "acorn", "acorn-walk"],
            capture_output=True,
            text=True
        )
        return "acorn" in result.stdout and "acorn-walk" in result.stdout
    except:
        return False


def check_go_deps():
    """Проверяет Go (встроенный, всегда доступен)"""
    try:
        result = subprocess.run(["go", "version"], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False


def check_dependencies(languages):
    """Проверяет все зависимости для указанных языков"""
    deps_status = {
        "python": {"name": "radon", "installed": check_python_deps()},
        "go": {"name": "Go (built-in)", "installed": check_go_deps()},
        "javascript": {"name": "acorn + acorn-walk", "installed": check_js_deps()}
    }

    missing_deps = []
    for lang in languages:
        if lang in deps_status:
            if not deps_status[lang]["installed"]:
                missing_deps.append(lang)

    return deps_status, missing_deps


def print_dependency_status(deps_status, missing_deps, languages_found):
    """Красиво выводит статус зависимостей"""
    print("\n🔍 CODEAUDIT - DEPENDENCY CHECK")
    print("=" * 50)
    print(f"📁 Found languages: {', '.join(languages_found) or 'None'}")
    print()

    print("📦 DEPENDENCY STATUS:")
    print("-" * 30)

    for lang, info in deps_status.items():
        if lang in languages_found:
            status_icon = "✅" if info["installed"] else "❌"
            print(f"{status_icon} {lang.title()}: {info['name']}")
            if not info["installed"]:
                print(f"   → Need to install")
        else:
            status_icon = "⏭️ "
            print(f"{status_icon} {lang.title()}: {info['name']} (not needed)")

    print()

    if missing_deps:
        print("🚨 MISSING DEPENDENCIES:")
        print("-" * 25)
        for lang in missing_deps:
            if lang == "python":
                print(f"• Install radon: pip install radon")
            elif lang == "javascript":
                print(f"• Install acorn packages: npm install -g acorn acorn-walk")
            elif lang == "go":
                print(f"• Install Go from: https://golang.org/dl/")
    else:
        print("✅ All dependencies are installed!")


def install_python_deps():
    """Устанавливает Python зависимости"""
    print("📦 Installing Python dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "radon"], check=True)
        print("✅ radon installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install radon: {e}")
        return False


def install_js_deps():
    """Устанавливает JavaScript зависимости"""
    print("📦 Installing JavaScript dependencies...")
    try:
        subprocess.run(["npm", "install", "-g", "acorn", "acorn-walk"], check=True)
        print("✅ acorn + acorn-walk installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install JS deps: {e}")
        return False


# -----------------------
# CLI
# -----------------------

def main():
    parser = argparse.ArgumentParser(prog="codeaudit")
    parser.add_argument("command", choices=["scan", "check-deps"])
    parser.add_argument("path")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--threshold", type=int, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--install", action="store_true",
                        help="Automatically install missing dependencies")

    args = parser.parse_args()

    try:
        if args.command == "scan":
            language = detect_language(args.path)
            if not language:
                raise RuntimeError("Unsupported language")

            if language == "python":
                complexities = analyze_python(args.path)
            elif language == "go":
                complexities = analyze_go(args.path)
            elif language == "js":
                complexities = analyze_js(args.path)
            else:
                complexities = []

            metrics = compute_metrics(complexities)
            rp = metrics["refactoring_pressure"]

            output = {
                "language": language,
                "summary": metrics,
                "risk_level": risk_level(rp),
                "threshold_exceeded": (
                    args.threshold is not None and rp > args.threshold
                )
            }

            if args.verbose:
                output["top_complexities"] = sorted(
                    complexities,
                    key=lambda x: x["complexity"],
                    reverse=True
                )[:20]

            if args.format == "json":
                print(json.dumps(output, indent=2))
            else:
                print("\n=== CODEAUDIT REPORT ===\n")
                print(json.dumps(output, indent=2))

            if args.threshold is not None and rp > args.threshold:
                sys.exit(2)

        elif args.command == "check-deps":
            languages_found = detect_languages(args.path)

            if not languages_found:
                output = {
                    "error": "No supported languages found in the project",
                    "languages_found": [],
                    "dependencies": {},
                    "missing_dependencies": []
                }
                if args.format == "json":
                    print(json.dumps(output, indent=2))
                else:
                    print("⚠️ No supported languages found in the project")
                sys.exit(1)

            deps_status, missing_deps = check_dependencies(languages_found)

            if args.format == "json":
                output = {
                    "languages_found": languages_found,
                    "dependencies": {
                        lang: {
                            "name": info["name"],
                            "installed": info["installed"]
                        } for lang, info in deps_status.items()
                    },
                    "missing_dependencies": missing_deps,
                    "all_dependencies_installed": len(missing_deps) == 0
                }
                print(json.dumps(output, indent=2))
            else:
                print_dependency_status(deps_status, missing_deps, languages_found)

            if args.install and missing_deps:
                print("\n🔧 AUTO-INSTALLING MISSING DEPENDENCIES:")
                print("-" * 45)
                success = True

                for lang in missing_deps:
                    if lang == "python":
                        if not install_python_deps():
                            success = False
                    elif lang == "javascript":
                        if not install_js_deps():
                            success = False

                if success:
                    print("\n✅ All dependencies installed successfully!")
                else:
                    print("\n❌ Some dependencies failed to install")
                    sys.exit(1)
            elif missing_deps:
                sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
