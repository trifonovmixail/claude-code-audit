# CodeAudit

`codeaudit` is a CLI tool and Claude Code skill for analyzing the complexity of your codebase and estimating **refactoring pressure**.
It supports **Python, Golang, and JavaScript** projects, and provides a quantitative measure of how "complicated" your code is, highlighting functions, modules, and files that may require refactoring.

Now with **module-level analysis** that considers file size (Lines of Code) in refactoring pressure calculations!

## 🚀 Installation

### Automatic Installation (Recommended)

Install in one line:

```bash
curl -s https://raw.githubusercontent.com/trifonovmixail/claude-code-audit/main/install.sh | /bin/sh
```

Or download and run the script:

```bash
curl -o install.sh https://raw.githubusercontent.com/trifonovmixail/claude-code-audit/main/install.sh
chmod +x install.sh
./install.sh
```

### Manual Installation

Alternatively, you can install manually:

```bash
mkdir -p ~/.claude/skills/
cp -r ./code-audit ~/.claude/skills/code-audit
chmod +x ~/.claude/skills/code-audit/codeaudit.py
```

Once installed, the skill can be invoked by Claude to run automated complexity scans on your projects.

---

## ⚡ How CodeAudit Works

1. **Language Detection**
   CodeAudit scans the project directory and detects source files by their extensions:

   * Python: `.py`
   * Golang: `.go`
   * JavaScript / TypeScript: `.js`, `.ts`

