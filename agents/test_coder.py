"""
agents/test_coder.py
-------------------
Test Coder Agent - writes pytest code from test specs.
"""

from __future__ import annotations

import json

from .base import BaseAgent
from pipeline_state import ArtifactKey, PipelineState


SYSTEM_PROMPT = """You are a test coder. Write pytest code from test specifications.

Respond ONLY with valid pytest code in a JSON object. No explanations."""


class TestCoderAgent(BaseAgent):
    """
    Writes pytest code from test case specifications.

    Produces:
    - TEST_FILE_PATH: path to generated test file
    """

    name = "TestCoder"

    def _execute(self, state: PipelineState) -> None:
        test_manifest = state.get_artifact(ArtifactKey.TEST_SUITE_MANIFEST)
        snapshot = state.get_artifact(ArtifactKey.CODEBASE_SNAPSHOT)

        # Write pytest code
        test_file = self._write_tests(test_manifest, snapshot)

        state.set_artifact(ArtifactKey.TEST_FILE_PATH, test_file)
        self.log_summary(f"Generated test file: {test_file}")

    def _write_tests(self, test_cases: list[dict], snapshot: dict) -> str:
        """Generate pytest code from test cases."""
        prompt = f"""Write pytest code for these test cases:

{json.dumps(test_cases, indent=2)}

Codebase info:
{json.dumps(snapshot, indent=2)}

Return JSON with this schema:
{{
  "test_file_path": "tests/test_qa_generated.py",
  "test_code": "import pytest\\n\\n..."
}}

Write valid pytest code with:
- Proper fixtures
- Clear test names matching TC-* IDs
- Assertions matching the test case assertions
- Use mock where needed"""

        try:
            result = self.call_llm_json(SYSTEM_PROMPT, prompt)
            if isinstance(result, dict):
                # Write the file
                file_path = result.get("test_file_path", "tests/test_qa_generated.py")
                test_code = result.get("test_code", "# No code generated")

                # Create tests directory if needed
                from pathlib import Path
                test_dir = Path("tests")
                test_dir.mkdir(exist_ok=True)

                full_path = test_dir / "test_qa_generated.py"
                full_path.write_text(test_code)

                return str(full_path)
        except Exception as exc:
            self._logger.warning("LLM test coding failed: %s", exc)

        # Fallback
        from pathlib import Path
        test_dir = Path("tests")
        test_dir.mkdir(exist_ok=True)
        fallback_path = test_dir / "test_qa_generated.py"
        fallback_path.write_text('import pytest\n\ndef test_placeholder():\n    pass\n')
        return str(fallback_path)