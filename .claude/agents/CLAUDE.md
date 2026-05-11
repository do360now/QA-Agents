# CLAUDE.md — QA Multi-Agent Pipeline

**Context: The Mythos Era (April 2026)**

Claude Mythos Preview represents a watershed moment for security. Frontier AI models can now autonomously find and exploit zero-day vulnerabilities at scale. This QA pipeline is designed to help defenders respond rapidly — matching the pace of AI-capable adversaries while preserving rigor in requirement traceability, risk identification, and test coverage.

---

## Mission

This directory implements a multi-agent QA pipeline that operates in two complementary modes, both converging on the same deliverables: Polarion work items (REQ + TC), a passing/failing pytest suite, a Polarion test run, a `tc_wi_mapping.csv` traceability matrix, and an executive QA report.

- **MODE_A — Requirement-driven** (forward path)
  Start from a Polarion requirement. Analyze it, derive a risk register, generate mitigating test cases, optionally implement the feature, write and execute pytest, then produce a traceable QA report and update all affected documentation.

- **MODE_B — Code-driven** (reverse path)
  Start from a codebase change (commit range, branch, module). Reverse-engineer the implicit requirements, identify risks and coverage gaps, generate test cases, back-fill Polarion work items, execute tests, and produce the same QA report.

Mode selection is the `orchestrator`'s first decision. Hybrid runs (e.g. a change touches an existing REQ and introduces undeclared behaviour) run MODE_A on the declared slice and MODE_B on the residual.

---

## The advisor pattern

These agents implement the **advisor pattern**: a fast executor handles most of the work, and a stronger advisor is consulted at strategic moments for plans and course corrections. Inspired by Anthropic's advisor tool (https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool): pair a faster executor with a higher-intelligence advisor that reads the full context and produces concise guidance (target: under 100 words, enumerated steps).

**When the executor calls the advisor:**
1. **Early** — after orientation (file reads, listing commands) but *before* substantive work. In QA, this means: after reading the requirement / diff, before committing to a risk model or test plan.
2. **When stuck** — recurring errors, non-converging test outcomes, contradictions between requirement text and observed behaviour.
3. **Before declaring done** — after writes and test output are in transcript. Make the deliverable durable first (file written, test run recorded, Polarion updated) so a timeout mid-advice doesn't lose work.

**How the executor treats advice:** follow it unless empirical evidence contradicts a specific claim. A passing self-test is not evidence the advice is wrong. If your evidence conflicts with advice, do one reconcile call rather than silently switching.

## How to invoke the advisor

Shell out via Bash, using the Claude Code CLI in non-interactive print mode:

```bash
claude -p --model <advisor-model> "$(cat <<'EOF'
You are a [role] advisor. The executor has context below.
Respond in under 100 words using enumerated steps, not explanations.

<task>
[current task]
</task>

<transcript>
[what the executor has found so far — file paths, errors, partial output]
</transcript>

What should the executor do next?
EOF
)"
```

For long transcripts, pipe via stdin: `claude -p --model <advisor-model> < prompt.txt`.

Alternatively, advisor calls can be made via the Anthropic SDK (Python/Node) against the Claude API — use the same model IDs.

---

## Claude model family

| Model | ID | Role |
|-------|----|------|
| Opus 4.7 | `claude-opus-4-7` | Flagship — deepest reasoning, long-context (1M tokens) |
| Opus 4.6 | `claude-opus-4-6` | Strong reasoning |
| Sonnet 4.6 | `claude-sonnet-4-6` | Balanced — default for executors |
| Haiku 4.5 | `claude-haiku-4-5` | Fast/cheap — lightweight executors |

---

## Agents

