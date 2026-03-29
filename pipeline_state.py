"""
pipeline_state.py
-----------------
Canonical state schema for the QA agent pipeline.

Design principle (Ousterhout): this module is the single source of truth for
what the pipeline *knows* at any moment. Every agent reads from and writes to
this object. No agent-to-agent direct coupling — they communicate exclusively
through PipelineState.

The interface is intentionally narrow: agents call `state.set_artifact()` and
`state.advance()`. The complexity of serialisation, validation, and phase
ordering is hidden here.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Phase ordering — the canonical execution sequence
# ---------------------------------------------------------------------------

class Phase(Enum):
    """Ordered pipeline phases. Ordinal value encodes allowed transitions."""
    INIT           = 0
    ANALYSIS       = 1   # Analyst Agent: read codebase, derive requirements
    RISK           = 2   # Risk Analyst: build risk register
    TEST_DESIGN    = 3   # Test Designer: produce test case specs
    TEST_CODE      = 4   # Test Coder: write pytest code
    FEATURE_CODE   = 5   # Feature Implementer: make tests pass (TDD)
    EXECUTION      = 6   # Test Executor: run the suite
    REPORTING      = 7   # Reporter: markdown + Polarion
    DONE           = 8
    FAILED         = 99  # Terminal failure — requires human intervention


# ---------------------------------------------------------------------------
# Artifact keys — what each phase produces
# ---------------------------------------------------------------------------

class ArtifactKey(str, Enum):
    """
    Stable keys for artifacts stored in PipelineState.artifacts.
    Using an enum prevents typo-driven KeyErrors across agents.
    """
    CODEBASE_SNAPSHOT   = "codebase_snapshot"    # Phase.ANALYSIS output
    REQUIREMENTS        = "requirements"          # Phase.ANALYSIS output
    RISK_REGISTER       = "risk_register"         # Phase.RISK output
    TEST_SUITE_MANIFEST = "test_suite_manifest"  # Phase.TEST_DESIGN output
    TEST_FILE_PATH      = "test_file_path"        # Phase.TEST_CODE output
    FEATURE_FILES       = "feature_files"         # Phase.FEATURE_CODE output
    EXECUTION_REPORT    = "execution_report"      # Phase.EXECUTION output
    REPORT_PATH         = "report_path"           # Phase.REPORTING output


# ---------------------------------------------------------------------------
# Lightweight structured types for artifact payloads
# ---------------------------------------------------------------------------

@dataclass
class Risk:
    id: str                  # e.g. "R1", "S2", "P1"
    description: str
    severity: str            # Critical | High | Medium | Low
    likelihood: str          # High | Medium | Low
    module: str
    category: str            # Bugs | Security | Performance | Maintainability | TestGap


@dataclass
class QATestSpec:
    id: str                  # e.g. "TC-R1-001"
    name: str
    risk_id: str
    severity: str
    module: str
    preconditions: list[str]
    actions: list[str]
    assertions: list[str]
    postconditions: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    test_id: str
    status: str              # PASS | FAIL | SKIP | ERROR | XFAIL | XPASS
    duration_s: float
    error_message: str | None = None


@dataclass
class FeedbackEvent:
    """
    Raised by Test Executor when a failure needs routing.
    The Orchestrator inspects this to decide whether to loop back.
    """
    test_id: str
    failure_type: str        # "test_bug" | "feature_bug" | "new_risk"
    detail: str
    target_phase: Phase      # Phase the Orchestrator should rewind to


# ---------------------------------------------------------------------------
# Core state object
# ---------------------------------------------------------------------------

@dataclass
class PipelineState:
    """
    Single shared object that all agents read from and write to.

    Agents never communicate with each other directly. The Orchestrator
    passes this object into each agent call; agents mutate it via the
    public API below.

    Fields
    ------
    run_id      : unique identifier for this pipeline run (timestamp-based)
    scope       : root path of the codebase being analysed
    phase       : current execution phase
    artifacts   : keyed store of outputs from each phase
    feedback    : pending FeedbackEvents from Test Executor
    retry_count : how many times the current phase has been retried
    max_retries : ceiling before escalating to Phase.FAILED
    errors      : log of non-fatal errors; agents append, never raise
    started_at  : unix timestamp
    updated_at  : unix timestamp of last mutation
    """
    scope: str
    run_id: str                               = field(default_factory=lambda: f"run-{int(time.time())}")
    phase: Phase                              = Phase.INIT
    artifacts: dict[str, Any]                = field(default_factory=dict)
    feedback: list[FeedbackEvent]            = field(default_factory=list)
    retry_count: int                          = 0
    max_retries: int                          = 3
    errors: list[str]                         = field(default_factory=list)
    started_at: float                         = field(default_factory=time.time)
    updated_at: float                         = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Artifact API — the primary interface for agents
    # ------------------------------------------------------------------

    def set_artifact(self, key: ArtifactKey, value: Any) -> None:
        """Store an artifact produced by the current phase."""
        self.artifacts[key.value] = value
        self._touch()

    def get_artifact(self, key: ArtifactKey) -> Any:
        """
        Retrieve an artifact. Raises KeyError with a clear message if absent,
        so agents fail loudly rather than silently operating on None.
        """
        if key.value not in self.artifacts:
            raise KeyError(
                f"Artifact '{key.value}' not found. "
                f"Current phase: {self.phase.name}. "
                f"Available: {list(self.artifacts.keys())}"
            )
        return self.artifacts[key.value]

    def has_artifact(self, key: ArtifactKey) -> bool:
        return key.value in self.artifacts

    # ------------------------------------------------------------------
    # Phase transition API — owned exclusively by the Orchestrator
    # ------------------------------------------------------------------

    def advance(self, to: Phase) -> None:
        """
        Transition to the next phase. Validates the transition is legal:
        only forward moves and feedback-driven rewinds are permitted.

        Rewinds (to.value < self.phase.value) are allowed when there is
        a pending FeedbackEvent targeting that phase — the Orchestrator
        is responsible for clearing feedback before calling advance().
        """
        is_rewind = to.value < self.phase.value
        if is_rewind:
            pending_targets = {fb.target_phase for fb in self.feedback}
            if to not in pending_targets:
                raise ValueError(
                    f"Illegal rewind {self.phase.name} → {to.name}: "
                    f"no FeedbackEvent targeting {to.name}."
                )
        self.phase = to
        self.retry_count = 0
        self._touch()

    def mark_failed(self, reason: str) -> None:
        self.errors.append(f"[FATAL] {reason}")
        self.phase = Phase.FAILED
        self._touch()

    def record_error(self, message: str) -> None:
        """Non-fatal. Agent continues; Orchestrator may retry."""
        self.errors.append(f"[{self.phase.name}] {message}")
        self._touch()

    def increment_retry(self) -> bool:
        """
        Increment retry counter. Returns False when max_retries exceeded,
        signalling the Orchestrator to mark the run as FAILED.
        """
        self.retry_count += 1
        self._touch()
        return self.retry_count <= self.max_retries

    # ------------------------------------------------------------------
    # Feedback API — used by Orchestrator to route test failures
    # ------------------------------------------------------------------

    def add_feedback(self, event: FeedbackEvent) -> None:
        self.feedback.append(event)
        self._touch()

    def consume_feedback(self, failure_type: str) -> list[FeedbackEvent]:
        """
        Pop and return all feedback events of a given type.
        Orchestrator calls this before deciding whether to rewind.
        """
        matched   = [fb for fb in self.feedback if fb.failure_type == failure_type]
        remaining = [fb for fb in self.feedback if fb.failure_type != failure_type]
        self.feedback = remaining
        self._touch()
        return matched

    # ------------------------------------------------------------------
    # Persistence — save/restore to disk for resumability
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """
        Serialise state to JSON. Agents don't call this — the Orchestrator
        calls it after every successful phase transition.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "run_id":      self.run_id,
            "scope":       self.scope,
            "phase":       self.phase.name,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "errors":      self.errors,
            "started_at":  self.started_at,
            "updated_at":  self.updated_at,
            # Artifacts that are plain dicts/lists serialise fine.
            # Dataclass artifacts need __dict__ expansion — handled below.
            "artifacts":   self._serialise_artifacts(),
            "feedback":    [
                {
                    "test_id":      fb.test_id,
                    "failure_type": fb.failure_type,
                    "detail":       fb.detail,
                    "target_phase": fb.target_phase.name,
                }
                for fb in self.feedback
            ],
        }
        path.write_text(json.dumps(snapshot, indent=2, default=str))

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        """Restore state from a saved JSON snapshot."""
        data = json.loads(path.read_text())
        state = cls(scope=data["scope"], run_id=data["run_id"])
        state.phase       = Phase[data["phase"]]
        state.retry_count = data["retry_count"]
        state.max_retries = data["max_retries"]
        state.errors      = data["errors"]
        state.started_at  = data["started_at"]
        state.updated_at  = data["updated_at"]
        state.artifacts   = data["artifacts"]   # raw dicts; agents re-hydrate if needed
        state.feedback    = [
            FeedbackEvent(
                test_id      = fb["test_id"],
                failure_type = fb["failure_type"],
                detail       = fb["detail"],
                target_phase = Phase[fb["target_phase"]],
            )
            for fb in data["feedback"]
        ]
        return state

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> str:
        lines = [
            f"Run:     {self.run_id}",
            f"Scope:   {self.scope}",
            f"Phase:   {self.phase.name}",
            f"Retries: {self.retry_count}/{self.max_retries}",
            f"Artifacts produced: {[k for k in self.artifacts]}",
            f"Pending feedback:   {len(self.feedback)}",
            f"Errors logged:      {len(self.errors)}",
        ]
        if self.errors:
            lines.append("--- Errors ---")
            lines.extend(f"  {e}" for e in self.errors)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _touch(self) -> None:
        self.updated_at = time.time()

    def _serialise_artifacts(self) -> dict:
        result = {}
        for k, v in self.artifacts.items():
            if hasattr(v, "__dict__"):
                result[k] = v.__dict__
            elif isinstance(v, list) and v and hasattr(v[0], "__dict__"):
                result[k] = [item.__dict__ for item in v]
            else:
                result[k] = v
        return result
