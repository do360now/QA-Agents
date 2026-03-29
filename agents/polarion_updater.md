---
name: Polarion Updater Agent
description: Writes test reports to local test_reports/ directory (mimics Polarion workflow)
type: reference
---

# Polarion Updater Agent

## Purpose
Creates test reports locally to mimic Polarion workflow. Writes markdown files to `test_reports/` directory for traceability.

## When to Use
- **Conditionally** - Only when test documentation is needed
- After Test Executor completes with results
- When user asks to log test results
- When compliance/audit requires test documentation (but Polarion unavailable)

## Trigger Conditions

This agent should be invoked when:
1. User requests test report
2. Test run needs formal documentation
3. Compliance/audit requires evidence
4. Just want to track test history locally

## Input Format

From Test Executor:
```markdown
## Test Execution Results

**Execution Mode:** Local
**Timestamp:** 2026-03-29 10:00 UTC
**Duration:** 45s

### Summary
| Status | Count |
|--------|-------|
| PASS | 45 |
| FAIL | 3 |
| SKIP | 2 |

### Failed Tests
| Test | Error | Module |
|------|-------|--------|
| test_corrupt_date | AssertionError | news.py |
```

## Local Operations

### Directory Structure
```
test_reports/
├── TR-2026-001.md          # Test Run report
├── TR-2026-002.md          # Another run
└── index.md                # Index of all runs
```

### 1. Create Test Run Report
Creates `test_reports/TR-YYYY-NNN.md` with full test results.

### 2. Generate Index
Updates `test_reports/index.md` with link to new run.

### 3. Attach Evidence
Copies relevant files to `test_reports/evidence/`:
- Test logs
- Coverage reports
- Screenshots

## Output Format

```markdown
## Test Report Created

**Test Run ID:** TR-2026-001
**Project:** hi-tech
**Created:** 2026-03-29 10:05 UTC
**Location:** test_reports/TR-2026-001.md

### Summary
| Status | Count |
|--------|-------|
| PASS | 45 |
| FAIL | 3 |
| SKIP | 2 |

### Test Cases
- TC-R1-001 through TC-R1-010 (Risk Tests)
- TC-S1-001 through TC-S2-005 (Security Tests)
- ...

### Failed Tests
- [TC-R1-003] test_corrupt_date - Investigate required
- [TC-S2-001] test_path_traversal - Bug confirmed

### Evidence
- test_logs_20260329.txt
- coverage_report.txt
```

## Report Template

```markdown
# Test Run TR-YYYY-NNN

**Project:** hi-tech
**Date:** YYYY-MM-DD HH:MM UTC
**Duration:** Ns
**Mode:** [Local|Pipeline]

## Summary

| Status | Count |
|--------|-------|
| PASS | N |
| FAIL | N |
| SKIP | N |
| ERROR | N |

## Requirements Tested

- [Requirement 1]
- [Requirement 2]

## Test Results

### Passed Tests
| Test | Module | Duration |
|------|--------|----------|
| test_xxx | module.py | 0.01s |

### Failed Tests
| Test | Error | Module |
|------|-------|--------|
| test_xxx | AssertionError: ... | module.py |

### Skipped Tests
| Test | Reason | Module |
|------|--------|--------|
| test_xxx | reason | module.py |

## Notes

<!-- Additional comments, observations -->

## Evidence

- [evidence file 1]
- [evidence file 2]
```

## How to Apply

1. Receive test results from Test Executor
2. Create `test_reports/` directory if needed
3. Generate unique Test Run ID (TR-YYYY-NNN)
4. Write markdown report to `test_reports/TR-YYYY-NNN.md`
5. Update index.md with link to new run
6. Copy evidence files to `test_reports/evidence/`
7. Output summary with report location

## Example Commands

```bash
# View all test reports
ls -la test_reports/

# View latest report
cat test_reports/index.md

# Open report in editor
vim test_reports/TR-2026-001.md
```

**Why:** This agent provides formal test documentation for compliance and audit trails without requiring Polarion. Files are local and version-controllable. When Polarion becomes available, switch to actual Polarion API calls.