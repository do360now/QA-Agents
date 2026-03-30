---
name: Orchestrator Agent
description: QA pipeline state machine — owns phase sequencing, retry policy, feedback routing, and resumability
type: reference
---

# Orchestrator Agent

## Purpose
Runs the QA pipeline as a resumable state machine. The only module that knows
about phase ordering, retry policy, and feedback-driven rewinds. All other
agents are stateless — they receive a `PipelineState`, mutate artifacts, and
return. The Orchestrator hides all coordination complexity behind a single call.

```python
state = orchestrator.run(scope="hi-tech/")
```

## What It Hides

Every other module is spared from knowing about:
- Phase sequencing and legal transition rules
- Retry budget management (per-phase, not per-run)
- The distinction between fatal exceptions and non-fatal recorded errors
- Feedback-driven rewinds (which failure type routes to which phase)
- State persistence after every successful phase transition
- Resume logic when a previous run was interrupted

## Pipeline Phases

Phases execute in this fixed order. The Orchestrator owns this sequence — no
agent may advance the phase directly.

```
INIT → ANALYSIS → RISK → TEST_DESIGN → TEST_CODE → FEATURE_CODE → EXECUTION → REPORTING → DONE
                                                          ▲               │
                                                          └───────────────┘
                                                        feedback rewind loop
```

| Phase | Agent | Produces |
|-------|-------|----------|
| ANALYSIS | Analyst | `codebase_snapshot`, `requirements` |
| RISK | Risk Analyst | `risk_register` |
| TEST_DESIGN | Test Designer | `test_suite_manifest` |
| TEST_CODE | Test Coder | `test_file_path` |
| FEATURE_CODE | Feature Implementer | `feature_files` |
| EXECUTION | Test Executor | `execution_report` + optional `FeedbackEvent`s |
| REPORTING | Reporter | `report_path` |

## Feedback Routing

When Test Executor adds `FeedbackEvent`s to `PipelineState`, the Orchestrator
routes them by priority before advancing. Higher rewinds subsume lower ones.

| `failure_type` | Rewinds to | Meaning |
|----------------|------------|---------|
| `new_risk` | `RISK` | Test revealed an undiscovered risk — re-analyse |
| `feature_bug` | `FEATURE_CODE` | Implementation is wrong — fix the code |
| `test_bug` | `TEST_CODE` | Test itself is broken — fix the test |

Priority order: `new_risk` > `feature_bug` > `test_bug`. If a run produces
multiple feedback types, only the highest-priority rewind fires. Lower-priority
events are discarded — they will be re-evaluated after the higher rewind
completes.

## Retry Policy

Each phase has its own retry budget, reset on every successful phase transition.

- Agent raises exception → `retry_count` incremented, phase re-runs
- Agent calls `state.record_error()` → same retry path (non-fatal)
- `retry_count > max_retries` → `state.mark_failed()`, pipeline stops
- Default `max_retries`: 3

Retries are logged with attempt number. After exhaustion, `state.summary()`
contains the full error history for diagnosis.

## State Persistence

After every successful phase transition, the Orchestrator serialises
`PipelineState` to `.pipeline_state/{run_id}.json`. This enables:

```bash
# Resume an interrupted run from the last successful phase
python main.py --scope hi-tech/ --resume .pipeline_state/run-1774813299.json
```

Persistence failure is non-fatal — the pipeline continues, but resumability
is lost for that run.

## Agent Protocol

Every agent satisfies this protocol. The Orchestrator injects agents at
construction time (dependency injection), making it testable with mocks.

```python
class Agent(Protocol):
    name: str
    def run(self, state: PipelineState) -> None: ...
```

Agents must:
- Read inputs from `state.get_artifact(ArtifactKey.X)`
- Write outputs via `state.set_artifact(ArtifactKey.X, value)`
- Log non-fatal issues via `state.record_error("message")`
- Add feedback via `state.add_feedback(FeedbackEvent(...))`
- **Never** call `state.advance()` — that is exclusively the Orchestrator's right
- Raise an exception only for unrecoverable errors

## Entry Point

```python
# main.py
orc = Orchestrator(
    analyst=AnalystAgent(model="ollama/qwen2.5-coder:7b"),
    risk_analyst=RiskAnalystAgent(model="ollama/qwen2.5-coder:7b"),
    test_designer=TestDesignerAgent(model="ollama/qwen2.5-coder:7b"),
    test_coder=TestCoderAgent(model="ollama/qwen2.5-coder:7b"),
    feature_implementer=FeatureImplementerAgent(model="ollama/qwen2.5-coder:7b"),
    test_executor=TestExecutorAgent(),       # no LLM — runs pytest directly
    reporter=ReporterAgent(backend="local"), # or backend="polarion"
    state_dir=Path(".pipeline_state"),
    max_retries=3,
)

state = orc.run(scope="hi-tech/")
# or
state = orc.run(scope="hi-tech/", resume_from=Path(".pipeline_state/run-xyz.json"))
```

## Output

`orchestrator.run()` always returns the final `PipelineState`. Inspect
`state.phase` to determine outcome.

```python
if state.phase == Phase.DONE:
    print(f"Report: {state.get_artifact(ArtifactKey.REPORT_PATH)}")
else:
    # Phase.FAILED — human intervention required
    print(state.summary())
```

`state.summary()` prints:

```
Run:     run-1774813299
Scope:   hi-tech/
Phase:   FAILED
Retries: 3/3
Artifacts produced: ['codebase_snapshot', 'requirements', 'risk_register']
Pending feedback:   0
Errors logged:      4
--- Errors ---
  [RISK] Model returned malformed JSON on attempt 1
  [RISK] Model returned malformed JSON on attempt 2
  [FATAL] Phase RISK exceeded 3 retries.
```

## Implementation Reference

- `pipeline_state.py` — `PipelineState`, `Phase`, `ArtifactKey`, `FeedbackEvent`
- `orchestrator.py` — `Orchestrator`, `Agent` protocol, `FEEDBACK_ROUTING`
- `test_pipeline.py` — 29 tests covering all behaviours above

**Why:** The Orchestrator earns its existence by hiding genuinely complex state
machine logic. Agents stay simple and stateless. The pipeline is resumable,
debuggable, and testable with mocks at every seam.
