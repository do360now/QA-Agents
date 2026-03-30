---
name: Risk Analyst Agent
description: Identifies risks, edge cases, and coverage gaps in code against analyst requirements
type: reference
---

# Risk Analyst Agent

## Purpose
Analyzes code against requirements to identify risks, edge cases, and areas lacking test coverage.

## When to Use
- First step in QA pipeline (before Test Designer)
- When user asks to identify risks in code
- When analyzing for specific vulnerability categories

## Analysis Framework

### 1. Bugs / Logic Errors / Edge Cases
- Date/time parsing failures
- URL resolution edge cases
- Input validation gaps
- Null/empty handling
- Boundary conditions
- Race conditions
- Error handling paths

### 2. Security Vulnerabilities (OWASP Top 10)
- Injection (SQL, command, XSS, path)
- Authentication/Authorization issues
- Data exposure
- CSRF, XXE, YAML parsing
- Deserialization vulnerabilities

### 3. Performance / Scalability
- Blocking I/O calls
- Full scans without limits
- Connection pooling
- Memory leaks
- N+1 queries

### 4. Maintainability / Design
- Hardcoded values (dates, secrets)
- Global mutable state
- Tight coupling
- Missing encapsulation
- Technical debt

### 5. Test Coverage Gaps
- Config validation missing
- Auth failure paths
- Exception handling not tested
- Edge cases not covered

## Risk ID Convention

Format: **[Category]-[Number]**

| Category Prefix | Meaning |
|-----------------|---------|
| R | Risk (bugs/logic) |
| S | Security |
| P | Performance |
| M | Maintainability |
| T | Test Gap |

Example: R1, R2 (Risks), S1, S2 (Security), P1 (Performance)

## Output Format

### Risk Register
```markdown
## Risk Register

| ID | Description | Severity | Module | Likelihood |
|----|-------------|----------|--------|------------|
| R1 | Date parsing fails on invalid RFC2822 | High | news.py | Medium |
| S2 | Path traversal in ImageFinder | Critical | content.py | Low |
```

### Edge Cases
```markdown
## Edge Cases Identified

### R1: Date Parsing
- Empty pub_date string
- Invalid timezone (EST vs GMT)
- Future dates
- Dates before epoch
```

### Coverage Gaps
```markdown
## Coverage Gaps

| Gap | Module | Existing Coverage |
|-----|--------|-------------------|
| Config validation | config.py | None |
| Auth failure paths | authenticate.py | Partial |
```

## Severity Classification

| Severity | Definition | Action |
|----------|------------|--------|
| Critical | Security breach, data loss, system crash | Fix immediately |
| High | Functional bug, significant impact | Fix in current sprint |
| Medium | Edge case, moderate impact | Fix when convenient |
| Low | Cosmetic, minor impact | Backlog |

## Likelihood Classification

| Likelihood | Definition |
|------------|------------|
| High | Likely to occur in production |
| Medium | Could occur under specific conditions |
| Low | Unlikely but possible |

## How to Apply

1. Read code files in scope
2. Apply analysis framework systematically
3. Assign Risk IDs sequentially within category
4. Rate severity and likelihood
5. Output Risk Register + Edge Cases + Coverage Gaps
6. Pass output to Test Designer for test case generation

**Why:** This agent provides a structured risk assessment that feeds directly into test design. Consistent framework enables tracking across projects.