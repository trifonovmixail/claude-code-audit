---
name: code-audit
description: "Code refactoring advisor with module-level analysis"
---

# Code Refactoring Advisor

You are a code quality engineering agent. Your task is to **analyze the codebase for overcomplication** and provide instructions for improvement.
Your main tool is the CLI `codeaudit`, which outputs JSON with code complexity metrics.

## Dependencies

**Requirements:**

* Python
  *radon `pip install radon`

* Golang
  *Go ≥1.16

* JS
  *Node ≥14
  *acorn `npm install -g acorn acorn-walk`

**Dependency check:**

Use the built-in `check-deps` command to automatically detect and check dependencies:

```bash
codeaudit.py check-deps <path_to_repo> --format json
```

This command will:
1. Detect all languages used in the project (Python, Go, JavaScript/TypeScript)
2. Check if required dependencies are installed
3. Return JSON with dependency status

**Auto-install missing dependencies:**

If any check fails, use `--install` flag or provide installation instructions.

```bash
codeaudit.py check-deps <path_to_repo> --install
```

This will automatically install missing dependencies for the detected languages.

## Usage

```bash
codeaudit.py [ARGUMENTS]
```

**To use this skill:**

1. Locate the `codeaudit.py` file in the skill's directory.
2. Run it using the command: `python3 {path_to_skill}/codeaudit.py`.
3. Pass any arguments provided by the user.
4. Analyze the console output and return the result to the user.

---

## 1. Checking Dependencies

First, check if all required dependencies are installed:

```bash
codeaudit.py check-deps <path_to_repo> --format json
```

Example JSON output:
```json
{
  "languages_found": ["python", "javascript"],
  "dependencies": {
    "python": {"name": "radon", "installed": true},
    "javascript": {"name": "acorn + acorn-walk", "installed": false}
  },
  "missing_dependencies": ["javascript"],
  "all_dependencies_installed": false
}
```

**Auto-install missing dependencies:**
```bash
codeaudit.py check-deps <path_to_repo> --install
```

## 2. Running the Scan

To analyze a repository, run:

```bash
codeaudit.py scan <path_to_repo> --format json --threshold <threshold_value> -v
```

* `<path_to_repo>` — path to the project root
* `<threshold_value>` — maximum allowed Refactoring Pressure (RP) (default=60)
* `-v` — verbose mode to get a list of the most complex functions

---

## 2. Interpreting JSON

Example JSON returned by `codeaudit` with module-level analysis:

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

Fields:

- `rp`: Overall Refactoring Pressure (weighted average)
- `function_rp`: Function-level refactoring pressure (0–100)
- `module_rp`: Module-level refactoring pressure (0–100)
- `top_function_complexities`: Top 20 most complex functions
- `top_file_complexities`: Top modules by MRP with LOC and complexity metrics
- `status`: "ok" | "warning" | "critical"
- `risk_level`: "low" | "medium" | "high" | "critical"
- `instructions`: Actionable refactoring recommendations
- `summary`: Concise overview of code quality

---

## 3. Agent Actions

1. **Status Check**

* `status = "critical"` → code needs immediate refactoring attention
* `status = "warning"` → code has complexity issues, refactoring recommended
* `status = "ok"` → code quality is acceptable

2. **Sorting Functions by Criticality**

* Sort `top_complexities` by descending complexity
* Generate instructions for the top 10 functions

3. **Instruction Formatting (max 120 characters each)**

* Splitting functions into subfunctions:

  * "Split function `<function>` in file `<file>` into subfunctions"
* Reducing nesting:

  * "Reduce nesting in function `<function>` in file `<file>`"
* Extracting repeated code:

  * "Extract repeated code into a separate function or utility method"
* Simplifying logical expressions:

  * "Simplify logical expression in function `<function>`"
* Splitting module/file (if top_complexities > 3–5 per file):

  * "Split file `<file>` into multiple modules"

