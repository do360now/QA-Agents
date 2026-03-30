# Pipeline Improvement Requirements

## Priority: Medium

### 1. Deep Artifact Serialization
**File:** `pipeline_state.py`
**Lines:** 318-327 (`_serialise_artifacts`)

**Problem:** Current serialization only handles shallow lists of dataclasses. Fails for nested structures like `list[list[QATestSpec]]` or dicts containing dataclasses.

**Requirement:** Extend `_serialise_artifacts` to recursively handle:
- Nested lists of dataclasses
- Dicts with dataclass values
- Nested dicts containing lists of dataclasses

---

## Priority: Low

### 2. Cache Phase Ordering
**File:** `orchestrator.py`
**Lines:** 240-251 (`_next_phase`)

**Problem:** Ordered phase list is recalculated on every call to `_next_phase`.

**Requirement:** Move phase ordering to a class-level constant:
```python
class Orchestrator:
    _PHASE_ORDER: list[Phase] = sorted([p for p in Phase if p not in (Phase.FAILED,)], key=lambda p: p.value)
```

### 3. Remove Redundant Feedback Clear
**File:** `orchestrator.py`
**Line:** 225

**Problem:** `state.feedback.clear()` is called after `consume_feedback()` already removes matching items.

**Requirement:** Remove line 225 — `consume_feedback` already removes matching feedback events.

### 4. Add Unknown Feedback Type Warning
**File:** `orchestrator.py`
**Lines:** 229-231

**Problem:** Pipeline silently continues when feedback contains unrecognized types.

**Requirement:** Log a warning for any unhandled feedback types before advancing, rather than silently continuing.

### 5. Optimize Artifact Key Error Message
**File:** `pipeline_state.py`
**Line:** 165

**Problem:** Calls `list(self.artifacts.keys())` on every KeyError.

**Requirement:** Store available artifact keys as a cached property or only compute once when needed.

---

## Priority: Test Hygiene

### 6. Fix Mutable Fixture State
**File:** `test_pipeline.py`
**Lines:** 299-315 (`_make_executor_with_feedback`)

**Problem:** Mutates `all_mock_agents` dict in place, which could cause issues if tests run in isolation or order changes.

**Requirement:** Create a fresh copy of agents for each test rather than mutating the fixture.

### 7. Cleaner Test Closure Pattern
**File:** `test_pipeline.py`
**Lines:** 274-278

**Problem:** Uses `call_count = {"n": 0}` dict closure pattern.

**Requirement:** Replace with `itertools.count()` or a simple nonlocal integer.