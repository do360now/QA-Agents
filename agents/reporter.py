"""
agents/reporter.py
------------------
Reporter Agent - generates markdown + Polarion reports.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .base import BaseAgent
from pipeline_state import ArtifactKey, PipelineState


class ReporterAgent(BaseAgent):
    """
    Generates QA report in markdown format.

    Produces:
    - REPORT_PATH: path to generated report
    """

    name = "Reporter"

    def _execute(self, state: PipelineState) -> None:
        # Gather all artifacts
        snapshot = state.get_artifact(ArtifactKey.CODEBASE_SNAPSHOT)
        requirements = state.get_artifact(ArtifactKey.REQUIREMENTS)
        risks = state.get_artifact(ArtifactKey.RISK_REGISTER)
        test_manifest = state.get_artifact(ArtifactKey.TEST_SUITE_MANIFEST)
        execution_report = state.get_artifact(ArtifactKey.EXECUTION_REPORT)

        # Generate report
        report_path = self._generate_report(
            scope=state.scope,
            snapshot=snapshot,
            requirements=requirements,
            risks=risks,
            test_manifest=test_manifest,
            execution_report=execution_report,
        )

        state.set_artifact(ArtifactKey.REPORT_PATH, report_path)
        self.log_summary(f"Generated report: {report_path}")

    def _generate_report(
        self,
        scope: str,
        snapshot: dict,
        requirements: list,
        risks: list,
        test_manifest: list,
        execution_report: list,
    ) -> str:
        """Generate markdown report."""
        report_lines = [
            "# QA Report",
            "",
            f"**Scope:** {scope}",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"- Files analyzed: {len(snapshot.get('files', []))}",
            f"- Requirements identified: {len(requirements)}",
            f"- Risks identified: {len(risks)}",
            f"- Test cases designed: {len(test_manifest)}",
            f"- Tests executed: {len(execution_report)}",
            "",
        ]

        # Requirements section
        if requirements:
            report_lines.extend([
                "## Requirements",
                "",
                "| ID | Type | Description | Module |",
                "|-----|------|-------------|--------|",
            ])
            for req in requirements[:10]:
                report_lines.append(
                    f"| {req.get('id', '')} | {req.get('type', '')} | {req.get('text', '')} | {req.get('modules', [''])[0]} |"
                )
            report_lines.append("")

        # Risks section
        if risks:
            report_lines.extend([
                "## Risk Register",
                "",
                "| ID | Category | Severity | Description |",
                "|----|----------|----------|-------------|",
            ])
            for risk in risks[:10]:
                report_lines.append(
                    f"| {risk.get('id', '')} | {risk.get('category', '')} | {risk.get('severity', '')} | {risk.get('description', '')} |"
                )
            report_lines.append("")

        # Test execution section
        if execution_report:
            report_lines.extend([
                "## Test Results",
                "",
                "| Test ID | Status |",
                "|---------|--------|",
            ])
            for result in execution_report[:20]:
                status_icon = "✓" if result.get("status") == "PASS" else "✗"
                report_lines.append(
                    f"| {result.get('test_id', '')} | {status_icon} {result.get('status', '')} |"
                )
            report_lines.append("")

        # Write report
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)

        report_path = report_dir / f"qa_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path.write_text("\n".join(report_lines))

        return str(report_path)