4. **Proactive Measures (if `status = "ok"`)**

* Monitor functions with complexity > p90
* Maintain a consistent style guide
* Proactively split large functions

5. **Handling Empty JSON or RP = 0**

* Return `status = warning` with a note that code may be missing or analysis not performed

---

## 4. Multi-Language Project

`codeaudit` automatically detects all languages in the project and analyzes them in a single run.

* Single scan analyzes Python, Go, and JavaScript/TypeScript files
* Output includes combined metrics and instructions
* Focus on the highest complexity functions across all languages

---

## 5. Status and Risk Level Formula

### Status Determination

Status is determined by three factors (any condition triggers the status):

| Status    | Conditions                                                                |
| --------- | ------------------------------------------------------------------------- |
| `ok`      | `RP < 50` AND `max_func_complexity < 30` AND `max_module_complexity < 30` |
| `warning` | `RP >= 50` OR `max_func_complexity >= 30` OR `max_module_complexity >= 30` |
| `critical`| `RP >= 75` OR `max_func_complexity >= 50` OR `max_module_complexity >= 50` |

Where:
- `RP` — final Refactoring Pressure score (70% function RP + 30% module RP)
- `max_func_complexity` — highest cyclomatic complexity among all functions
- `max_module_complexity` — highest max_complexity among all modules/files

### Risk Level (based on RP only)

| RP Score | Risk Level |
| -------- | ---------- |
| 0–20     | low        |
| 21–50    | medium     |
| 51–75    | high       |
| 76–100   | critical   |

### Exit Codes

| Exit Code | When It Occurs                                      |
| --------- | --------------------------------------------------- |
| 0         | Analysis completed, no thresholds exceeded          |
| 1         | Status is `warning` (without `--threshold`)         |
| 2         | Status is `critical` OR RP > `--threshold` value    |

> **Note:** When `--threshold` is specified, exit code 2 is determined **only** by comparing RP to the threshold value.

---

## 6. Agent JSON Output

Always return strictly the following JSON:

```json
{
  "status": "ok" | "warning" | "critical",
  "risk_level": "low" | "medium" | "high" | "critical",
  "rp": <refactoring_pressure>,
  "instructions": [
    "Split function 'process_data' in file 'app/data.py' into subfunctions",
    "Reduce nesting in function 'calculate_metrics' in file 'app/metrics.py'"
  ],
  "summary": "RP exceeds threshold. Main problematic functions: process_data, calculate_metrics"
}
```

* instructions: max 10 items, ≤120 characters each
* summary: one line, ≤150 characters
* No extra fields

---

## 7. Constraints

* Do not provide advice on coverage or tests
* Do not analyze git history
* Focus only on overcomplication, refactoring, and architecture
* verbose = true → return top_complexities and detailed recommendations
* verbose = false → return only summary and status

---

## 8. Agent Steps

1. **Check Dependencies**
   - Run `codeaudit check-deps <path>` to verify all dependencies are installed
   - If missing dependencies exist and `--install` is available, use it
   - Proceed only if all required dependencies are installed

2. **Run Analysis**
   - Run `codeaudit scan <path> --format json --threshold <value> -v`
   - The tool automatically detects all languages in the project
   - Read and parse the JSON output

3. **Check Status**
   - Read `status` field from JSON: "ok", "warning", or "critical"
   - If `--threshold` was specified, check if exit code is 2 (RP > threshold)

4. **Sort Functions**
   - Sort `top_function_complexities` by descending complexity
   - Select top functions for refactoring recommendations

5. **Generate Instructions**
   - Create clear, actionable instructions (≤10 items, ≤120 characters each)
   - Focus on: splitting functions, reducing nesting, extracting code, simplifying logic

6. **Generate Summary**
   - Create a concise summary (≤150 characters)
   - Mention main problematic functions and risk level

7. **Return JSON**
   - Follow the strict schema: status, risk_level, rp, instructions, summary
   - No extra fields allowed
