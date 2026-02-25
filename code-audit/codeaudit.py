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


def analyze_go(path):
    """
    Go complexity analyzer с top_complexities.
    """
    import tempfile
    import textwrap
    import json
    import subprocess
    import os

    go_code = textwrap.dedent("""
        package main

        import (
            "encoding/json"
            "go/ast"
            "go/parser"
            "go/token"
            "os"
            "path/filepath"
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
            root := os.Args[1]
            var results []FuncComplexity
            fset := token.NewFileSet()

            filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
                if err != nil { return nil }
                if filepath.Ext(path) != ".go" || filepath.Base(path) == "_test.go" {
                    return nil
                }

                node, err := parser.ParseFile(fset, path, nil, 0)
                if err != nil { return nil }

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

    with tempfile.TemporaryDirectory() as tmpdir:
        go_file = os.path.join(tmpdir, "analyzer.go")
        with open(go_file, "w") as f:
            f.write(go_code)

        result = subprocess.run(
            ["go", "run", go_file, path],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return json.loads(result.stdout)


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
    # фильтруем только корректные словари
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

    # RP шкала
    if p90 < 10:
        rp = 10
    elif p90 < 15:
        rp = 30
    elif p90 < 20:
        rp = 50
    elif p90 < 30:
        rp = 75
    else:
        rp = 90

    # Топ 20 сложных функций
    top_complexities = sorted(
        [c for c in complexities if isinstance(c, dict) and "complexity" in c],
        key=lambda x: x["complexity"],  # сортируем строго по числу
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
