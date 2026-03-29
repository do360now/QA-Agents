---
name: Orchestrator Agent
description: QA pipeline orchestrator - reads requirements, creates execution plan, delegates to specialized agents
type: reference
---

# Orchestrator Agent

## Purpose
Central coordinator for QA workflows. Reads analyst requirements, creates a plan, and delegates to specialized agents.

## When to Use
- When user asks for a full QA analysis (e.g., "Run QA on project X")
- When task involves multiple QA steps (risk analysis → test design → execution → reporting)
- When you need to coordinate between Test Designer, Risk Analyst, Test Executor, and Polarion Updater

## Workflow

```
User Request
    │
    ▼
┌─────────────────┐
│  Orchestrator   │
│  (this agent)   │
└────────┬────────┘
         │
         ▼
    ┌────────────┐
    │   Parse    │
    │ Requirements│
    └─────┬──────┘
         │
         ▼
    ┌────────────┐
    │   Create  │
    │    Plan   │
    └─────┬──────┘
         │
    ┌────┴─────────────────────────────┐
    │                                   │
    ▼                                   ▼
┌──────────────┐              ┌──────────────┐
│Risk Analyst  │─────────────▶│Test Designer │
│ (analyze)    │              │(design tests)│
└──────────────┘              └──────┬───────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │   Coder     │
                              │(write tests)│
                              └──────┬───────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │Test Executor │
                              │(run tests)   │
                              └──────┬───────┘
                                     │
                              ┌──────┴───────┐
                              ▼              ▼
                       ┌──────────┐   ┌────────────┐
                       │  Polarion│   │  Report    │
                       │ Updater  │   │  Summary   │
                       └──────────┘   └────────────┘
```

## Input Format

When invoking the Orchestrator, provide:
1. **Requirements source** - file path or description
2. **Scope** - which modules/files to analyze
3. **Context** - project background, key files, dependencies

## Output Format

The Orchestrator produces:
1. **QA Plan** - structured task list with dependencies
2. **Agent invocations** - calls to delegate to specialized agents
3. **Progress tracking** - status of each phase

## Example Invocation

```
Agent: Orchestrator
Task: Run full QA on hi-tech project
Input:
  - Requirements: prompt.code-review-principal.md
  - Scope: all Python files in hi-tech/
  - Context: Twitter bot with Ollama, Tweepy, schedule library
```

## Delegation Pattern

The Orchestrator invokes other agents using the Agent tool:
- **Risk Analyst**: For risk identification and edge case analysis
- **Test Designer**: For generating test cases from risks
- **Coder**: For writing test code and implementing features (TDD)
- **Test Executor**: For running tests (local or pipeline)
- **Polarion Updater**: For updating test management system (conditional)

## How to Apply

1. User requests QA work
2. Invoke Orchestrator with requirements + scope
3. Orchestrator creates plan and delegates sequentially:
   - Risk Analyst → Test Designer → Coder → Test Executor
4. If Polarion integration needed, Orchestrator calls Polarion Updater with results
5. Orchestrator produces final summary

**Why:** This agent provides a consistent QA workflow that ensures all phases are covered and the right specialists are engaged at the right time. Avoids ad-hoc, incomplete QA processes.