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

**Dependency check for running codeaudit:**

1. Python:
   - Verify Python is installed: python3 --version
   - Verify radon is installed: python3 -m radon --version

2. Golang:
   - Verify Go is installed: go version
   - Ensure version is ≥1.16

3. Node.js / JS:
   - Verify Node.js: node -v (must be ≥14)
   - Verify global modules:
       - acorn: node -e "require('acorn')"
       - acorn-walk: node -e "require('acorn-walk')"
   - ESLint is not required

If any check fails, the agent should provide instructions on how to install the missing packages.

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

## 1. Running the Scan

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

1. Determine the project language
2. Run `codeaudit` with `--threshold` and `-v`
3. Read JSON
4. Check `threshold_exceeded`
5. Sort top_complexities
6. Generate instructions (≤10, ≤120 characters)
7. Generate summary (≤150 characters)
8. Combine results for multi-language projects (max RP)
9. Return JSON strictly in the schema: status, risk_level, rp, instructions, summary
