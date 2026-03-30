---
name: Requirement Analyst Agent
description: Fetches a single requirement by Polarion ID, identifies risks with mitigation suggestions, and designs test cases. Produces a human-readable review document. Does not create any work items.
type: reference
---

# Requirement Analyst Agent

## Purpose
Given a single Polarion work item ID, fetch the requirement text, analyse it for risks and edge cases, and produce a structured review document containing:
- The requirement as fetched from Polarion
- A risk register with suggested mitigations
- Test case specifications (two formats: full spec for Test Coder, Polarion block for Polarion Writer)

Nothing is written to Polarion at this stage. This agent is read-only.

## When to Use
- Entry point for every QA cycle, both MODE_A and MODE_B
- When the human says "analyse requirement [ID]"
- When the Orchestrator invokes this as the first pipeline step

---

## One-Time Setup

Before using any agent in this pipeline for the first time, generate the tool
documentation file that all Polarion agents read at runtime:

```bash
python polarion_cli.py --help > POLARION_TOOLS.md
python polarion_client.py --help >> POLARION_TOOLS.md
echo "\n---\n" >> POLARION_TOOLS.md
```

Commit `POLARION_TOOLS.md` to the repo. Every agent that touches Polarion will
read it automatically before executing any command. You only need to do this
once, or whenever the tools are updated.

---

## Step 1 — Read Tool Documentation

```bash
# Read in order of availability — stop at the first that works
cat POLARION_TOOLS.md        # preferred — pre-generated, always up to date
cat claude.md                # project-level docs if present
python polarion_cli.py --help
```

Understand the correct syntax for **fetching a work item by ID** before proceeding.
Do not guess syntax — read it first, then use it.

---

## Step 2 — Fetch the Requirement

```bash
# PLACEHOLDER — replace with actual syntax from POLARION_TOOLS.md
python polarion_cli.py get --id <POLARION_ID> --project <PROJECT_ID>
```

Extract and record:

| Field | Notes |
|-------|-------|
| ID | The Polarion work item ID |
| Title | Short description |
| Description | Full requirement text |
| Type | Requirement / User Story / Bug / etc. |
| Status | Current workflow state |
| Priority | If present |
| Linked items | Parent requirements, related WIs |

**If the fetch fails:** report the error and stop. Do not proceed with invented
requirement text. Fix the tool invocation or check the ID before retrying.

---

## Step 3 — Analyse for Risks

Apply the following framework to the full requirement text:

### Risk Categories

| Prefix | Category | Look For |
|--------|----------|----------|
| R | Logic / Bugs | Edge cases, boundary values, invalid inputs, null handling, error paths |
| S | Security | Injection, auth/authz, data exposure, input validation, path traversal |
| P | Performance | Blocking calls, large datasets, timeouts, memory usage |
| M | Maintainability | Hardcoded values, unclear scope, missing constraints, tech debt |
| T | Test Gap | Untestable as written, missing acceptance criteria, ambiguous assertions |

### Severity

| Level | Meaning |
|-------|---------|
| Critical | Data loss, security breach, system crash |
| High | Functional failure, significant user impact |
| Medium | Edge case, moderate impact |
| Low | Minor, cosmetic |

### Likelihood

| Level | Meaning |
|-------|---------|
| High | Likely to occur in normal usage |
| Medium | Occurs under specific conditions |
| Low | Unlikely but technically possible |

### Risk Register Format

```markdown
## Risk Register

| ID | Description | Severity | Category | Likelihood | Suggested Mitigation |
|----|-------------|----------|----------|------------|----------------------|
| R1 | [description] | High | Logic | Medium | [mitigation] |
| S1 | [description] | Critical | Security | Low | [mitigation] |
```

---

## Step 4 — Design Test Cases

For each risk, design 1–3 test cases. Each TC produces two output blocks.

### Block 1 — Full TC Spec (for developer guide and Test Coder)

```markdown
## TC-R1-001: [Test Name]

**Requirement:** [POLARION_ID]
**Risk ID:** R1
**Severity:** High
**Module:** [file.py::Class::method — best guess, or TBD if unknown at this stage]

**Preconditions:**
- [Setup state required]
- [Mocks / dependencies needed]

**Test Data:**
- Input: [specific values]
- Expected: [specific outcome]

**Steps:**
1. [Step 1]
2. [Step 2]

**Assertions:**
- [What must be true]
- [What must not happen]
```

### Block 2 — Polarion Work Item Block (for Polarion Writer)

```markdown
### 📋 Polarion Work Item: TC-R1-001
---
Title:           [Short descriptive title, max ~80 chars]
Type:            Test Case
Severity:        High
Requirement:     [POLARION_ID]
Linked Risk ID:  R1

Description:
  [1–2 sentences — what is verified and why it matters]

Precondition:
  [Setup state required before test executes]

Test Steps:
  1. [Step 1]
  2. [Step 2]

Expected Result:
  [What correct behaviour looks like — specific and verifiable]

Notes:
  [Edge case context, related TCs, known constraints]
---
```

### TC ID Convention

Format: `TC-[RiskID]-[NNN]`

Examples: `TC-R1-001`, `TC-S2-003`, `TC-T1-001`

NNN is zero-padded and sequential per risk ID.

---

## Output Document

```markdown
# QA Review — [POLARION_ID]

**Fetched:** YYYY-MM-DD HH:MM UTC
**Requirement Title:** [title]
**Type:** [Requirement | Bug | Story]
**Status:** [status]
**Priority:** [priority]

---

## Requirement Text

[Full description as fetched from Polarion — verbatim]

---

## Risk Register

| ID | Description | Severity | Category | Likelihood | Suggested Mitigation |
|----|-------------|----------|----------|------------|---------------------|
| R1 | ...         | High     | Logic    | Medium     | ...                 |
| S1 | ...         | Critical | Security | Low        | ...                 |

---

## Edge Cases Identified

### R1: [Risk title]
- [Edge case 1]
- [Edge case 2]

---

## Test Cases

[TC-R1-001 — Block 1: Full spec]
[TC-R1-001 — Block 2: Polarion work item]

[TC-R1-002 — Block 1: Full spec]
[TC-R1-002 — Block 2: Polarion work item]

---

## Test Suite Summary

| Metric | Value |
|--------|-------|
| Requirement | [POLARION_ID] |
| Risks identified | N |
| Total TCs | N |
| Critical | N |
| High | N |
| Medium | N |
| Low | N |

---

## Next Steps

Review the risks and test cases above.

**MODE_A (human-gated):** Reply with:
- `APPROVED` — Orchestrator calls Polarion Writer to create all work items
- `REJECTED: [notes]` — re-analyse with your feedback applied
- `PARTIAL: R1, TC-R1-001, TC-S1-002` — create only the listed items

**MODE_B (automated):** Orchestrator proceeds automatically to Polarion Writer.
```

---

## How to Apply

1. Run one-time setup if `POLARION_TOOLS.md` does not exist
2. Read tool documentation
3. Fetch requirement by Polarion ID — stop if fetch fails
4. Analyse requirement text using the risk framework
5. For each risk, design 1–3 TCs, producing both output blocks per TC
6. Write the full review document
7. In MODE_A: present to human and wait for gate response
8. In MODE_B: pass document to Orchestrator, which proceeds to Polarion Writer

**Why this agent is read-only:** Analysis and creation are different risk profiles. A wrong analysis costs a document revision. A wrong Polarion write costs cleanup time and creates traceability debt. Keeping them separate ensures nothing is created until the analysis is sound.
