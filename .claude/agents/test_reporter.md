---
name: Test Reporter Agent
description: Creates a structured test run document by mapping pytest results to TC work items. Produces a Polarion-ready report with PASS/FAIL/SKIP status per TC, error details, and evidence links.
type: reference
---

# Test Reporter Agent

## Purpose
Takes the `junit-xml` output from Test Executor and the approved TC list from Test Designer, and produces a complete test run document. Each TC work item is matched to its executed test function, assigned a status (PASS/FAIL/SKIP), and annotated with error details and evidence. The resulting document is structured for direct reference when manually creating a Polarion test run.

## When to Use
- After Test Executor has produced `junit-xml` + log file
- When creating a formal test run record
- When the human needs Polarion-ready evidence to close out a test cycle
- For audit trails and traceability between requirements → risks → TCs → test results

## Input

From Test Executor:
- `test_results/run_YYYYMMDD_HHMMSS.xml` — junit-xml result file
- `test_results/run_YYYYMMDD_HHMMSS.log` — terminal output log
- `test_results/coverage_html/` — coverage report (optional)

From Test Designer (or Orchestrator):
- Approved TC list with TC-ID → test function name mapping

## TC-to-Result Mapping

The core job of this agent is to join the TC list against the junit-xml results.

**Mapping key:** The TC-ID docstring in each test function.

The Test Coder places `"""TC-R1-001: ..."""` as the docstring of each test function. The junit-xml `<testcase>` element carries this as the `name` attribute. The reporter:

1. Parses the junit-xml for all `<testcase>` elements
2. Extracts the TC-ID from the function docstring (via the name field or classname)
3. Looks up each TC-ID in the approved TC list
4. Joins: TC spec ↔ test result
5. Flags any TC with no matching result as `NOT RUN`
6. Flags any result with no matching TC as `UNTRACKED` (test exists but has no TC spec)

## Output Format

### Test Run Document

```markdown
# Test Run: TR-[YYYY]-[NNN]

**Project:** [project name]
**Date:** YYYY-MM-DD HH:MM UTC
**Duration:** [N]s
**Executed by:** Test Executor (local)
**Pytest Command:** python -m pytest test_bot.py -v --junit-xml=...
**Results File:** test_results/run_YYYYMMDD_HHMMSS.xml
**Log File:** test_results/run_YYYYMMDD_HHMMSS.log

---

## Summary

| Status     | Count |
|------------|-------|
| PASS       | 47    |
| FAIL       | 3     |
| SKIP       | 2     |
| NOT RUN    | 1     |
| UNTRACKED  | 2     |
| **Total**  | **55**|

Coverage: 84% (see test_results/coverage_html/index.html)

---

## TC Result Mapping

| TC ID      | Title                                      | Test Function                        | Class              | Status    | Duration | Notes                          |
|------------|--------------------------------------------|--------------------------------------|--------------------|-----------|----------|--------------------------------|
| TC-R1-001  | Date parsing with invalid RFC2822 format   | test_corrupt_date_sorts_last         | TestDateSorting    | ✅ PASS   | 0.12s    | —                              |
| TC-R1-002  | Empty pub_date handled gracefully          | test_empty_pubdate_sorts_last        | TestDateSorting    | ✅ PASS   | 0.08s    | —                              |
| TC-R1-003  | None pub_date handled gracefully           | test_none_pubdate_sorts_last         | TestDateSorting    | ✅ PASS   | 0.07s    | —                              |
| TC-S2-001  | Path traversal in ImageFinder blocked      | test_path_traversal_blocked          | TestImageFinder    | ❌ FAIL   | 0.09s    | OSError not raised — see §3.1  |
| TC-S2-002  | Symlink escape in image path blocked       | test_symlink_escape_blocked          | TestImageFinder    | ✅ PASS   | 0.11s    | —                              |
| TC-P1-001  | Feed parse completes within 2s             | test_large_feed_under_2s             | TestPerformance    | ⏭ SKIP   | —        | @pytest.mark.slow              |
| TC-T1-001  | Config validates required keys on startup  | test_config_missing_key              | TestConfig         | ❌ FAIL   | 0.04s    | KeyError not caught — see §3.2 |
| TC-T2-001  | Auth failure returns 401 not 500           | test_auth_failure_returns_401        | TestAuth           | 🔲 NOT RUN | —       | Test function not found in XML |

---

## Failed Tests — Detail

### §3.1 TC-S2-001 — test_path_traversal_blocked

**Status:** FAIL
**Class:** TestImageFinder
**Duration:** 0.09s

**Error:**
```
AssertionError: OSError was not raised
  File "test_bot.py", line 214, in test_path_traversal_blocked
    with pytest.raises(OSError):