2. **Cyclomatic Complexity Analysis**

   * For **Python**, it uses [radon](https://radon.readthedocs.io/en/latest/) to compute **cyclomatic complexity**, **LCOM**, and other metrics.
   * For **Golang**, it analyzes the AST to compute cyclomatic complexity per function.
   * For **JavaScript/TypeScript**, it uses a **temporary Node.js script with `acorn` and `acorn-walk`** to parse modern JS/TS syntax and compute cyclomatic complexity per function.

3. **Module-Level Analysis**
   CodeAudit includes comprehensive module-level analysis with MRP (Module Refactoring Pressure):

   * **Function Analysis**: Cyclomatic complexity per function
   * **Module Analysis**: File size (LOC), total complexity, average complexity
   * **MRP Calculation**: `0.4*complexity_density + 0.4*max_complexity + 0.2*loc_factor`
   * **Weighted RP**: 70% function RP + 30% module RP for final score

   The following metrics are collected for each language:

| Metric                    | Description                                        |
| ------------------------- | -------------------------------------------------- |
| `functions`               | Total number of functions analyzed                 |
| `p50_complexity`          | 50th percentile cyclomatic complexity (median)     |
| `p90_complexity`          | 90th percentile cyclomatic complexity (upper tail) |
| `max_complexity`          | Maximum cyclomatic complexity in the codebase      |
| `top_complexities`        | Top 20 most complex functions                      |
| `module_rp`               | Module-level refactoring pressure (0-100)          |
| `top_file_complexities`   | Top modules by MRP with LOC and complexity metrics |
| `LCOM` (Python only)      | Lack of Cohesion in Methods, per class/module      |
| `cycles` (Go only)        | Number of cycles in call graph                     |
| `graph_density` (Go only) | Density of function dependency graph               |

---

## 🧮 Refactoring Pressure Formula

The **Refactoring Pressure (RP)** is a normalized score from **0 to 100**, calculated based on the cyclomatic complexity and other structural metrics:

```
RP = w1*P90 + w2*max_complexity + w3*avg_LCOM + w4*cycles + w5*graph_density
```

Where:

* `P90` – 90th percentile complexity
* `max_complexity` – maximum function complexity
* `avg_LCOM` – average Lack of Cohesion in Methods (Python)
* `cycles` – number of cyclic dependencies (Go)
* `graph_density` – call graph density (Go)
* `w1..w5` – configurable weights for each metric

The final RP is **clamped between 0 and 100**.

> The higher the RP, the more your codebase is “stressed” and likely needs refactoring.

---

## 📊 Interpreting Results

After running the scan, the JSON or CLI report contains:

```json
{
  "language": "python",
  "status": "ok",
  "risk_level": "low",
  "rp": 42,
  "function_rp": 35,
  "module_rp": 50,
  "top_function_complexities": [
    {"function": "process_data", "file": "app/data.py", "complexity": 32},
    {"function": "calculate_metrics", "file": "app/metrics.py", "complexity": 28}
  ],
  "top_file_complexities": [
    {
      "file": "app/data.py",
      "loc": 250,
      "total_complexity": 85,
      "avg_complexity": 8.5,
      "function_count": 10,
      "max_complexity": 32,
      "module_rp": 65
    },
    {
      "file": "app/metrics.py",
      "loc": 180,
      "total_complexity": 70,
      "avg_complexity": 7.0,
      "function_count": 9,
      "max_complexity": 28,
      "module_rp": 58
    }
  ],
  "instructions": [
    "Split function 'process_data' in file 'app/data.py' into subfunctions",
    "Review module 'app/data.py' - high refactoring pressure (65)",
    "Consider refactoring high-complexity areas"
  ],
  "summary": "Low to moderate complexity - maintain current standards"
}
```

### Risk Levels

| RP Score | Risk Level | Interpretation                                     |
| -------- | ---------- | -------------------------------------------------- |
| 0–20     | Low        | Code is simple and maintainable                    |
| 21–50    | Medium     | Some functions may need refactoring                |
| 51–75    | High       | Code is complex; refactoring recommended           |
| 76–100   | Critical   | Code is very complex; immediate attention required |

### Status Determination

The `status` field is determined by three factors (any condition triggers the status):

| Status    | Conditions                                                                 |
| --------- |----------------------------------------------------------------------------|
| `ok`      | `RP < 50` AND `max_func_complexity < 30` AND `max_module_complexity < 30`  |
| `warning` | `RP >= 50` OR `max_func_complexity >= 30` OR `max_module_complexity >= 30` |
| `critical`| `RP >= 75` OR `max_func_complexity >= 50` OR `max_module_complexity >= 50` |

Where:
- `RP` — final Refactoring Pressure score (70% function RP + 30% module RP)
- `max_func_complexity` — highest cyclomatic complexity among all functions
- `max_module_complexity` — highest max_complexity among all modules/files

> **Note:** These thresholds are configurable constants in `codeaudit.py`:
> - `CRITICAL_RP_THRESHOLD = 75`
> - `WARNING_RP_THRESHOLD = 50`
> - `CRITICAL_COMPLEXITY_THRESHOLD = 50`
> - `WARNING_COMPLEXITY_THRESHOLD = 30`

### Exit Codes

| Exit Code | Meaning                    | When It Occurs                                    |
| --------- | -------------------------- | ------------------------------------------------- |
| 0         | Success                    | Analysis completed, no thresholds exceeded        |
| 1         | Warning                    | Status is `warning` (without `--threshold`)       |
| 2         | Critical / Threshold       | Status is `critical` OR RP > `--threshold` value  |

#### Exit Code Examples

```bash
# Exit code 2: status is "critical" (max_complexity >= 20)
python codeaudit.py scan ./my_project

# Exit code 0: RP (14) <= threshold (60)
python codeaudit.py scan ./my_project --threshold 60

# Exit code 2: RP (14) > threshold (10)
python codeaudit.py scan ./my_project --threshold 10

# Exit code 1: status is "warning" (no threshold, but max_complexity >= 15)
python codeaudit.py scan ./my_project
```

> **Note:** When `--threshold` is specified, exit code 2 is determined **only** by comparing RP to the threshold value. Built-in status rules are ignored.

### Top Complexities

* `top_function_complexities` shows **the 20 most complex functions** across the codebase, sorted by cyclomatic complexity.
* `top_file_complexities` shows **the top modules by MRP** with Lines of Code and detailed complexity metrics.
* This helps focus refactoring efforts on both problematic functions and modules.

---

## ⚙️ CLI Usage

```bash
# Scan a project directory and output JSON
python codeaudit.py scan ./my_project --format json --threshold 60 -v

# Verbose mode shows detailed metrics for functions and modules
python codeaudit.py scan ./my_project -v
```

---

## 🔧 Dependencies

**Python:**

```text
pip install radon
```

**Golang:**

```text
Go >= 1.16
```

**JavaScript:**

```text
Node.js >=14
npm install -g acorn acorn-walk
```

---

## 📌 Notes

* JS analysis now supports **modern ES6+ and TypeScript syntax** without ESLint or `package.json`.
* Module-level analysis now includes **Lines of Code (LOC)** consideration in MRP calculations.
* Refactoring Pressure is **a relative measure**, intended to help prioritize refactoring, not an absolute indicator of code quality.
* The final RP score is a weighted average: **70% function RP + 30% module RP**.
* Use `-v` flag to see detailed breakdown of function and module complexities.
