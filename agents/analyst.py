"""
agents/analyst.py
-----------------
Analyst Agent - reads codebase, builds structural snapshot, derives requirements.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import BaseAgent
from pipeline_state import ArtifactKey, PipelineState


SYSTEM_PROMPT = """You are a code analyst. Your task is to analyze Python source files and extract their structure.

Respond ONLY in JSON matching the schemas provided. Do not summarise. Do not explain. Emit JSON only."""


class AnalystAgent(BaseAgent):
    """
    First agent in the pipeline. Takes a codebase root path, reads every relevant
    source file, builds a structural snapshot, and derives a requirements list.

    Produces:
    - CODEBASE_SNAPSHOT: structural analysis of each file
    - REQUIREMENTS: list of explicit, inferred, and gap requirements
    """

    name = "Analyst"

    def _execute(self, state: PipelineState) -> None:
        scope = Path(state.scope)
        if not scope.exists():
            raise FileNotFoundError(f"Scope directory not found: {scope}")

        # Step 1: Build codebase snapshot
        snapshot = self._build_snapshot(scope)

        # Step 2: Derive requirements
        requirements = self._derive_requirements(snapshot, scope)

        # Store artifacts
        state.set_artifact(ArtifactKey.CODEBASE_SNAPSHOT, snapshot)
        state.set_artifact(ArtifactKey.REQUIREMENTS, requirements)

        self.log_summary(
            f"Scope: {state.scope}, Files: {len(snapshot.get('files', []))}, "
            f"Requirements: {len(requirements)}"
        )

    def _build_snapshot(self, scope: Path) -> dict:
        """Build structural snapshot of the codebase."""
        files = self.read_files_in_dir(scope, "*.py")

        if not files:
            raise ValueError(f"No Python files found in {scope}")

        # Build file list for LLM
        file_list = []
        for path, content in sorted(files.items()):
            relative = path.relative_to(scope)
            file_info = {
                "path": str(relative),
                "content": self.truncate_for_llm(content, max_chars=10000),
            }
            file_list.append(file_info)

        # Call LLM to extract structure
        prompt = f"""Extract structure from the following Python files in {scope}:

{json.dumps(file_list, indent=2)}

Return JSON with this schema:
{{
  "files": [
    {{
      "path": "relative/path.py",
      "classes": ["ClassName"],
      "functions": ["func_name"],
      "imports": ["requests", "datetime"],
      "external_calls": ["requests.get", "feedparser.parse"],
      "config_deps": ["RSS_FEED_URL"],
      "has_tests": true,
      "line_count": 100,
      "todos": ["TODO: fix this"]
    }}
  ],
  "dependency_inventory": ["requests", "feedparser"],
  "uncovered_modules": ["config.py"]
}}"""

        try:
            result = self.call_llm_json(SYSTEM_PROMPT, prompt)
        except Exception as exc:
            self._logger.warning("LLM structure extraction failed, using fallback: %s", exc)
            result = self._fallback_snapshot(files, scope)

        return result

    def _fallback_snapshot(self, files: dict[Path, str], scope: Path) -> dict:
        """Build basic snapshot without LLM."""
        file_list = []
        for path, content in sorted(files.items()):
            relative = path.relative_to(scope)

            # Simple extraction
            classes = re.findall(r'^class (\w+)', content, re.MULTILINE)
            functions = re.findall(r'^def (\w+)', content, re.MULTILINE)
            imports = re.findall(r'^import (\w+)', content, re.MULTILINE)
            imports += re.findall(r'^from (\w+)', content, re.MULTILINE)

            file_list.append({
                "path": str(relative),
                "classes": classes,
                "functions": functions,
                "imports": list(set(imports)),
                "external_calls": [],
                "config_deps": [],
                "has_tests": "test_" in str(relative),
                "line_count": len(content.splitlines()),
                "todos": [],
            })

        return {
            "files": file_list,
            "dependency_inventory": [],
            "uncovered_modules": [f["path"] for f in file_list if not f.get("has_tests")],
        }

    def _derive_requirements(self, snapshot: dict, scope: Path) -> list[dict]:
        """Derive requirements from snapshot and any documentation."""
        # Look for docs
        docs = {}
        for doc_path in scope.rglob("*.md"):
            try:
                docs[doc_path.name] = self.read_file(doc_path)
            except Exception:
                pass

        docs_content = json.dumps(list(docs.items())[:5])  # Limit docs

        prompt = f"""Given this codebase snapshot and documentation, derive requirements.

Snapshot:
{json.dumps(snapshot, indent=2)}

Docs:
{docs_content}

Return JSON with this schema:
[
  {{
    "id": "REQ-001",
    "type": "explicit|inferred|gap",
    "text": "requirement description",
    "source": "README.md:L14 or module.py::function",
    "modules": ["main.py"]
  }}
]

Generate at least 5 requirements covering different modules."""

        try:
            result = self.call_llm_json(SYSTEM_PROMPT, prompt)
            if isinstance(result, list):
                return result
        except Exception as exc:
            self._logger.warning("LLM requirements derivation failed: %s", exc)

        # Fallback: basic requirements
        return [
            {
                "id": "REQ-001",
                "type": "inferred",
                "text": "Code must handle errors gracefully",
                "source": "General",
                "modules": [],
            }
        ]