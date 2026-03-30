"""
agents/feature_implementer.py
-----------------------------
Feature Implementer Agent - implements features to make tests pass (TDD).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .base import BaseAgent
from pipeline_state import ArtifactKey, PipelineState


SYSTEM_PROMPT = """You are a feature implementer. Implement code to make failing tests pass.

Respond ONLY with valid Python code in a JSON object. No explanations."""


class FeatureImplementerAgent(BaseAgent):
    """
    Implements features using TDD - makes tests pass.

    Produces:
    - FEATURE_FILES: list of modified/created files
    """

    name = "FeatureImplementer"

    def _execute(self, state: PipelineState) -> None:
        test_file = state.get_artifact(ArtifactKey.TEST_FILE_PATH)
        snapshot = state.get_artifact(ArtifactKey.CODEBASE_SNAPSHOT)

        # Run tests to see what's failing
        failures = self._run_tests(test_file)

        # Implement fixes
        modified = self._implement_fixes(failures, snapshot, test_file)

        state.set_artifact(ArtifactKey.FEATURE_FILES, modified)
        self.log_summary(f"Modified {len(modified)} files")

    def _run_tests(self, test_file: str) -> list[dict]:
        """Run pytest and collect failures."""
        test_path = Path(test_file)
        if not test_path.exists():
            return []

        try:
            result = subprocess.run(
                ["pytest", str(test_path), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout + result.stderr

            # Parse failures (simple approach)
            failures = []
            for line in output.splitlines():
                if "FAILED" in line:
                    failures.append({"output": line})

            return failures
        except Exception as exc:
            self._logger.warning("Test execution failed: %s", exc)
            return []

    def _implement_fixes(
        self,
        failures: list[dict],
        snapshot: dict,
        test_file: str,
    ) -> list[str]:
        """Implement fixes based on test failures."""
        if not failures:
            self._logger.info("No test failures to fix")
            return []

        # Get existing modules to modify
        modules = snapshot.get("files", [])
        if not modules:
            return []

        # Prompt LLM to implement fixes
        prompt = f"""The following tests are failing:

{json.dumps(failures, indent=2)}

Available modules:
{json.dumps(modules[:5], indent=2)}

Return JSON with this schema:
{{
  "files": [
    {{
      "path": "module.py",
      "code": "full Python code to write"
    }}
  ]
}}

Implement the minimal code changes needed to make tests pass.
Keep changes focused and minimal."""

        try:
            result = self.call_llm_json(SYSTEM_PROMPT, prompt)
            if isinstance(result, dict):
                files = result.get("files", [])
                modified = []
                for f in files:
                    path = Path(f.get("path", "module.py"))
                    code = f.get("code", "")
                    path.write_text(code)
                    modified.append(str(path))
                return modified
        except Exception as exc:
            self._logger.warning("LLM implementation failed: %s", exc)

        return []