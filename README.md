# CodeAudit

`codeaudit` is a CLI tool and Claude Code skill for analyzing the complexity of your codebase and estimating **refactoring pressure**.
It supports **Python, Golang, and JavaScript** projects, and provides a quantitative measure of how "complicated" your code is, highlighting functions, modules, and files that may require refactoring.

## 🚀 Installation

### Automatic Installation (Recommended)

Install in one line:

```bash
eval "$(curl -s https://raw.githubusercontent.com/trifonovmixail/claude-code-audit/main/install.sh)"
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

3. **Aggregating Metrics**
   The following metrics are collected for each language:

| Metric                    | Description                                        |
| ------------------------- | -------------------------------------------------- |
| `functions`               | Total number of functions analyzed                 |
| `p50_complexity`          | 50th percentile cyclomatic complexity (median)     |
| `p90_complexity`          | 90th percentile cyclomatic complexity (upper tail) |
| `max_complexity`          | Maximum cyclomatic complexity in the codebase      |
| `top_complexities`        | Top 20 most complex functions                      |
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
  "summary": {
    "functions": 320,
    "p50_complexity": 1,
    "p90_complexity": 6,
    "max_complexity": 19,
    "refactoring_pressure": 10
  },
  "risk_level": "low",
  "threshold_exceeded": false,
  "top_complexities": [
    {"function": "foo", "file": "package/module.py", "complexity": 19},
    {"function": "bar", "file": "package/module.py", "complexity": 14}
  ]
}
```

### Risk Levels

| RP Score | Risk Level | Interpretation                                     |
| -------- | ---------- | -------------------------------------------------- |
| 0–20     | Low        | Code is simple and maintainable                    |
| 21–50    | Medium     | Some functions may need refactoring                |
| 51–80    | High       | Code is complex; refactoring recommended           |
| 81–100   | Critical   | Code is very complex; immediate attention required |

> `threshold_exceeded` is `true` if RP exceeds a user-defined threshold (default 60).

### Top Complexities

* `top_complexities` shows **the 20 most complex functions** across the codebase, sorted by cyclomatic complexity.
* This helps focus refactoring efforts on the functions with the highest complexity first.

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
* Python and Go metrics remain unchanged.
* Refactoring Pressure is **a relative measure**, intended to help prioritize refactoring, not an absolute indicator of code quality.
* The
