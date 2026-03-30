"""
agents/test_executor.py
-----------------------
Test Executor Agent - runs pytest and classifies failures.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .base import BaseAgent
from pipeline_state import (
    ArtifactKey,
    ExecutionResult,
    FeedbackEvent,
    Phase,
    PipelineState,
)


class TestExecutorAgent(BaseAgent):
    """
    Runs pytest suite and classifies test outcomes.

    Produces:
    - EXECUTION_REPORT: list of ExecutionResult with status
    - FeedbackEvent for any failures that need routing
    """

    name = "TestExecutor"

    def _execute(self, state: PipelineState) -> None:
        test_file = state.get_artifact(ArtifactKey.TEST_FILE_PATH)
        risk_register = state.get_artifact(ArtifactKey.RISK_REGISTER)

        # Run tests
        results = self._run_tests(test_file)

        # Store execution report
        state.set_artifact(ArtifactKey.EXECUTION_REPORT, [
            {"test_id": r.test_id, "status": r.status, "duration_s": r.duration_s}
            for r in results
        ])

        # Add feedback for failures
        for result in results:
            if result.status in ("FAIL", "ERROR"):
                self._classify_failure(state, result, risk_register)

        passed = sum(1 for r in results if r.status == "PASS")
        self.log_summary(f"Executed {len(results)} tests: {passed} passed, {len(results) - passed} failed")

    def _run_tests(self, test_file: str) -> list[ExecutionResult]:
        """Run pytest and parse results."""
        test_path = Path(test_file)
        if not test_path.exists():
            return []

        try:
            result = subprocess.run(
                ["pytest", str(test_path), "-v", "--tb=short", "--json-report", "--json-report-file=/tmp/report.json"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            output = result.stdout + result.stderr

            # Try to parse JSON report
            json_report = Path("/tmp/report.json")
            if json_report.exists():
                data = json.loads(json_report.read_text())
                return self._parse_json_report(data)

            # Fallback: parse text output
            return self._parse_text_output(output)

        except subprocess.TimeoutExpired:
            return [ExecutionResult(test_id="timeout", status="ERROR", duration_s=300, error_message="Test timeout")]
        except Exception as exc:
            return [ExecutionResult(test_id="error", status="ERROR", duration_s=0, error_message=str(exc))]

    def _parse_json_report(self, data: dict) -> list[ExecutionResult]:
        """Parse JSON report from pytest."""
        results = []
        for test in data.get("tests", []):
            results.append(ExecutionResult(
                test_id=test.get("nodeid", "unknown"),
                status=test.get("outcome", "UNKNOWN"),
                duration_s=test.get("setup", {}).get("duration", 0) + test.get("call", {}).get("duration", 0),
                error_message=test.get("call", {}).get("longrepr"),
            ))
        return results

    def _parse_text_output(self, output: str) -> list[ExecutionResult]:
        """Parse text output from pytest."""
        results = []
        for line in output.splitlines():
            if line.startswith("tests/") and ("PASSED" in line or "FAILED" in line or "ERROR" in line):
                parts = line.split()
                if len(parts) >= 2:
                    test_id = parts[0]
                    status = "PASS" if "PASSED" in line else "FAIL"
                    results.append(ExecutionResult(test_id=test_id, status=status, duration_s=0))
        return results

    def _classify_failure(
        self,
        state: PipelineState,
        result: ExecutionResult,
        risk_register: list[dict],
    ) -> None:
        """Classify failure and add feedback."""
        test_id = result.test_id
        error_msg = result.error_message or ""

        # Map test ID to risk
        failure_type = "test_bug"  # Default
        target = Phase.TEST_CODE

        # Try to determine failure type from error message
        if any(kw in error_msg.lower() for kw in ("not implemented", "attributeerror", "import error")):
            failure_type = "feature_bug"
            target = Phase.FEATURE_CODE
        elif any(kw in error_msg.lower() for kw in ("risk", "security", "vulnerability")):
            failure_type = "new_risk"
            target = Phase.RISK
        else:
            # Check if there's a matching risk
            for risk in risk_register:
                if risk.get("id", "") in test_id:
                    failure_type = "feature_bug"
                    target = Phase.FEATURE_CODE
                    break

        state.add_feedback(FeedbackEvent(
            test_id=test_id,
            failure_type=failure_type,
            detail=error_msg[:200] if error_msg else "Test failed",
            target_phase=target,
        ))