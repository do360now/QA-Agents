"""
orchestrator.py
---------------
The QA pipeline Orchestrator.

Design principle (Ousterhout): this is the *only* module that knows about
phase ordering, retry policy, and feedback routing. Every other agent is
stateless — it receives a PipelineState, mutates artifacts, and returns.
The Orchestrator hides the state machine complexity behind a single call:

    result = orchestrator.run(scope="/path/to/project")

Agents are injected at construction time (dependency injection), making
the Orchestrator independently testable with mock agents.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from pipeline_state import (
    ArtifactKey,
    FeedbackEvent,
    Phase,
    PipelineState,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent protocol — the single interface every agent must satisfy
# ---------------------------------------------------------------------------

class Agent(Protocol):
    """
    Narrow interface for all pipeline agents.

    An agent receives the full PipelineState, mutates it (adds artifacts,
    logs errors, raises FeedbackEvents), and returns. It never advances
    the phase — that is exclusively the Orchestrator's responsibility.

    Raising an exception signals an unrecoverable error within the agent.
    Non-fatal errors should be written to state.record_error() instead.
    """
    name: str

    def run(self, state: PipelineState) -> None: ...


# ---------------------------------------------------------------------------
# Feedback routing table
# ---------------------------------------------------------------------------

# Maps failure_type strings (produced by Test Executor) to the Phase
# the Orchestrator should rewind to.
FEEDBACK_ROUTING: dict[str, Phase] = {
    "test_bug":    Phase.TEST_CODE,
    "feature_bug": Phase.FEATURE_CODE,
    "new_risk":    Phase.RISK,
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Runs the QA pipeline as a resumable state machine.

    Responsibilities (hidden from callers):
    - Phase sequencing and transition validation
    - Retry policy on agent failure
    - Feedback-driven rewinds (test failures loop back to the right phase)
    - State persistence after every successful transition
    - Structured logging throughout

    Not responsible for:
    - Any QA logic (that belongs in agents)
    - Report formatting (that belongs in Reporter)
    - Test execution mechanics (that belongs in Test Executor)
    """

    def __init__(
        self,
        analyst:              Agent,
        risk_analyst:         Agent,
        test_designer:        Agent,
        test_coder:           Agent,
        feature_implementer:  Agent,
        test_executor:        Agent,
        reporter:             Agent,
        state_dir:            Path = Path(".pipeline_state"),
        max_retries:          int  = 3,
    ) -> None:
        self._agents: dict[Phase, Agent] = {
            Phase.ANALYSIS:     analyst,
            Phase.RISK:         risk_analyst,
            Phase.TEST_DESIGN:  test_designer,
            Phase.TEST_CODE:    test_coder,
            Phase.FEATURE_CODE: feature_implementer,
            Phase.EXECUTION:    test_executor,
            Phase.REPORTING:    reporter,
        }
        self._state_dir  = state_dir
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API — one method
    # ------------------------------------------------------------------

    def run(
        self,
        scope: str,
        resume_from: Path | None = None,
    ) -> PipelineState:
        """
        Execute the full QA pipeline for `scope`.

        Parameters
        ----------
        scope       : root path of the codebase to analyse (e.g. "hi-tech/")
        resume_from : path to a saved PipelineState JSON to resume a partial run

        Returns the final PipelineState regardless of outcome. Inspect
        state.phase to determine success (Phase.DONE) vs failure (Phase.FAILED).
        """
        state = self._initialise(scope, resume_from)
        logger.info("Pipeline started. Run ID: %s  Scope: %s", state.run_id, state.scope)

        while state.phase not in (Phase.DONE, Phase.FAILED):
            self._run_current_phase(state)

        self._log_outcome(state)
        return state

    # ------------------------------------------------------------------
    # State machine internals
    # ------------------------------------------------------------------

    def _initialise(self, scope: str, resume_from: Path | None) -> PipelineState:
        if resume_from and resume_from.exists():
            state = PipelineState.load(resume_from)
            logger.info("Resuming from %s at phase %s", resume_from, state.phase.name)
        else:
            state = PipelineState(scope=scope, max_retries=self._max_retries)
            state.advance(Phase.ANALYSIS)
        return state

    def _run_current_phase(self, state: PipelineState) -> None:
        phase  = state.phase
        agent  = self._agents.get(phase)

        if agent is None:
            state.mark_failed(f"No agent registered for phase {phase.name}")
            return

        logger.info("[%s] Running agent: %s", phase.name, agent.name)

        errors_before = len(state.errors)

        try:
            agent.run(state)
        except Exception as exc:                          # agent raised — retry or fail
            self._handle_agent_exception(state, exc)
            return

        new_errors = state.errors[errors_before:]
        if new_errors:
            # Non-fatal errors were recorded by the agent during THIS attempt.
            # Retry the phase if budget allows; otherwise fail.
            last_error = new_errors[-1]
            logger.warning("[%s] Agent recorded errors: %s", phase.name, last_error)
            if not state.increment_retry():
                state.mark_failed(
                    f"Phase {phase.name} exceeded {self._max_retries} retries. "
                    f"Last error: {last_error}"
                )
                return
            logger.info("[%s] Retrying (attempt %d/%d)", phase.name, state.retry_count, self._max_retries)
            return                                        # loop will re-run the same phase

        # Phase succeeded. Handle feedback before advancing.
        if state.feedback and phase == Phase.EXECUTION:
            self._route_feedback(state)
            return

        self._advance_to_next(state, phase)

    def _handle_agent_exception(self, state: PipelineState, exc: Exception) -> None:
        phase = state.phase
        logger.error("[%s] Agent raised exception: %s", phase.name, exc, exc_info=True)
        state.record_error(str(exc))
        if not state.increment_retry():
            state.mark_failed(
                f"Phase {phase.name} raised unhandled exception after "
                f"{self._max_retries} retries: {exc}"
            )

    def _route_feedback(self, state: PipelineState) -> None:
        """
        Inspect FeedbackEvents from Test Executor and rewind to the
        appropriate phase. Priority: new_risk > feature_bug > test_bug.
        Rationale: rewinding further is safer — re-running from RISK
        re-generates test design and code automatically.
        """
        for failure_type in ("new_risk", "feature_bug", "test_bug"):
            if not any(fb.failure_type == failure_type for fb in state.feedback):
                continue
            target = FEEDBACK_ROUTING[failure_type]
            events = state.consume_feedback(failure_type)   # consume BEFORE advance
            logger.info(
                "[FEEDBACK] %d '%s' event(s) — rewinding to %s",
                len(events), failure_type, target.name,
            )
            for ev in events:
                logger.debug("  └─ %s: %s", ev.test_id, ev.detail)
            # Re-add so advance() can validate the rewind, then clear
            for ev in events:
                state.add_feedback(ev)
            state.advance(target)
            state.feedback.clear()      # consumed; advance validated them
            self._persist(state)
            return

        # No feedback to act on (shouldn't reach here, but be safe)
        logger.warning("[EXECUTION] Feedback list was non-empty but contained no routable events.")
        self._advance_to_next(state, Phase.EXECUTION)

    def _advance_to_next(self, state: PipelineState, current: Phase) -> None:
        """Move to the next sequential phase, or DONE if pipeline is complete."""
        next_phase = self._next_phase(current)
        state.advance(next_phase)
        self._persist(state)
        logger.info("[%s] ✓ Complete → %s", current.name, next_phase.name)

    @staticmethod
    def _next_phase(current: Phase) -> Phase:
        """
        Returns the next Phase in ordinal sequence.
        Phase.EXECUTION → Phase.REPORTING → Phase.DONE.
        """
        ordered = [p for p in Phase if p not in (Phase.FAILED,)]
        ordered.sort(key=lambda p: p.value)
        idx = ordered.index(current)
        if idx + 1 < len(ordered):
            return ordered[idx + 1]
        return Phase.DONE

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self, state: PipelineState) -> None:
        """Save state after every phase transition. Enables resumability."""
        path = self._state_dir / f"{state.run_id}.json"
        try:
            state.save(path)
            logger.debug("State persisted to %s", path)
        except Exception as exc:
            # Persistence failure is non-fatal — pipeline continues.
            logger.warning("Failed to persist state: %s", exc)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def _log_outcome(self, state: PipelineState) -> None:
        if state.phase == Phase.DONE:
            report = state.get_artifact(ArtifactKey.REPORT_PATH) if state.has_artifact(ArtifactKey.REPORT_PATH) else "N/A"
            logger.info(
                "Pipeline COMPLETE. Run: %s  Report: %s",
                state.run_id, report,
            )
        else:
            logger.error(
                "Pipeline FAILED at phase %s. Run: %s\n%s",
                state.phase.name, state.run_id, state.summary(),
            )
