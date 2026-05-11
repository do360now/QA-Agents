# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────

start_minimax2.7:
	ollama launch claude --model minimax-m2.7:cloud

update_ollama:
	curl -fsSL https://ollama.com/install.sh | sh
	ollama pull gemma3:4b

# ─────────────────────────────────────────────
# Security Agent
# ─────────────────────────────────────────────

# Full security scan + patch + hardening
security-full:
	@echo "Running full security scan + patch + hardening..."
	@echo "Agent: Security Agent" > /tmp/security-input.md
	@echo "Mode: full" >> /tmp/security-input.md
	@echo "System: localhost" >> /tmp/security-input.md
	@cat /tmp/security-input.md

# Quick vulnerability check (read-only)
security-scan:
	@echo "Running security scan (read-only)..."
	@echo "Agent: Security Agent" > /tmp/security-input.md
	@echo "Mode: scan" >> /tmp/security-input.md
	@echo "System: localhost" >> /tmp/security-input.md
	@cat /tmp/security-input.md

# Apply security updates only
security-patch:
	@echo "Applying security updates..."
	@echo "Agent: Security Agent" > /tmp/security-input.md
	@echo "Mode: patch" >> /tmp/security-input.md
	@echo "System: localhost" >> /tmp/security-input.md
	@cat /tmp/security-input.md

# Response to specific CVE (set CVE=)
security-incident:
	@echo "Running security incident response for $(CVE)..."
	@echo "Agent: Security Agent" > /tmp/security-input.md
	@echo "Mode: incident" >> /tmp/security-input.md
	@echo "System: localhost" >> /tmp/security-input.md
	@echo "Target: $(CVE)" >> /tmp/security-input.md
	@cat /tmp/security-input.md

# Enable automatic security updates
security-autoupdate:
	@echo "Enabling automatic security updates..."
	sudo apt install -y unattended-upgrades
	echo 'APT::Periodic::Update-Package-Lists "1"; APT::Periodic::Download-Upgradeable-Packages "1"; APT::Periodic::AutocleanInterval "7"; APT::Periodic::Unattended-Upgrade "1";' | sudo tee /etc/apt/apt.conf.d/10periodic

# Show help
security-help:
	@echo "Security Agent Make Targets:"
	@echo ""
	@echo "  make security-scan       - Quick vulnerability check (read-only)"
	@echo "  make security-patch      - Apply security updates only"
	@echo "  make security-full       - Full scan + patch + hardening"
	@echo "  make security-incident  - CVE-specific response (set CVE=...)"
	@echo "  make security-autoupdate - Enable automatic security updates"
	@echo "  make security-help       - Show this help"
	@echo ""
	@echo "Examples:"
	@echo "  make security-full"
	@echo "  make CVE=CVE-2026-1234 security-incident"

security-upgrade:
	sudo apt-get update && sudo apt-get upgrade -y
	sudo sysctl -w kernel.core_pattern=/dev/null
	sudo ufw --force enable
	