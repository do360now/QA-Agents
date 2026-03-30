---
name: Test Executor Agent
description: Runs the test suite, collects results, and emits FeedbackEvents for failures that need routing
type: reference
---

# Test Executor Agent

## Purpose
Executes the test suite and does two things with the results:
1. Writes an `execution_report` artifact for the Reporter
2. Classifies failures and emits `FeedbackEvent`s for the Orchestrator to route

This is the only agent that does not call an LLM. It runs `pytest` as a
subprocess, parses stdout, and makes routing decisions based on the error types
it sees.

## When to Use
- Phase.EXECUTION — after Feature Implementer completes
- After every feedback rewind that modified test or feature code

## Inputs

From `PipelineState`:
```python
state.get_artifact(ArtifactKey.TEST_FILE_PATH)    # which file to run
state.get_artifact(ArtifactKey.FEATURE_FILES)     # for context on what changed
```

## Execution Modes

### Mode 1: Local (default)
```bash
# Full suite
python -m pytest test_bot.py -v --tb=short --json-report --json-report-file=.report.json

# After feature_bug rewind — only re-run affected tests
python -m pytest test_bot.py -k "test_corrupt_date or test_empty_pubdate" -v

# With coverage
python -m pytest test_bot.py --cov=. --cov-report=term-missing
```

### Mode 2: Pipeline
```bash
# GitHub Actions
gh run list --branch main --limit 1
gh run watch [run_id]
gh run view [run_id] --log
```

## Failure Classification

This is the core logic of this agent. Every `FAIL` or `ERROR` result is
classified before being written to state. Classification is rule-based —
no LLM required.

| Error pattern | `failure_type` | Rewinds to |
|---------------|----------------|------------|
| `AttributeError`, `ImportError`, `NameError` in test body | `test_bug` | TEST_CODE |
| `AssertionError` with wrong expected value | `feature_bug` | FEATURE_CODE |
| `Exception` raised by production code (not test) | `feature_bug` | FEATURE_CODE |
| Test reveals behaviour not in Risk Register | `new_risk` | RISK |
| `SyntaxError` in test file | `test_bug` | TEST_CODE |
| `SyntaxError` in feature file | `feature_bug` | FEATURE_CODE |

**Classification is conservative**: when ambiguous, prefer `feature_bug` over
`test_bug`. It is cheaper to re-run Feature Implementer than to wrongly blame
the tests.

**Do not classify SKIP or XFAIL as failures.** These are documented and
intentional.

## Emitting FeedbackEvents

After classifying failures, add events to state before the Orchestrator
reads them:

```python
# feature code returned wrong value
state.add_feedback(FeedbackEvent(
    test_id="TC-R1-001",
    failure_type="feature_bug",
    detail="AssertionError: news_list[0].article.link == 'https://example.com/bad', expected 'good'",
    target_phase=Phase.FEATURE_CODE,
))

# test references a class that doesn't exist
state.add_feedback(FeedbackEvent(
    test_id="TC-T1-001",
    failure_type="test_bug",
    detail="AttributeError: module 'config' has no attribute 'Config'",
    target_phase=Phase.TEST_CODE,
))

# test exposed a completely untracked risk
state.add_feedback(FeedbackEvent(
    test_id="TC-R2-001",
    failure_type="new_risk",
    detail="requests.get() hung for 30s with no timeout — risk not in register",
    target_phase=Phase.RISK,
))
```

**Only emit FeedbackEvents for failures worth rewinding for.** If a test
fails for a trivial reason (e.g. wrong import alias), fix it in the report
and flag it as `test_bug`. Do not emit `new_risk` unless the failure reveals
genuinely undiscovered behaviour.

**The Orchestrator routes by priority.** You do not need to pick one type —
emit all that apply. The Orchestrator will take the highest-priority rewind.

## Output Artifact

```python
state.set_artifact(ArtifactKey.EXECUTION_REPORT, {
    "mode": "local",
    "timestamp": "2026-03-29T10:00:00Z",
    "duration_s": 12.4,
    "summary": {
        "pass": 26,
        "fail": 2,
        "skip": 1,
        "error": 0,
        "xfail": 0,
        "xpass": 0,
    },
    "results": [
        {
            "test_id": "TC-R1-001",
            "test_name": "TestDateSorting::test_corrupt_date_sorts_last",
            "status": "FAIL",
            "duration_s": 0.12,
            "error": "AssertionError: assert 'https://example.com/bad' == 'https://example.com/good'",
            "failure_type": "feature_bug",
        },
        {
            "test_id": "TC-S1-001",
            "test_name": "TestPathSecurity::test_path_traversal_blocked",
            "status": "PASS",
            "duration_s": 0.03,
            "error": None,
            "failure_type": None,
        },
        # ...
    ],
    "coverage": {
        "news.py": 87,
        "config.py": 94,
        "main.py": 61,
    },
    "feedback_emitted": ["feature_bug", "test_bug"],
})
```

## Flakiness Detection

If a test fails, re-run it in isolation before classifying:

```bash
python -m pytest test_bot.py::TestDateSorting::test_corrupt_date_sorts_last -v --count=3
```

If it passes on re-run: mark as `XFAIL` with note "flaky — passes in isolation".
Do not emit a FeedbackEvent for flaky tests. Log to `state.record_error()` so
it appears in the report.

## Output Summary

```markdown
## Test Executor Output

**Mode:** Local
**Duration:** 12.4s
**Timestamp:** 2026-03-29 10:00:00 UTC

### Results
| Status | Count |
|--------|-------|
| PASS | 26 |
| FAIL | 2 |
| SKIP | 1 |

### Failed Tests
| TC-ID | Test | Error | Classification |
|-------|------|-------|----------------|
| TC-R1-001 | test_corrupt_date_sorts_last | AssertionError | feature_bug |
| TC-T1-001 | test_config_missing_url_raises | AttributeError | test_bug |

### FeedbackEvents Emitted
- feature_bug → Orchestrator will rewind to FEATURE_CODE
- test_bug → lower priority, will not fire this cycle

### Coverage
- news.py: 87%
- config.py: 94%
- main.py: 61% ← below threshold

**Next:** Orchestrator routes feedback (Phase.EXECUTION → Phase.FEATURE_CODE)
```

## Environment Requirements

```
Python 3.12+
pytest
pytest-json-report    # structured output parsing
pytest-cov            # coverage (optional but recommended)
```

**Why:** Test Executor earns its place by being the only agent that sees ground
truth — what the code actually does, not what it's supposed to do. The
FeedbackEvent classification is what makes the pipeline self-correcting rather
than just a linear sequence. Without it, failures are dead ends. With it, they
drive the next iteration.
