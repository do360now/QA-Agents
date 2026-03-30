"""
agents/risk_analyst.py
----------------------
Risk Analyst Agent - identifies risks, edge cases, and coverage gaps.
"""

from __future__ import annotations

import json

from .base import BaseAgent
from pipeline_state import ArtifactKey, PipelineState


SYSTEM_PROMPT = """You are a risk analyst. Analyze code against requirements to identify risks, edge cases, and test coverage gaps.

Respond ONLY in JSON. No explanations."""


class RiskAnalystAgent(BaseAgent):
    """
    Analyzes code against requirements to identify risks.

    Produces:
    - RISK_REGISTER: list of identified risks with severity and likelihood
    """

    name = "RiskAnalyst"

    def _execute(self, state: PipelineState) -> None:
        # Get inputs
        snapshot = state.get_artifact(ArtifactKey.CODEBASE_SNAPSHOT)
        requirements = state.get_artifact(ArtifactKey.REQUIREMENTS)

        # Analyze for risks
        risks = self._analyze_risks(snapshot, requirements)

        state.set_artifact(ArtifactKey.RISK_REGISTER, risks)
        self.log_summary(f"Identified {len(risks)} risks")

    def _analyze_risks(self, snapshot: dict, requirements: list) -> list[dict]:
        """Analyze codebase for risks."""
        prompt = f"""Analyze this codebase for risks, bugs, security issues, and test coverage gaps.

Codebase snapshot:
{json.dumps(snapshot, indent=2)}

Requirements:
{json.dumps(requirements, indent=2)}

Categories to check:
1. Bugs / Logic Errors - date parsing, null handling, edge cases
2. Security - injection, auth, path traversal
3. Performance - blocking I/O, full scans, memory
4. Maintainability - hardcoded values, global state
5. Test Coverage Gaps - missing test paths

Return JSON with this schema:
[
  {{
    "id": "R1",
    "description": "risk description",
    "severity": "Critical|High|Medium|Low",
    "likelihood": "High|Medium|Low",
    "module": "file.py",
    "category": "Bugs|Security|Performance|Maintainability|TestGap"
  }}
]

Generate at least 5 risks across different categories. Use IDs: R1, R2 (bugs), S1, S2 (security), P1 (performance), M1 (maintainability), T1 (test gap)."""

        try:
            result = self.call_llm_json(SYSTEM_PROMPT, prompt)
            if isinstance(result, list):
                return result
        except Exception as exc:
            self._logger.warning("LLM risk analysis failed: %s", exc)

        # Fallback
        return [
            {
                "id": "R1",
                "description": "Error handling should be reviewed",
                "severity": "Medium",
                "likelihood": "Medium",
                "module": "General",
                "category": "TestGap",
            }
        ]