| Agent | Executor | Advisor | Responsibility |
|-------|----------|---------|----------------|
| `orchestrator` | `claude-sonnet-4-6` | `claude-opus-4-7` | Mode selection (A/B/hybrid), pipeline routing, gate enforcement |
| `requirement-analyst` | `claude-sonnet-4-6` | `claude-opus-4-7` | Parses REQ; produces risk register and candidate TC set |
| `code-analyst` | `claude-sonnet-4-6` | `claude-opus-4-7` | MODE_B only — reverse-engineers REQs from diffs and module structure |
| `polarion-writer` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Creates/updates REQ + TC work items; maintains `tc_wi_mapping.csv`; duplicate-checks before insert |
| `feature-coder` | `claude-sonnet-4-6` | `claude-opus-4-7` | Implements the requirement under test (MODE_A only); minimal, architecture-respecting |
| `test-coder` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Generates pytest files; embeds TC-ID in function names |
| `test-executor` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Runs pytest; emits JUnit XML + coverage; classifies failures |
| `test-run-creator` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Creates Polarion test run; attaches evidence; flips TC statuses |
| `report-writer` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Produces `qa_report.md`; updates `README.md`, `CHANGELOG.md`, and affected ADRs |
| `security-agent` | `claude-sonnet-4-6` | `claude-opus-4-7` | Threat-model overlay, SAST/SCA scan, hardening recommendations |

**Rationale**: Analysis-heavy stages (orchestrator, requirement-analyst, code-analyst, feature-coder, security-agent) pair Sonnet 4.6 execution with Opus 4.7 advisory review — the strongest available reasoning at decision points. Write-focused agents (polarion-writer, test-coder, test-executor, test-run-creator, report-writer) use Sonnet 4.6 for both executor and advisor since the tasks are more mechanical.

---

## Pipeline stages

### MODE_A — Requirement-driven

```
requirement-analyst → polarion-writer → feature-coder* → test-coder → test-executor → test-run-creator → report-writer
                                     ↘ security-agent (parallel) ↗
```
*`feature-coder` runs only when implementation is requested; analysis-only runs skip it.*

1. **Analyze** — `requirement-analyst` reads the Polarion REQ, produces a **risk register** (likelihood × impact × category), and proposes candidate test cases, each linked to the risk(s) it mitigates. Unmitigatable risks are flagged as residual.
2. **Record** — `polarion-writer` creates/updates TC work items, links them to the parent REQ, and appends rows to `tc_wi_mapping.csv`. Before insert, it duplicate-checks by hashed title + REQ-ID to avoid TC bloat across re-runs.
3. **Implement** *(optional)* — `feature-coder` produces a minimal implementation that satisfies the REQ; no scope creep, no speculative generality.
4. **Codify tests** — `test-coder` writes pytest files. Each test function name embeds its TC-ID, e.g. `test_TC_1234_login_rejects_expired_token`. Parametrized cases keep the same TC-ID prefix.
5. **Execute** — `test-executor` runs pytest, emits JUnit XML + coverage report, classifies failures (`assertion` / `error` / `flake` / `env`), and quarantines flakes for a second pass before reporting.
6. **Record run** — `test-run-creator` creates a Polarion test run, attaches JUnit XML and logs, and flips TC statuses (`passed` / `failed` / `blocked`) against `tc_wi_mapping.csv`.
7. **Report** — `report-writer` produces `qa_report.md`, updates `README.md` and `CHANGELOG.md`, touches any affected ADRs, and summarizes coverage delta vs. the previous baseline.

### MODE_B — Code-driven

```
code-analyst → requirement-analyst → polarion-writer → test-coder → test-executor → test-run-creator → report-writer
```

1. **Reverse-engineer** — `code-analyst` inspects the diff / target module and produces draft REQ statements in given/when/then form, flagging behaviours that have no corresponding Polarion REQ.
2. **Analyze** — `requirement-analyst` enriches drafts with risks and candidate test cases, identifying coverage gaps against existing tests.
3. **Back-fill** — `polarion-writer` creates the missing REQs (linked back to the commit/PR) before creating TCs, preserving traceability.
4. Downstream stages (4–7) are identical to MODE_A.

