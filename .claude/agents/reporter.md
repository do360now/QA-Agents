---
name: Reporter Agent
description: Generates test reports — one interface, two backends (local markdown or Polarion)
type: reference
---

# Reporter Agent

## Purpose
Produces the final test report from the execution results. One interface,
two backends — the caller never needs to know which one is active.

```python
ReporterAgent(backend="local")    # writes markdown to test_reports/
ReporterAgent(backend="polarion") # posts to Polarion via API
```

This replaces the original Polarion Updater, which was a shallow module — it
wrapped three lines of file writing in an agent. The Reporter earns its place
by hiding a genuine abstraction: the difference between local storage and
Polarion's API is significant, but the pipeline should not care.

## When to Use
- Phase.REPORTING — always the final phase before DONE
- When user explicitly requests a report mid-run
- When compliance requires a formal test record

## Inputs

From `PipelineState`:
```python
state.get_artifact(ArtifactKey.EXECUTION_REPORT)    # from Test Executor
state.get_artifact(ArtifactKey.RISK_REGISTER)        # for traceability matrix
state.get_artifact(ArtifactKey.TEST_SUITE_MANIFEST)  # for test case metadata
state.get_artifact(ArtifactKey.REQUIREMENTS)          # for requirements coverage
```

## Output Artifact

```python
state.set_artifact(ArtifactKey.REPORT_PATH,
    "test_reports/TR-2026-001.md"      # local backend
    # or
    "polarion://PROJECT/TR-2026-001"   # Polarion backend
)
```

## Backend: Local (default)

Writes a structured markdown file to `test_reports/`. Files are
version-controllable and require no external dependencies.

### Directory Structure
```
test_reports/
├── index.md              # links to all runs, most recent first
├── TR-2026-001.md        # this run
├── TR-2026-002.md
└── evidence/
    ├── TR-2026-001/
    │   ├── pytest_output.txt
    │   └── coverage_report.txt
    └── TR-2026-002/
```

### Run ID Generation
Format: `TR-YYYY-NNN` where NNN is zero-padded and auto-incremented.
Reads `test_reports/index.md` to find the last used ID.
If `test_reports/` does not exist, creates it and starts at `TR-{year}-001`.

### Report Template

```markdown
# Test Run TR-YYYY-NNN

**Project:** [state.scope]
**Date:** YYYY-MM-DD HH:MM UTC
**Duration:** Ns
**Mode:** Local | Pipeline
**Pipeline Run:** [state.run_id]

---

## Summary

| Status | Count |
|--------|-------|
| PASS | N |
| FAIL | N |
| SKIP | N |
| ERROR | N |

**Overall:** PASS | FAIL

---

## Requirements Coverage

| REQ-ID | Requirement | Tests | Status |
|--------|-------------|-------|--------|
| REQ-001 | System must post tweets on a schedule | TC-R1-001, TC-R1-002 | ✓ Covered |
| REQ-005 | HTTP requests must enforce timeouts | TC-R2-001 | ✗ Not covered |

---

## Risk Coverage

| Risk ID | Description | Severity | TC-IDs | Test Status |
|---------|-------------|----------|--------|-------------|
| R1 | Date parsing fails on invalid RFC2822 | High | TC-R1-001, TC-R1-002 | PASS |
| S1 | Path traversal in ImageFinder | Critical | TC-S1-001, TC-S1-002 | FAIL |

---

## Test Results

### Passed (N)
| TC-ID | Test Name | Module | Duration |
|-------|-----------|--------|----------|
| TC-R1-001 | test_corrupt_date_sorts_last | news.py | 0.12s |

### Failed (N)
| TC-ID | Test Name | Error | Module |
|-------|-----------|-------|--------|
| TC-S1-001 | test_path_traversal_blocked | AssertionError | content.py |

### Skipped (N)
| TC-ID | Test Name | Reason |
|-------|-----------|--------|
| TC-P1-001 | test_large_feed_performance | marked slow |

---

## Coverage

| Module | Coverage |
|--------|----------|
| news.py | 87% |
| config.py | 94% |
| main.py | 61% |

---

## Observations

<!-- Auto-generated notes from execution_report -->
- main.py coverage below 70% threshold — consider adding integration tests
- TC-S1-001 failure confirmed a real bug — path traversal not blocked

---

## Evidence

- [pytest_output.txt](evidence/TR-2026-001/pytest_output.txt)
- [coverage_report.txt](evidence/TR-2026-001/coverage_report.txt)
```

### Index Update

After writing the report, prepend to `test_reports/index.md`:

```markdown
| TR-2026-001 | 2026-03-29 | hi-tech/ | 26 PASS / 2 FAIL | [View](TR-2026-001.md) |
```

## Backend: Polarion

Posts test results to Polarion ALM via its REST API. Same report content,
different transport.

```python
# Configuration (from environment or config file)
POLARION_URL      = "https://polarion.yourcompany.com"
POLARION_PROJECT  = "VCP"
POLARION_USER     = os.environ["POLARION_USER"]
POLARION_TOKEN    = os.environ["POLARION_TOKEN"]
```

### API Operations

**1. Create Test Run**
```
POST /polarion/rest/v1/projects/{projectId}/testruns
Body: { "title": "TR-2026-001", "type": "automated", ... }
```

**2. Link Test Cases**
```
PATCH /polarion/rest/v1/projects/{projectId}/testruns/{runId}/testrecords
Body: [{ "testCaseId": "TC-R1-001", "result": "passed", ... }]
```

**3. Attach Evidence**
```
POST /polarion/rest/v1/projects/{projectId}/testruns/{runId}/attachments
Body: [pytest_output.txt, coverage_report.txt]
```

### Mapping: PipelineState → Polarion

| PipelineState field | Polarion field |
|--------------------|----------------|
| `TC-R1-001` | Test Case Work Item ID |
| `PASS/FAIL/SKIP` | Test Record result |
| `duration_s` | Execution time |
| `error` | Comment / defect link |
| `state.run_id` | Custom field: pipeline_run_id |

### Error Handling

Polarion API failures are non-fatal by design — the test run happened, the
code works or doesn't, regardless of whether the report was stored. If the
Polarion call fails:

1. `state.record_error("Polarion API failed: {detail}")`
2. Fall back to local markdown automatically
3. Log Polarion URL that was attempted so it can be posted manually

## Switching Backends

The `backend` parameter is injected at Orchestrator construction:

```python
# In main.py — read from env or CLI flag
backend = "polarion" if os.environ.get("POLARION_TOKEN") else "local"

reporter = ReporterAgent(backend=backend)
```

The rest of the pipeline never knows or cares which backend is active.

## Output Summary

```markdown
## Reporter Output

**Backend:** Local
**Report ID:** TR-2026-001
**Location:** test_reports/TR-2026-001.md
**Evidence:** test_reports/evidence/TR-2026-001/
**Index:** Updated

### Coverage Summary
- Requirements covered: 10/12 (83%)
- Risks covered: 8/9 (89%)

**Pipeline:** DONE
```

**Why:** The original Polarion Updater was shallow — three lines of file I/O
wrapped in agent ceremony. The Reporter earns its depth by absorbing a real
abstraction: the gap between local markdown and Polarion's API is significant,
but it should be invisible to the pipeline. One interface, swappable backend,
zero changes to any other agent when you cut over to real Polarion.
