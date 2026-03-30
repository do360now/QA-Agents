# QA-Agents

A multi-agent pipeline for automated quality assurance. Uses a state-machine orchestration pattern where specialized agents analyze code, identify risks, design tests, implement features, execute tests, and generate reports.

## Quick Start

```bash
# Run the pipeline on a codebase
python3 main.py --scope ./my-project --model llama3

# With verbose logging
python3 main.py --scope ./my-project -v

# Resume from a previous run
python3 main.py --scope ./my-project --resume-from .pipeline_state/run-123.json
```

## Requirements

- Python 3.12+
- `requests` library (`pip install requests`)
- An LLM provider (Ollama, Anthropic, or OpenAI)

## Installation

```bash
pip install requests
```

## LLM Setup

### Ollama (local models)

```bash
# Install Ollama, then:
make start_gemma3  # or make start_minimax

# Or manually:
ollama serve
ollama pull llama3
```

### Cloud Providers

```bash
# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."

# Run with cloud provider
python3 main.py --scope ./my-project --provider anthropic --model claude-3-opus-20240229
```

## Commands

```bash
# Run tests
pytest test_pipeline.py

# Run a single test
pytest test_pipeline.py::TestOrchestratorHappyPath::test_run_completes_all_phases
```

## Architecture

### Pipeline Phases

1. **ANALYSIS** — Analyst reads codebase, builds snapshot, derives requirements
2. **RISK** — Risk Analyst identifies bugs, security issues, coverage gaps
3. **TEST_DESIGN** — Test Designer creates test case specs
4. **TEST_CODE** — Test Coder writes pytest code
5. **FEATURE_CODE** — Feature Implementer makes tests pass (TDD)
6. **EXECUTION** — Test Executor runs the suite
7. **REPORTING** — Reporter generates markdown report

### Key Files

| File | Description |
|------|-------------|
| `orchestrator.py` | Pipeline orchestration and state machine |
| `pipeline_state.py` | Central state object and phase definitions |
| `llm_client.py` | LLM client (Ollama, Anthropic, OpenAI) |
| `agents/` | Agent implementations |
| `main.py` | CLI entry point |

### Output

- `.pipeline_state/` — Persisted pipeline state for resumability
- `reports/` — Generated QA reports in markdown
- `tests/` — Generated pytest test files