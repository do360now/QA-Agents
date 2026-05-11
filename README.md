# QA Agents

This repository contains Claude Code agents for QA pipeline automation and system security.

## Agents

| Agent | Purpose |
|-------|---------|
| Requirement Analyst | Fetches Polarion requirements, identifies risks, designs test cases |
| Polarion Writer | Creates risk and TC work items in Polarion |
| Feature Coder | Implements feature code from requirements |
| Test Coder | Writes pytest functions from TC specs |
| Test Executor | Runs pytest, produces junit-xml + logs |
| Test Run Creator | Creates Polarion test runs, maps results |
| Orchestrator | Coordinates full QA pipeline |
| Security Agent | System security scanning, patching, hardening |

## Security Agent

The Security Agent maintains Ubuntu system security by monitoring vulnerabilities, applying patches, and enforcing system hardening.

### Make Targets

```bash
make security-scan       # Quick vulnerability check (read-only)
make security-patch      # Apply security updates only
make security-full       # Full scan + patch + hardening
make CVE=CVE-2026-1234 security-incident  # CVE-specific response
make security-autoupdate # Enable automatic security updates
make security-help       # Show help
```

### Modes

| Mode | Description |
|------|-------------|
| `scan` | Vulnerability assessment only (no changes) |
| `patch` | Apply available security updates |
| `full` | Complete scan + patch + hardening |
| `incident` | Targeted response for specific CVE |

### Invocation

```markdown
Agent: Security Agent
Mode: [scan | patch | full | incident]
System: [localhost or /path/to/target]
Target: [optional: specific package or CVE]
```

### Scheduling

```markdown
Agent: Security Agent
Schedule: daily
System: localhost
```

## Mythos Preview Context

Claude Mythos Preview can discover zero-day vulnerabilities in hours. Patch cycles should be shortened to 24-72 hours for critical CVEs. See [ubuntu-security-patching-guide.md](ubuntu-security-patching-guide.md) for details.

## Setup

```bash
# Install dependencies
sudo apt install unattended-upgrades

# Start Claude
make start_claude
```