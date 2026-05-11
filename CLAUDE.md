# QA Agents — Project Context

This project contains Claude Code agents for QA pipeline automation and a Security Agent for system hardening.

## Advisory Pattern

All agents in this project use the **advisor pattern**: a fast executor (Sonnet 4.6) handles work, and a stronger advisor (Opus 4.7 or Sonnet 4.6) is consulted at key decision points.

See `.claude/agents/CLAUDE.md` for the full advisory pattern documentation and `ADVISOR_OUTPUT_CONTRACT.md` for the validation contract.

## QA Pipeline Agents

See `.claude/agents/CLAUDE.md` for the full agent inventory and invocation instructions.

## Security Agent Usage

The Security Agent is defined in `.claude/agents/security_agent.md`.

### Invoke via Agent tool

```markdown
Agent: Security Agent
Mode: [scan | patch | full | incident]
System: [localhost or /path/to/target]
Target: [optional: CVE or package]
```

### Invoke via Make

```bash
make security-scan           # Quick vulnerability check (read-only)
make security-patch          # Apply security updates
make security-full           # Full scan + patch + hardening
make CVE=CVE-2026-1234 security-incident  # CVE response
make security-autoupdate     # Enable auto-updates
make security-help           # Show available targets
```

## Key Files

- `.claude/agents/security_agent.md` — Security Agent definition
- `ubuntu-security-patching-guide.md` — System patching procedures
- `Makefile` — Security make targets

## Mythos Precaution

Claude Mythos Preview can find zero-day vulnerabilities in hours. Patch cycles should be shortened to 24-72 hours. The Security Agent prioritizes rapid CVE response.