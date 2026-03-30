---
name: Test Run Creator Agent
description: Creates a Polarion test run and maps pytest results to TC work items. Reads tc_wi_mapping.csv for WI IDs and extracts TC IDs from function names in the junit-xml. Write agent — called only after explicit approval.
type: reference
---

# Test Run Creator Agent

## Purpose
Takes the `junit-xml` from Test Executor and the `tc_wi_mapping.csv` from Polarion Writer, creates a test run in Polarion, and records PASS / FAIL / BLOCKED for each TC with error details and attached evidence.

This is a **write agent** — it creates real Polarion records. Called only after
explicit human approval (MODE_A) or when all tests pass in the Orchestrator's
automated pipeline (MODE_B).

## When to Use
- **MODE_A:** After human reviews Test Executor results and responds at Gate 2
- **MODE_B:** Automatically after Test Executor reports all tests passing

---

## Step 1 — Read Tool Documentation

```bash
cat POLARION_TOOLS.md        # preferred
cat claude.md                # fallback
python polarion_cli.py --help
python polarion_client.py --help
```

Understand the syntax for:
- **Creating a test run** — title, project, linked requirement
- **Adding a test record** — TC WI ID, result status, comment, duration
- **Attaching evidence** — log file, xml file attachment to a test run

---

## Step 2 — Load the TC→WI Mapping

Read `test_results/tc_wi_mapping.csv` written by Polarion Writer:

```python
import csv

tc_wi_map = {}
with open("test_results/tc_wi_mapping.csv", newline="") as f:
    for row in csv.reader(f):
        if len(row) == 2:
            tc_id, wi_id = row[0].strip(), row[1].strip()
            tc_wi_map[tc_id] = wi_id
# Result: {"TC-R1-001": "WI-4521", "TC-R1-002": "WI-4522", ...}
```

If the file is missing, stop and report — the mapping is required to link results
to Polarion WIs. Do not proceed without it.

---

## Step 3 — Parse the junit-xml

Parse the junit-xml and extract TC IDs from function names using a regex:

```python
import re
import xml.etree.ElementTree as ET

def extract_tc_id(name: str) -> str | None:
    """
    Extract TC ID from a pytest function name.
    
    Expected format: test_tc_r1_001_some_descriptive_name
    Extracted:       TC-R1-001
    
    Also handles parametrized names like:
      test_tc_r1_001_003_004_blank_inputs[None-ValueError]
    Returns the first TC ID found.
    """
    match = re.search(r'tc[_-]([a-z]\d+)[_-](\d+)', name, re.IGNORECASE)
    if match:
        category = match.group(1).upper()   # e.g. R1, S2
        number = match.group(2)              # e.g. 001
        return f"TC-{category}-{number}"    # e.g. TC-R1-001
    return None

tree = ET.parse("test_results/run_YYYYMMDD_HHMMSS.xml")
root = tree.getroot()

results = {}
for testcase in root.iter("testcase"):
    name      = testcase.attrib.get("name", "")
    classname = testcase.attrib.get("classname", "")
    duration  = testcase.attrib.get("time", "0")

    failure = testcase.find("failure")
    skipped = testcase.find("skipped")
    error   = testcase.find("error")

    if failure is not None:
        status  = "FAILED"
        message = (failure.attrib.get("message") or failure.text or "").strip()
    elif skipped is not None:
        status  = "BLOCKED"   # Polarion uses BLOCKED for skipped/not-run
        message = (skipped.attrib.get("message") or "").strip()
    elif error is not None:
        status  = "FAILED"    # ERROR = test code bug, still recorded as FAILED
        message = (error.attrib.get("message") or error.text or "").strip()
        message = f"[TEST ERROR — not a feature bug] {message}"
    else:
        status  = "PASSED"
        message = ""

    tc_id = extract_tc_id(name)

    results[tc_id or f"UNTRACKED:{name}"] = {
        "function": name,
        "class":    classname,
        "duration": duration,
        "status":   status,
        "message":  message,
        "tc_id":    tc_id,
    }
```

After parsing, cross-reference against `tc_wi_map`:
- TC in mapping but **not in xml** → `NOT RUN`
- TC in xml but **not in mapping** → `UNTRACKED` (test exists, no Polarion WI)

---

## Step 4 — Pre-flight Summary

Present the full mapping before writing anything to Polarion:

```markdown
## Test Run Creator — Pre-flight

**Requirement:** [POLARION_ID]
**Results from:** test_results/run_YYYYMMDD_HHMMSS.xml
**Mapping from:** test_results/tc_wi_mapping.csv

### TC Result Mapping
| TC ID      | Polarion WI ID | Function                              | Status   | Duration |
|------------|---------------|---------------------------------------|----------|----------|
| TC-R1-001  | WI-4521       | test_tc_r1_001_invalid_input_raises   | ✅ PASSED | 0.12s   |
| TC-R1-002  | WI-4522       | test_tc_r1_002_valid_input_returns    | ✅ PASSED | 0.08s   |
| TC-R2-001  | WI-4523       | test_tc_r2_001_external_failure       | ❌ FAILED | 0.09s   |
| TC-S1-001  | WI-4524       | (not in xml)                          | 🔲 NOT RUN | —      |

### Untracked Tests (in xml, no Polarion WI)
| Function | Status |
|----------|--------|
| test_legacy_behaviour | PASSED |

**Test Run title:** "[POLARION_ID] — Test Run YYYY-MM-DD"

Proceed? Reply `YES` to create the test run in Polarion.
```