`feature-coder` is skipped — the code already exists. If the analyst pair identifies required code changes (e.g. missing input validation), those are filed as new MODE_A work items, not patched inline.

---

## Deliverables and artifacts

| Artifact | Producer | Purpose |
|----------|----------|---------|
| `tc_wi_mapping.csv` | `polarion-writer`, `test-run-creator` | Authoritative TC ↔ WI traceability. Columns: `tc_id, wi_id, requirement_id, test_file, test_function, created_at, last_run, last_status`. |
| `risk_register.md` | `requirement-analyst` | Per-feature risk catalogue with likelihood, impact, mitigating TC-IDs, and residual risks. |
| `artifacts/<run-id>/junit.xml` | `test-executor` | Machine-readable test results consumed by `test-run-creator`. |
| `artifacts/<run-id>/coverage/` | `test-executor` | HTML + `coverage.xml` for delta analysis. |
| `qa_report.md` | `report-writer` | Executive summary: scope, mode (A/B), risks covered, pass/fail counts, coverage delta, residual risks, security findings, Polarion links. |
| `docs/README.md`, `docs/CHANGELOG.md`, `docs/adr/*` | `report-writer` | Updated when observable behaviour changes. |

---

## Gate rules (orchestrator-enforced)

These gates block pipeline progression when violated. Violations require explicit override with justification logged to the run transcript.

- **Traceability gate** — no code change ships without at least one TC linked to a REQ in `tc_wi_mapping.csv`.
- **TC-ID embedding** — `test-coder` MUST embed TC-ID in the function name; `test-executor` MUST extract TC-IDs from the JUnit XML and reconcile against `tc_wi_mapping.csv` — mismatches block `test-run-creator`.
- **No-duplicate gate** — `polarion-writer` refuses to create a TC when a hash collision on `(REQ-ID, normalized_title)` exists; it updates the existing TC instead.
- **Green-report gate** — if `test-executor` reports any failure, `report-writer` cannot mark the run as "green"; a residual-risk section is mandatory.
- **Security gate** — `security-agent` findings at severity HIGH or CRITICAL block report finalization until acknowledged or mitigated, and are carried into the report's residual-risk section.
- **Flake gate** — a test classified as `flake` on first pass but `passed` on quarantine pass is reported but does not block; three consecutive flake classifications quarantine the TC and raise a new REQ for investigation.

---

## Invocation

```
Agent(
  description: "Analyse requirement POLARION-1234",
  subagent_type: "requirement-analyst",
  prompt: "Analyze requirement POLARION-1234 for the Authentication project."
)
```

For MODE_B entry:

```
Agent(
  description: "Reverse-engineer REQs from PR #482",
  subagent_type: "orchestrator",
  prompt: "Run MODE_B on branch feature/session-renewal against main. Target module: src/auth/session.py."
)
```

---

## Adding new agents

Frontmatter contract:

```yaml
---
name: my-agent
description: One-line purpose (shown in agent picker)
mode: [A, B]           # which pipeline modes the agent participates in
executor: claude-sonnet-4-6
advisor: claude-opus-4-7
integrity-hash-sha256: SHA256:<hash>
tools:
  - name: Bash
  - name: Read
---

# My Agent

[agent description and workflow]
```

Every new agent must document:
1. Its preconditions (what must exist in the run state before it runs).
2. Its postconditions (what it writes to `tc_wi_mapping.csv`, `artifacts/`, or Polarion).
3. Which gate rules its output feeds.

---

## Advisor Output Validation

Before acting on any advisor output, run it through the validation checklist in `ADVISOR_OUTPUT_CONTRACT.md`. The executor is responsible for rejecting any advisor response that violates the contract — in particular, advice that invents TC-IDs, REQ-IDs, or file paths not present in the transcript must be discarded and re-requested with a clarifying prompt.