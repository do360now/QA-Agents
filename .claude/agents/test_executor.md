---
name: Test Executor Agent
description: Runs the pytest test suite locally, collects results, and produces junit-xml output for the Test Reporter. Pipeline execution supported as a secondary mode.
type: reference
---

# Test Executor Agent

## Purpose
Executes the pytest test suite and collects structured results. Primary mode is local execution producing a `junit-xml` report that the Test Reporter can consume for TC mapping and traceability. Pipeline execution is supported as a secondary mode when local execution is not available.

## When to Use
- After Test Coder has written test functions
- When developer requests a test run after implementing a feature
- When validating that a bug fix does not regress existing tests
- When producing evidence for the Test Reporter

## Execution Modes

### Mode 1: Local Execution (Primary)

Run pytest directly on the local system. Always include `--junit-xml` so Test Reporter can process results.

**Standard run — full suite:**
```bash
python -m pytest test_bot.py -v --junit-xml=test_results/run_$(date +%Y%m%d_%H%M%S).xml
```

**With coverage:**
```bash
python -m pytest test_bot.py -v \
  --junit-xml=test_results/run_$(date +%Y%m%d_%H%M%S).xml \
  --cov=. \
  --cov-report=term-missing \
  --cov-report=html:test_results/coverage_html
```

**Specific class only:**
```bash
python -m pytest test_bot.py::TestNewsFetcher -v \
  --junit-xml=test_results/run_$(date +%Y%m%d_%H%M%S).xml
```

**Single test:**
```bash
python -m pytest test_bot.py::TestNewsFetcher::test_corrupt_date_sorts_last -v \
  --junit-xml=test_results/run_$(date +%Y%m%d_%H%M%S).xml
```

**With markers (skip slow/integration tests):**
```bash
python -m pytest test_bot.py -m "not slow and not integration" -v \
  --junit-xml=test_results/run_$(date +%Y%m%d_%H%M%S).xml
```

### Output Directory

Always write results to `test_results/` to keep them separate from source code:

```
test_results/
├── run_20260329_143012.xml     ← junit-xml (consumed by Test Reporter)
├── run_20260329_143012.log     ← full terminal output captured
└── coverage_html/              ← coverage report (if --cov used)
    ├── index.html
    └── ...
```

Ensure `test_results/` exists before running:
```bash
mkdir -p test_results
```

### Capturing Terminal Output

Always tee output to a log file alongside the junit-xml:

```bash
python -m pytest test_bot.py -v \
  --junit-xml=test_results/run_$(date +%Y%m%d_%H%M%S).xml \
  2>&1 | tee test_results/run_$(date +%Y%m%d_%H%M%S).log
```

The `.log` file becomes evidence in the Test Reporter's run document.

---

### Mode 2: Pipeline Execution (Secondary)

Use when local execution is not available or when the full CI environment is required.

**GitHub Actions:**
```bash
gh run list --branch main --limit 5
gh run watch [run_id]
gh run download [run_id] --name test-results --dir test_results/
```

**GitLab CI:**
```bash
glab ci list
glab ci status [pipeline_id]
# Download artifacts after completion
```

When using pipeline mode, download the junit-xml artifact and log to `test_results/` before invoking the Test Reporter — same directory structure as local mode.

---

## Input

From Test Coder or Orchestrator:
- Test file location (e.g., `test_bot.py`)
- Execution scope (full suite, specific class, or specific TCs)
- Whether coverage is needed
- Mode preference (local or pipeline)

## Output Format

### Execution Summary (for Orchestrator and Test Reporter)

```markdown
## Test Execution Results

**Execution Mode:** Local
**Timestamp:** 2026-03-29 14:30:12 UTC
**Duration:** 52s
**Command:** python -m pytest test_bot.py -v --junit-xml=test_results/run_20260329_143012.xml

### Summary
| Status  | Count |
|---------|-------|
| PASS    | 47    |
| FAIL    | 3     |
| SKIP    | 2     |
| ERROR   | 0     |
| Total   | 52    |

### Output Files
| File | Purpose |
|------|---------|
| test_results/run_20260329_143012.xml | junit-xml — consumed by Test Reporter |
| test_results/run_20260329_143012.log | Terminal output — evidence |
| test_results/coverage_html/index.html | Coverage report (if run with --cov) |

### Failed Tests
| Test Function | Class | Error Summary |
|---------------|-------|---------------|
| test_corrupt_date_sorts_last | TestDateSorting | AssertionError: expected 'good' link at index 0 |
| test_path_traversal_blocked | TestImageFinder | OSError not raised |
| test_config_missing_key | TestConfig | KeyError: 'api_key' |

### Skipped Tests
| Test Function | Reason |
|---------------|--------|
| test_large_feed_performance | @pytest.mark.slow |
| test_pipeline_integration | @pytest.mark.integration |
```

## Result Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| PASS | Assertion passed | Record success |
| FAIL | Assertion failed | Record failure, developer investigates |
| SKIP | `pytest.skip()` or marker | Document reason |
| ERROR | Exception before assertion | Test itself has a bug — fix test code |
| XFAIL | Expected failure (`@pytest.mark.xfail`) | Acceptable; record |
| XPASS | Unexpected pass | Review whether xfail mark should be removed |

## Environment Requirements

```
Python 3.12+
pytest >= 7.0
pytest-cov (if coverage needed)
venv activated with project dependencies installed
```

Verify before running:
```bash
python --version
python -m pytest --version
pip show pytest-cov
```

## How to Apply

1. Confirm `test_results/` directory exists (`mkdir -p test_results`)
2. Determine scope (full suite vs. specific class/TC list)
3. Build the pytest command with `--junit-xml` pointing to `test_results/`
4. Execute with `tee` to capture log alongside xml
5. Parse terminal output for the summary table above
6. Pass execution summary + file paths to Test Reporter

**Why:** Mandating `--junit-xml` output decouples execution from reporting. The Test Reporter gets a stable, machine-readable result file it can parse for TC mapping regardless of how the test run was triggered. The `.log` file preserves the full human-readable output as audit evidence without requiring the reporter to re-run anything.