AssertionError: DID NOT RAISE <class 'OSError'>
```

**Analysis:** The production code in `content.py::ImageFinder._resolve_path()` does not currently validate for path traversal sequences (`../`). Feature implementation required.

**Recommended Action:** Developer to add path sanitisation in `ImageFinder._resolve_path()`. Re-run after fix.

---

### §3.2 TC-T1-001 — test_config_missing_key

**Status:** FAIL
**Class:** TestConfig
**Duration:** 0.04s

**Error:**
```
KeyError: 'api_key'
  File "config.py", line 38, in validate
    return self._data['api_key']
KeyError: 'api_key'
```

**Analysis:** Config.validate() raises unhandled `KeyError` instead of a structured `ConfigValidationError`. Test expects the exception to be caught and re-raised as a domain exception.

**Recommended Action:** Wrap dict access in config.py with explicit error handling.

---

## Skipped Tests — Detail

| TC ID     | Test Function           | Reason              |
|-----------|-------------------------|---------------------|
| TC-P1-001 | test_large_feed_under_2s | @pytest.mark.slow — excluded from standard run |

---

## Not Run — Detail

| TC ID     | Expected Function          | Reason |
|-----------|----------------------------|--------|
| TC-T2-001 | test_auth_failure_returns_401 | Function not found in junit-xml. Either not yet written by Test Coder or excluded by scope filter. |

---

## Untracked Tests (no TC mapping)

Tests that executed but have no corresponding TC work item:

| Test Function               | Class        | Status  |
|-----------------------------|--------------|---------|
| test_legacy_feed_format     | TestNewsFetcher | PASS |
| test_retry_on_connection_err| TestNewsFetcher | PASS |

These tests provide coverage but have no formal TC. Consider whether they should be backfilled with TC specs.

---

## Evidence

| File | Description |
|------|-------------|
| test_results/run_20260329_143012.xml | junit-xml — machine-readable full results |
| test_results/run_20260329_143012.log | Terminal output — full pytest output with timings |
| test_results/coverage_html/index.html | Coverage report — 84% overall |

---

## Polarion Test Run Entry Guide

When creating the Polarion test run manually, use this mapping:

| Polarion Field | Value |
|----------------|-------|
| Test Run ID | TR-2026-NNN (assign next sequential number) |
| Title | [project] — [YYYY-MM-DD] Test Run |
| Status | [In Progress / Completed] |
| Executed by | [your name] |
| Date | YYYY-MM-DD |

For each TC work item in the test run:
- Set status from the TC Result Mapping table above
- Paste the error detail from §3.x into the TC comment field (for failures)
- Attach `run_YYYYMMDD_HHMMSS.xml` and `.log` as run-level attachments
- Link the coverage report if available

```

## Test Run ID Convention

Format: `TR-[YYYY]-[NNN]`

Increment NNN sequentially per project per year. Track in a local `test_results/index.md`:

```markdown
# Test Run Index

| ID           | Date       | Result        | File |
|--------------|------------|---------------|------|
| TR-2026-001  | 2026-03-29 | 47P / 3F / 2S | run_20260329_143012.xml |
| TR-2026-002  | 2026-03-30 | 50P / 0F / 2S | run_20260330_090000.xml |
```

## Status Icons

| Symbol | Status | Meaning |
|--------|--------|---------|
| ✅ | PASS | Assertion succeeded |
| ❌ | FAIL | Assertion failed or unexpected exception |
| ⏭ | SKIP | `pytest.skip()` or marker excluded the test |
| 💥 | ERROR | Exception raised before assertion (test code bug) |
| 🔲 | NOT RUN | TC has no matching result in the xml |
| ⚠️ | UNTRACKED | Result has no matching TC work item |

## How to Apply

1. Receive `junit-xml` path + log path from Test Executor
2. Receive approved TC list (TC-ID → function name) from Orchestrator
3. Parse `junit-xml` using standard XML parsing — extract all `<testcase>` elements with name, classname, time, failure/skipped child nodes
4. Join TC list against parsed results on TC-ID (extracted from docstring in the `name` field)
5. Classify each TC: PASS, FAIL, SKIP, ERROR, NOT RUN, UNTRACKED
6. For each FAIL and ERROR: extract full error message and write a §3.x detail section
7. Write the full test run document to `test_results/TR-YYYY-NNN.md`
8. Update `test_results/index.md`
9. Output the Polarion entry guide section so the human knows exactly what to fill in

**Why:** The mapping table is the primary deliverable. It collapses the gap between "tests ran" and "we know which requirements were verified." Without explicit TC-to-result traceability, a green test run is evidence of nothing specific. With it, the human can walk into Polarion and close out each work item with confidence.