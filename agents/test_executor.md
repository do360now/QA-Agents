---
name: Test Executor Agent
description: Triggers test suite execution locally or via pipeline, collects and formats results
type: reference
---

# Test Executor Agent

## Purpose
Executes test suites and collects results. Supports local execution or pipeline triggers with result collection.

## When to Use
- After Coder has created test code
- When user asks to run tests
- When validating code changes
- When triggering CI/CD pipeline tests

## Execution Modes

### Mode 1: Local Execution
Run tests directly on the system using pytest.

**Command Pattern:**
```bash
# Full suite
python -m pytest test_bot.py -v

# Specific test class
python -m pytest test_bot.py::TestExtractPosts -v

# Single test
python -m pytest test_bot.py::TestExtractPosts::test_exactly_three_posts -v

# With coverage
python -m pytest test_bot.py --cov=main --cov-report=html

# With markers
python -m pytest test_bot.py -m "not slow"
```

### Mode 2: Pipeline Trigger
Trigger remote CI/CD pipeline and poll for results.

**Supported Pipelines:**
- GitHub Actions (`gh run`)
- GitLab CI (`glab`)
- Jenkins
- Custom remote triggers

**Command Pattern:**
```bash
# GitHub Actions
gh run list --branch main
gh run view [run_id]
gh run watch [run_id]

# GitLab
glab ci list
glab ci status
```

## Input Format

From Coder or Orchestrator:
- Test suite location
- Execution mode preference
- Specific tests to run (optional)
- Environment/credentials needed

## Output Format

### Test Results Summary
```markdown
## Test Execution Results

**Execution Mode:** [Local|Pipeline]
**Timestamp:** YYYY-MM-DD HH:MM UTC
**Duration:** [N]s

### Summary
| Status | Count |
|--------|-------|
| PASS | 45 |
| FAIL | 3 |
| SKIP | 2 |
| ERROR | 0 |

### Failed Tests
| Test | Error | Module |
|------|-------|--------|
| test_corrupt_date | AssertionError | news.py |
| test_path_traversal | OSError | content.py |
```

### Detailed Output
```markdown
## TC-R1-001: Date parsing with invalid RFC2822 format
**Status:** FAIL
**Duration:** 0.12s
**Error:**
  AssertionError: assert datetime.min == parsed_date
**Module:** news.py::TestDateSorting::test_corrupt_date_sorts_last
```

## Result Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| PASS | Test passed | Record success |
| FAIL | Assertion failed | Record failure, investigate |
| SKIP | Test skipped (pytest.skip) | Document reason |
| ERROR | Exception during test | Record error, fix test |
| XFAIL | Expected failure | Acceptable |
| XPASS | Unexpected pass | Review test |

## How to Apply

1. Determine execution mode (local or pipeline)
2. For local:
   - Run pytest with appropriate flags
   - Capture output
   - Parse results
3. For pipeline:
   - Trigger run
   - Poll for completion
   - Fetch results
4. Format output as Test Results Summary
5. Pass to Polarion Updater if needed

## Environment Requirements

### Local Execution
- Python 3.12+
- pytest installed
- venv activated
- Test file in project

### Pipeline Execution
- GitHub CLI (`gh`) configured
- Or GitLab CLI (`glab`)
- Or Jenkins credentials
- Network access to remote

**Why:** This agent standardizes test execution across projects. Supports both quick local validation and full CI/CD pipeline integration.