"""
agents/test_designer.py
-----------------------
Test Designer Agent - generates test case specifications.
"""

from __future__ import annotations

import json

from .base import BaseAgent
from pipeline_state import ArtifactKey, PipelineState


SYSTEM_PROMPT = """You are a test designer. Transform risks into actionable test cases with clear preconditions, actions, and assertions.

Respond ONLY in JSON. No explanations."""


class TestDesignerAgent(BaseAgent):
    """
    Transforms risks into test case specifications.

    Produces:
    - TEST_SUITE_MANIFEST: list of test cases with preconditions, actions, assertions
    """

    name = "TestDesigner"

    def _execute(self, state: PipelineState) -> None:
        risk_register = state.get_artifact(ArtifactKey.RISK_REGISTER)

        # Design test cases
        test_cases = self._design_tests(risk_register)

        state.set_artifact(ArtifactKey.TEST_SUITE_MANIFEST, test_cases)
        self.log_summary(f"Designed {len(test_cases)} test cases")

    def _design_tests(self, risks: list[dict]) -> list[dict]:
        """Design test cases from risks."""
        prompt = f"""Design test cases for these risks:

{json.dumps(risks, indent=2)}

For each risk, design 1-3 test cases. Return JSON with this schema:
[
  {{
    "id": "TC-R1-001",
    "name": "test name",
    "risk_id": "R1",
    "severity": "Critical|High|Medium|Low",
    "module": "file.py",
    "preconditions": ["mock setup", "environment state"],
    "actions": ["step 1", "step 2"],
    "assertions": ["expected result 1", "expected result 2"],
    "postconditions": ["cleanup needed"]
  }}
]

Make each test:
- Independent (can run alone)
- Repeatable (same input -> same output)
- Clear preconditions and assertions"""

        try:
            result = self.call_llm_json(SYSTEM_PROMPT, prompt)
            if isinstance(result, list):
                return result
        except Exception as exc:
            self._logger.warning("LLM test design failed: %s", exc)

        # Fallback
        return [
            {
                "id": "TC-R1-001",
                "name": "test placeholder",
                "risk_id": "R1",
                "severity": "Medium",
                "module": "General",
                "preconditions": [],
                "actions": [],
                "assertions": [],
                "postconditions": [],
            }
        ]