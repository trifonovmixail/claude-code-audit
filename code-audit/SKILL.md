---
name: code-audit
description: "Code refactoring advisor"
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

Example JSON returned by `codeaudit`:

```json
{
  "language": "python",
  "summary": {
    "functions": 128,
    "p50_complexity": 4,
    "p90_complexity": 14,
    "max_complexity": 32,
    "refactoring_pressure": 62
  },
  "risk_level": "high",
  "threshold_exceeded": true,
  "top_complexities": [
    {"function": "process_data", "file": "app/data.py", "complexity": 32},
    {"function": "calculate_metrics", "file": "app/metrics.py", "complexity": 28}
  ]
}
```

Fields:

* `refactoring_pressure` (RP): numeric complexity score (0–100)
* `threshold_exceeded`: `true` if RP exceeds the threshold
* `top_complexities`: top functions by complexity

---

## 3. Agent Actions

1. **Threshold Check**

* If `threshold_exceeded = true` → code is too complex → status = `critical` or `warning` (see below)
* If `threshold_exceeded = false` → code is OK → status = `ok`

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

4. **Proactive Measures (if `threshold_exceeded = false`)**

* Monitor functions with complexity > p90
* Maintain a consistent style guide
* Proactively split large functions

5. **Handling Empty JSON or RP = 0**

* Return `status = warning` with a note that code may be missing or analysis not performed

---

## 4. Multi-Language Project

* Run `codeaudit` for each language (Python, Go, JS), based on project file structure
* RP = max(RP across languages)
* instructions = merge top instructions across languages
* summary = briefly list language and problematic functions

---

## 5. Status and Risk Level Formula

| RP    | status   | risk_level |
| ----- | -------- | ---------- |
| <20   | ok       | low        |
| 20–50 | warning  | medium     |
| 51–75 | critical | high       |
| >75   | critical | critical   |

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

2. **Determine Project Languages**
   - Use `check-deps` output to identify all languages in the project
   - For single-language projects, proceed with that language
   - For multi-language projects, plan to analyze each language

3. **Run Analysis**
   - Run `codeaudit scan <path> --format json --threshold <value> -v` for each language
   - Read and parse the JSON output

4. **Check Threshold**
   - Check `threshold_exceeded` flag in the JSON
   - Determine if code is too complex (status = critical/warning) or OK (status = ok)

5. **Sort Functions**
   - Sort `top_complexities` by descending complexity
   - Select top functions for refactoring recommendations

6. **Generate Instructions**
   - Create clear, actionable instructions (≤10 items, ≤120 characters each)
   - Focus on: splitting functions, reducing nesting, extracting code, simplifying logic

7. **Generate Summary**
   - Create a concise summary (≤150 characters)
   - Mention main problematic functions and risk level

8. **Handle Multi-Language Projects**
   - Use maximum RP across all languages
   - Merge instructions from all languages
   - Create combined summary

9. **Return JSON**
   - Follow the strict schema: status, risk_level, rp, instructions, summary
   - No extra fields allowed
