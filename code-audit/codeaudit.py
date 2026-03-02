#!/usr/bin/env python3

import os
import sys
import json
import argparse
import tempfile
import textwrap
import subprocess
from pathlib import Path

# Constants for weights
FUNCTION_WEIGHT = 0.7
MODULE_WEIGHT = 0.3

# Status thresholds
CRITICAL_RP_THRESHOLD = 75          # RP >= this value triggers critical status
WARNING_RP_THRESHOLD = 50           # RP >= this value triggers warning status
CRITICAL_COMPLEXITY_THRESHOLD = 50  # max_complexity >= this value triggers critical
WARNING_COMPLEXITY_THRESHOLD = 30   # max_complexity >= this value triggers warning

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
            "go/ast"
            "go/parser"
            "go/token"
            "os"
            "path/filepath"
            "strings"
            "sync"
        )

        type FuncComplexity struct {
            Function   string `json:"function"`
            File       string `json:"file"`
            Complexity int    `json:"complexity"`
        }

        type AnalysisJob struct {
            Path string
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

        func analyzeFile(job AnalysisJob, fset *token.FileSet, results *[]FuncComplexity, mu *sync.Mutex) {
            node, err := parser.ParseFile(fset, job.Path, nil, 0)
            if err != nil {
                return
            }

            fileResults := make([]FuncComplexity, 0)
            for _, decl := range node.Decls {
                if fn, ok := decl.(*ast.FuncDecl); ok && fn.Name != nil {
                    fileResults = append(fileResults, FuncComplexity{
                        Function: fn.Name.Name,
                        File: job.Path,
                        Complexity: cyclomatic(fn),
                    })
                }
            }

            mu.Lock()
            *results = append(*results, fileResults...)
            mu.Unlock()
        }

        func main() {
            if len(os.Args) < 2 {
                os.Exit(1)
            }

            root := os.Args[1]

            var goFiles []string
            filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
                if err != nil { return nil }
                if filepath.Ext(path) == ".go" && !strings.HasSuffix(filepath.Base(path), "_test.go") {
                    goFiles = append(goFiles, path)
                }
                return nil
            })

            if len(goFiles) > 500 {
                goFiles = goFiles[:500]
            }

            var results []FuncComplexity
            var wg sync.WaitGroup
            var mu sync.Mutex

            fset := token.NewFileSet()
            jobs := make(chan AnalysisJob, len(goFiles))

            maxWorkers := 10
            for i := 0; i < maxWorkers; i++ {
                wg.Add(1)
                go func() {
                    defer wg.Done()
                    for job := range jobs {
                        analyzeFile(job, fset, &results, &mu)
                    }
                }()
            }

            for _, file := range goFiles {
                jobs <- AnalysisJob{Path: file}
            }
            close(jobs)

            wg.Wait()

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
        # Create a timeout wrapper for subprocess
        def run_with_timeout(cmd, timeout_seconds, cwd=None):
            """Run subprocess with timeout"""
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd
            )
            try:
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
    } catch(err) {
        console.error(`⚠️ Ошибка разбора ${filePath}: ${err.message}`);
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
        } else if (entry.isFile() && (fullPath.endsWith('.js') || fullPath.endsWith('.ts'))) {
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


def analyze_js_with_modules(path: str, timeout: int = 60) -> dict:
    """
    Analyze JavaScript code with module-level metrics.

    Args:
        path (str): Path to the JavaScript project directory to analyze
        timeout (int): Timeout in seconds for JS analysis (default: 60)

    Returns:
        dict: A dictionary containing modules and functions data

    Raises:
        TypeError: If path is not a string
        ValueError: If path is empty, doesn't exist, or is not a directory
        TimeoutError: If JS analysis exceeds timeout
        RuntimeError: If JS analysis fails
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

    # Check if node is available
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("Node.js is not installed or not available in PATH")

    # First check if there are any JS/TS files in the directory
    js_files = list(Path(path).rglob("*.js")) + list(Path(path).rglob("*.ts"))
    if not js_files:
        return {
            "modules": [],
            "functions": [],
            "warning": "No JavaScript or TypeScript files found in the specified path"
        }

    # Get functions data using existing analyze_js function with timeout
    try:
        import signal

        # Set up timeout
        def timeout_handler(signum, frame):
            raise TimeoutError(f"JS analysis timed out after {timeout} seconds")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            functions_data = analyze_js(path)
        finally:
            signal.alarm(0)  # Cancel the alarm
    except TimeoutError:
        raise TimeoutError(f"JS analysis timed out after {timeout} seconds")
    except RuntimeError as e:
        raise RuntimeError(f"JS analysis failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from JS analyzer: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error during JS analysis: {str(e)}")

    # Process functions data to create module metrics
    modules_dict = {}
    line_count_cache = {}

    for func_data in functions_data:
        file_path = func_data["file"]

        if file_path not in modules_dict:
            # Use utility function with caching
            modules_dict[file_path] = _create_module_entry(file_path, line_count_cache)

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

def _create_module_entry(file_path: str, cache: dict = None) -> dict:
    """
    Create a module entry with proper error handling and optional caching.

    Args:
        file_path (str): Path to the file
        cache (dict, optional): Cache dictionary to store line counts

    Returns:
        dict: Module entry dictionary with LOC and error handling
    """
    if cache is None:
        cache = {}

    # Check cache first
    if file_path in cache:
        loc = cache[file_path]
    else:
        # Create new module entry with comprehensive error handling for count_lines
        loc = None

        try:
            loc = count_lines(file_path)
        except FileNotFoundError:
            # File was processed during analysis but no longer exists
            pass
        except PermissionError:
            # No permission to read the file
            pass
        except IsADirectoryError:
            # Path is a directory, not a file
            pass
        except UnicodeDecodeError:
            # File encoding issues
            pass
        except OSError:
            # Other file system errors
            pass
        finally:
            cache[file_path] = loc

    return {
        "file": file_path,
        "loc": loc,
        "total_complexity": 0,
        "function_count": 0,
        "max_complexity": 0
    }


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


def compute_metrics_with_modules(modules_data, functions_data):
    """
    Compute metrics for both function-level and module-level data.

    Args:
        modules_data: List of dictionaries containing module-level metrics
        functions_data: List of dictionaries containing function-level metrics

    Returns:
        dict: Dictionary with computed metrics including function metrics,
               module metrics, and final weighted refactoring pressure

    Raises:
        TypeError: If inputs are not of expected type
        ValueError: If inputs contain invalid values
    """
    # Input validation
    if not isinstance(modules_data, list):
        raise TypeError(f"modules_data must be a list, got {type(modules_data).__name__}")

    if not isinstance(functions_data, list):
        raise TypeError(f"functions_data must be a list, got {type(functions_data).__name__}")

    # Validate modules_data structure
    for i, module in enumerate(modules_data):
        if not isinstance(module, dict):
            raise TypeError(f"Module at index {i} must be a dictionary, got {type(module).__name__}")
        # Check required fields with None handling
        if module.get("file") is None:
            raise ValueError(f"Module at index {i} is missing required field: file")

    # Validate functions_data structure
    for i, func in enumerate(functions_data):
        if not isinstance(func, dict):
            raise TypeError(f"Function at index {i} must be a dictionary, got {type(func).__name__}")
        # Check required fields with None handling
        if func.get("function") is None or func.get("file") is None or func.get("complexity") is None:
            raise ValueError(f"Function at index {i} is missing required fields: function, file, or complexity")

    # Calculate function-level metrics with error handling
    try:
        function_metrics = compute_metrics(functions_data)
    except Exception as e:
        raise RuntimeError(f"Failed to compute function metrics: {str(e)}") from e

    # Calculate module-level metrics
    if not modules_data:
        module_rp = 0
        top_modules = []
    else:
        # Calculate MRP for each module individually
        for module in modules_data:
            try:
                module["module_rp"] = calculate_mrp({
                    "total_complexity": int(module.get("total_complexity", 0)),
                    "max_complexity": int(module.get("max_complexity", 0)),
                    "loc": int(module.get("loc", 0))
                })
            except Exception as e:
                # If calculate_mrp fails for a module, use default value of 0
                module["module_rp"] = 0
                # Log error would go here in production
                # import warnings
                # warnings.warn(f"Failed to calculate module RP for {module.get('file', 'unknown')}: {str(e)}")

        # Calculate overall module RP as average of all module MRP values
        module_rp = sum(m.get("module_rp", 0) for m in modules_data) / len(modules_data) if modules_data else 0

        # Get top 10 modules by their individual MRP values
        top_modules = sorted(
            modules_data,
            key=lambda x: x.get("module_rp", 0),
            reverse=True
        )[:10]

    # Calculate final RP using weighted average with constants
    final_rp = int(FUNCTION_WEIGHT * function_metrics["refactoring_pressure"] + MODULE_WEIGHT * module_rp)

    return {
        "function_metrics": {
            "refactoring_pressure": function_metrics["refactoring_pressure"],
            "max_complexity": function_metrics["max_complexity"],
            "top_complexities": function_metrics["top_complexities"]
        },
        "module_metrics": {
            "module_rp": module_rp,
            "top_modules": top_modules
        },
        "final_rp": final_rp
    }


def generate_summary(metrics, function_metrics, module_metrics, complexity_threshold=10):
    """
    Generate a concise summary of the code quality analysis.

    Args:
        metrics: Overall metrics dictionary
        function_metrics: Function-level metrics
        module_metrics: Module-level metrics

    Returns:
        str: Summary string (max 150 characters)
    """
    if not metrics["function_metrics"]["top_complexities"]:
        return "No complex functions found. Code looks good!"

    max_func_complexity = function_metrics["max_complexity"]
    max_module_complexity = max(m.get("max_complexity", 0) for m in module_metrics["top_modules"])

    if max_func_complexity >= complexity_threshold or max_module_complexity >= complexity_threshold:
        return f"High complexity detected: max function {max_func_complexity}, module {max_module_complexity}"
    elif max_func_complexity >= 6:
        return f"Moderate complexity: consider refactoring {max_func_complexity}-function"
    else:
        return "Low complexity code - well structured"


def generate_instructions(metrics, function_metrics, module_metrics, max_instructions=10):
    """
    Generate refactoring instructions based on function and module metrics.

    Args:
        metrics: Overall metrics dictionary
        function_metrics: Function-level metrics
        module_metrics: Module-level metrics
        max_instructions: Maximum number of instructions to return

    Returns:
        list: List of instruction strings
    """
    instructions = []

    # Function-level instructions
    top_functions = function_metrics["top_complexities"][:5]
    for func in top_functions:
        if func["complexity"] >= 15:
            instructions.append(f"Function '{func['function']}' ({func['complexity']}) - consider breaking down")
        elif func["complexity"] >= 10:
            instructions.append(f"Function '{func['function']}' ({func['complexity']}) - simplify logic")

    # Module-level instructions
    top_modules = module_metrics["top_modules"][:3]
    for module in top_modules:
        if module.get("module_rp", 0) >= 70:
            instructions.append(f"Module {module['file']} - high refactoring pressure ({module.get('module_rp', 0)})")
        elif module.get("avg_complexity", 0) >= 10:
            instructions.append(f"Module {module['file']} - simplify average complexity ({module.get('avg_complexity', 0):.1f})")

    # Instructions for the overall project
    if metrics["final_rp"] >= 75:
        instructions.append("Overall project needs refactoring attention")
    elif metrics["final_rp"] >= 50:
        instructions.append("Consider refactoring high-complexity areas")
    else:
        instructions.append("Good code quality - maintain current standards")

    return instructions[:max_instructions]


def determine_status(metrics, function_metrics, module_metrics):
    """
    Determine overall status based on complexity metrics.

    Args:
        metrics: Overall metrics dictionary
        function_metrics: Function-level metrics
        module_metrics: Module-level metrics

    Returns:
        str: Status ("ok", "warning", "critical")
    """
    max_func = function_metrics["max_complexity"]
    max_module = max(m.get("max_complexity", 0) for m in module_metrics["top_modules"])
    final_rp = metrics["final_rp"]

    if (final_rp >= CRITICAL_RP_THRESHOLD or
        max_func >= CRITICAL_COMPLEXITY_THRESHOLD or
        max_module >= CRITICAL_COMPLEXITY_THRESHOLD):
        return "critical"
    elif (final_rp >= WARNING_RP_THRESHOLD or
          max_func >= WARNING_COMPLEXITY_THRESHOLD or
          max_module >= WARNING_COMPLEXITY_THRESHOLD):
        return "warning"
    else:
        return "ok"


def scan_with_module_analysis(project_path, language):
    """
    Analyze project with module-level analysis and return structured output.

    Args:
        project_path (str): Path to the project directory
        language (str): Programming language ("python", "go", "javascript")

    Returns:
        dict: Complete analysis result with both function and module metrics
    """
    # Get analysis data based on language
    if language == "python":
        analysis_data = analyze_python_with_modules(project_path)
    elif language == "go":
        analysis_data = analyze_go_with_modules(project_path)
    elif language == "javascript":
        analysis_data = analyze_js_with_modules(project_path)
    else:
        raise ValueError(f"Unsupported language: {language}")

    # Compute metrics
    metrics = compute_metrics_with_modules(
        analysis_data["modules"],
        analysis_data["functions"]
    )

    # Generate additional outputs
    summary = generate_summary(
        metrics,
        metrics["function_metrics"],
        metrics["module_metrics"]
    )

    instructions = generate_instructions(
        metrics,
        metrics["function_metrics"],
        metrics["module_metrics"]
    )

    # Determine status
    status = determine_status(
        metrics,
        metrics["function_metrics"],
        metrics["module_metrics"]
    )

    # Get risk level based on final RP
    rl = risk_level(metrics["final_rp"])

    # Prepare top functions and modules
    top_functions = metrics["function_metrics"]["top_complexities"]
    top_modules = []

    for module in metrics["module_metrics"]["top_modules"]:
        module_info = {
            "file": module["file"],
            "loc": module.get("loc", 0),
            "total_complexity": module.get("total_complexity", 0),
            "avg_complexity": module.get("avg_complexity", 0),
            "function_count": module.get("function_count", 0),
            "max_complexity": module.get("max_complexity", 0),
            "module_rp": module.get("module_rp", 0)
        }
        top_modules.append(module_info)

    return {
        "language": language,
        "status": status,
        "risk_level": rl,
        "rp": metrics["final_rp"],
        "function_rp": metrics["function_metrics"]["refactoring_pressure"],
        "module_rp": metrics["module_metrics"]["module_rp"],
        "top_function_complexities": top_functions,
        "top_file_complexities": top_modules,
        "instructions": instructions,
        "summary": summary
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
            # Use module-level analysis if available, fallback to legacy analysis
            try:
                language = detect_language(args.path)
                if not language:
                    raise RuntimeError("Unsupported language")

                output = scan_with_module_analysis(
                    args.path,
                    language
                )

                if args.format == "json":
                    print(json.dumps(output, indent=2))
                else:
                    print("\n=== CODEAUDIT REPORT ===\n")
                    print(json.dumps(output, indent=2))

                # Use --threshold if provided, otherwise use built-in status
                if args.threshold is not None:
                    if output["rp"] > args.threshold:
                        sys.exit(2)
                else:
                    if output["status"] == "critical":
                        sys.exit(2)
                    elif output["status"] == "warning":
                        sys.exit(1)

            except (RuntimeError, ValueError) as e:
                # Fallback to legacy analysis if module analysis fails
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
