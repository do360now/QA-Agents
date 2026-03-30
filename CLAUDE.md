# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QA-Agents is a multi-agent pipeline for automated quality assurance. It uses a state-machine orchestration pattern where specialized agents analyze code, identify risks, design tests, implement features, execute tests, and generate reports.

## Commands

```bash
# Run the pipeline
python3 main.py --scope ./my-project --model llama3

# With verbose logging
python3 main.py --scope ./my-project -v

# Resume from previous state
python3 main.py --scope ./my-project --resume-from .pipeline_state/run-123.json

# Run tests
pytest test_pipeline.py

# Run a single test
pytest test_pipeline.py::TestOrchestratorHappyPath::test_run_completes_all_phases

# Start ollama with gemma3 model
make start_gemma3

# Start ollama with minimax model
make start_minimax
```

## Architecture

### Pipeline Phases

The orchestrator runs through ordered phases:
1. **ANALYSIS** — Analyst reads codebase, builds snapshot, derives requirements
2. **RISK** — Risk Analyst identifies bugs, security issues, coverage gaps
3. **TEST_DESIGN** — Test Designer creates test case specs
4. **TEST_CODE** — Test Coder writes pytest code
5. **FEATURE_CODE** — Feature Implementer makes tests pass (TDD)
6. **EXECUTION** — Test Executor runs the suite
7. **REPORTING** — Reporter generates markdown report

### Central State Object

`PipelineState` in `pipeline_state.py` is the single source of truth. All agents communicate through it — never directly to each other. Agents:
- Read artifacts from `state.get_artifact(key)`
- Write outputs via `state.set_artifact(key, value)`
- Record non-fatal errors via `state.record_error()`
- Raise `FeedbackEvent` during execution for test failures

### Orchestrator Pattern

`orchestrator.py` contains the `Orchestrator` class that:
- Manages phase sequencing and transition validation
- Implements retry policy (default: 3 retries per phase)
- Routes feedback from test failures back to appropriate phases:
  - `test_bug` → rewind to TEST_CODE
  - `feature_bug` → rewind to FEATURE_CODE
  - `new_risk` → rewind to RISK
- Persists state after each phase for resumability

### Agent Interface

All agents inherit from `BaseAgent` (`agents/base.py`) and implement:
```python
def _execute(self, state: PipelineState) -> None:
    """Override in subclasses to implement agent logic."""
```

Agents are injected at Orchestrator construction time (dependency injection), enabling testability with mocks.

### LLM Client

`llm_client.py` provides a unified LLM client supporting:
- `OllamaClient` — local models (default)
- `AnthropicClient` — Claude API
- `OpenAIClient` — OpenAI API

Factory function: `create_llm_client(provider, model, api_key, base_url)`

### Artifact Keys

Each phase produces specific artifacts identified by `ArtifactKey` enum:
- `CODEBASE_SNAPSHOT`, `REQUIREMENTS` (ANALYSIS)
- `RISK_REGISTER` (RISK)
- `TEST_SUITE_MANIFEST` (TEST_DESIGN)
- `TEST_FILE_PATH` (TEST_CODE)
- `FEATURE_FILES` (FEATURE_CODE)
- `EXECUTION_REPORT` (EXECUTION)
- `REPORT_PATH` (REPORTING)

## Agent Implementations

| Agent | File | Description |
|-------|------|-------------|
| Analyst | `agents/analyst.py` | Codebase analysis and requirements derivation |
| RiskAnalyst | `agents/risk_analyst.py` | Risk identification and classification |
| TestDesigner | `agents/test_designer.py` | Test case specification |
| TestCoder | `agents/test_coder.py` | Pytest code generation |
| FeatureImplementer | `agents/feature_implementer.py` | TDD feature implementation |
| TestExecutor | `agents/test_executor.py` | Test suite execution |
| Reporter | `agents/reporter.py` | Report generation |

## Prompt Templates

System prompts are stored in `prompts/*.txt` and can be loaded via `load_prompt(name)` from `agents/base.py`.

## Output Directories

- `.pipeline_state/` — Persisted pipeline state
- `reports/` — Generated QA reports
- `tests/` — Generated test files