**MODE_A:** Wait for `YES`.
**MODE_B:** Orchestrator confirms automatically — proceed immediately.

---

## Step 5 — Create the Test Run

```bash
# PLACEHOLDER — replace with actual syntax from POLARION_TOOLS.md
python polarion_cli.py create-test-run \
  --project <PROJECT_ID> \
  --title "[POLARION_ID] — Test Run YYYY-MM-DD" \
  --linked-requirement <POLARION_ID> \
  --description "Pytest run for requirement [POLARION_ID]. Results mapped from test_results/run_YYYYMMDD_HHMMSS.xml."
```

Record the returned test run ID (e.g. `TR-0042`). All subsequent steps depend on it.

---

## Step 6 — Add TC Results

For each TC in the mapping that has a result (skip `NOT RUN` — do not add records for tests that did not execute):

```bash
# PASSED
# PLACEHOLDER — replace with actual syntax from POLARION_TOOLS.md
python polarion_cli.py add-test-record \
  --test-run TR-0042 \
  --test-case WI-4521 \
  --result PASSED \
  --duration 0.12 \
  --comment "test_tc_r1_001_invalid_input_raises_value_error"

# FAILED — include full error message
python polarion_cli.py add-test-record \
  --test-run TR-0042 \
  --test-case WI-4523 \
  --result FAILED \
  --duration 0.09 \
  --comment "AssertionError: ValueError not raised. See log: run_YYYYMMDD_HHMMSS.log"

# BLOCKED (skipped)
python polarion_cli.py add-test-record \
  --test-run TR-0042 \
  --test-case WI-4524 \
  --result BLOCKED \
  --comment "@pytest.mark.slow — excluded from this run"
```

### Status mapping

| pytest result | Polarion status |
|--------------|----------------|
| PASSED | PASSED |
| FAILED | FAILED |
| skipped | BLOCKED |
| ERROR (test bug) | FAILED — prefix comment with `[TEST ERROR]` |
| NOT RUN | Not added — flagged in summary only |

---

## Step 7 — Attach Evidence

```bash
# PLACEHOLDER — replace with actual syntax from POLARION_TOOLS.md
python polarion_cli.py attach \
  --test-run TR-0042 \
  --file test_results/run_YYYYMMDD_HHMMSS.log \
  --title "pytest terminal output"

python polarion_cli.py attach \
  --test-run TR-0042 \
  --file test_results/run_YYYYMMDD_HHMMSS.xml \
  --title "junit-xml results"

# If coverage was generated
python polarion_cli.py attach \
  --test-run TR-0042 \
  --file test_results/coverage_html/index.html \
  --title "coverage report"
```

---

## Step 8 — Output Creation Summary

```markdown
## Test Run Creator — Summary

**Requirement:** [POLARION_ID]
**Polarion Test Run ID:** TR-0042
**Created:** YYYY-MM-DD HH:MM UTC

### Results Recorded
| TC ID      | Polarion WI ID | Status     | Duration | Notes |
|------------|---------------|------------|----------|-------|
| TC-R1-001  | WI-4521       | ✅ PASSED  | 0.12s    | —     |
| TC-R1-002  | WI-4522       | ✅ PASSED  | 0.08s    | —     |
| TC-R2-001  | WI-4523       | ❌ FAILED  | 0.09s    | ValueError not raised — see log |
| TC-S1-001  | WI-4524       | 🔲 NOT RUN | —        | Not found in xml |

### Untracked Tests (not added to test run)
| Function | Status |
|----------|--------|
| test_legacy_behaviour | PASSED — no TC WI, not recorded |

### Evidence Attached
- pytest terminal output: run_YYYYMMDD_HHMMSS.log
- junit-xml: run_YYYYMMDD_HHMMSS.xml

### Agent Failures (if any steps failed)
| Step | Error |
|------|-------|
| — | — |

---
QA cycle complete for [POLARION_ID].
MODE_A: Review TR-0042 in Polarion. Failed TCs require developer investigation.
MODE_B: Orchestrator pipeline complete. Failed TCs were not retried (tests passed
        at time of run) — if FAILED appears here, it means tests regressed
        after the last retry. Flag for human review.
```

---

## Error Handling

| Situation | Action |
|-----------|--------|
| `tc_wi_mapping.csv` missing | Stop — report error, create nothing |
| junit-xml missing or unreadable | Stop — report error |
| TC ID cannot be extracted from function name | Mark as UNTRACKED, do not add to test run, flag in summary |
| Test run creation fails | Stop — report error, do not add records to a non-existent run |
| Single TC record add fails | Log failure, continue with remaining TCs, report at end |
| Attachment upload fails | Log it — test run record exists, flag for manual attachment |

---

## How to Apply

1. Read tool documentation (`POLARION_TOOLS.md`)
2. Load `test_results/tc_wi_mapping.csv` — stop if missing
3. Parse junit-xml, extract TC IDs using regex on function names
4. Cross-reference: identify NOT RUN and UNTRACKED cases
5. Present pre-flight table — wait for `YES` (MODE_A) or proceed (MODE_B)
6. Create test run in Polarion, record TR-XXXX
7. Add one test record per TC result (skip NOT RUN)
8. Attach log and xml as evidence
9. Output creation summary

**Why function name extraction matters:** The `name` field in junit-xml is the
function name — always present, always machine-readable. Docstrings are not
stored in junit-xml by default. The Test Coder's naming convention
(`test_tc_r1_001_...`) makes extraction reliable with a simple regex, removing
the need for any pytest plugins or custom configuration.
