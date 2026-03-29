"""
test_pipeline.py
----------------
Tests for PipelineState and Orchestrator.

Covers:
- Phase transitions (forward and feedback-driven rewinds)
- Retry policy
- Artifact API
- Feedback routing
- Persistence (save/load roundtrip)
- Orchestrator with mock agents
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pipeline_state import (
    ArtifactKey,
    FeedbackEvent,
    Phase,
    PipelineState,
    Risk,
    QATestSpec,
)
from orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_state() -> PipelineState:
    state = PipelineState(scope="test-project/")
    state.advance(Phase.ANALYSIS)
    return state


@pytest.fixture
def mock_agent():
    """Returns a factory for creating named mock agents that do nothing."""
    def _make(name: str, side_effect=None):
        agent = MagicMock()
        agent.name = name
        if side_effect:
            agent.run.side_effect = side_effect
        return agent
    return _make


@pytest.fixture
def all_mock_agents(mock_agent):
    return {
        "analyst":             mock_agent("Analyst"),
        "risk_analyst":        mock_agent("RiskAnalyst"),
        "test_designer":       mock_agent("TestDesigner"),
        "test_coder":          mock_agent("TestCoder"),
        "feature_implementer": mock_agent("FeatureImplementer"),
        "test_executor":       mock_agent("TestExecutor"),
        "reporter":            mock_agent("Reporter"),
    }


@pytest.fixture
def orchestrator(all_mock_agents, tmp_path):
    return Orchestrator(
        state_dir=tmp_path / "state",
        **all_mock_agents,
    )


# ---------------------------------------------------------------------------
# PipelineState — artifact API
# ---------------------------------------------------------------------------

class TestArtifactAPI:

    def test_set_and_get_artifact(self, fresh_state):
        fresh_state.set_artifact(ArtifactKey.REQUIREMENTS, ["req-1", "req-2"])
        result = fresh_state.get_artifact(ArtifactKey.REQUIREMENTS)
        assert result == ["req-1", "req-2"]

    def test_get_missing_artifact_raises_key_error(self, fresh_state):
        with pytest.raises(KeyError, match="codebase_snapshot"):
            fresh_state.get_artifact(ArtifactKey.CODEBASE_SNAPSHOT)

    def test_has_artifact_returns_false_when_absent(self, fresh_state):
        assert fresh_state.has_artifact(ArtifactKey.RISK_REGISTER) is False

    def test_has_artifact_returns_true_after_set(self, fresh_state):
        fresh_state.set_artifact(ArtifactKey.RISK_REGISTER, [])
        assert fresh_state.has_artifact(ArtifactKey.RISK_REGISTER) is True

    def test_set_artifact_updates_timestamp(self, fresh_state):
        before = fresh_state.updated_at
        time.sleep(0.01)
        fresh_state.set_artifact(ArtifactKey.REQUIREMENTS, [])
        assert fresh_state.updated_at > before


# ---------------------------------------------------------------------------
# PipelineState — phase transitions
# ---------------------------------------------------------------------------

class TestPhaseTransitions:

    def test_advance_forward_is_allowed(self, fresh_state):
        fresh_state.advance(Phase.RISK)
        assert fresh_state.phase == Phase.RISK

    def test_advance_resets_retry_count(self, fresh_state):
        fresh_state.retry_count = 2
        fresh_state.advance(Phase.RISK)
        assert fresh_state.retry_count == 0

    def test_rewind_without_feedback_raises(self, fresh_state):
        fresh_state.advance(Phase.RISK)
        with pytest.raises(ValueError, match="Illegal rewind"):
            fresh_state.advance(Phase.ANALYSIS)

    def test_rewind_with_matching_feedback_is_allowed(self, fresh_state):
        fresh_state.advance(Phase.RISK)
        fresh_state.advance(Phase.TEST_DESIGN)
        fresh_state.advance(Phase.TEST_CODE)
        fresh_state.advance(Phase.FEATURE_CODE)
        fresh_state.advance(Phase.EXECUTION)

        fresh_state.add_feedback(FeedbackEvent(
            test_id="TC-R1-001",
            failure_type="feature_bug",
            detail="assertion failed",
            target_phase=Phase.FEATURE_CODE,
        ))
        fresh_state.advance(Phase.FEATURE_CODE)
        assert fresh_state.phase == Phase.FEATURE_CODE

    def test_mark_failed_sets_terminal_phase(self, fresh_state):
        fresh_state.mark_failed("something exploded")
        assert fresh_state.phase == Phase.FAILED

    def test_mark_failed_appends_to_errors(self, fresh_state):
        fresh_state.mark_failed("fatal error")
        assert any("fatal error" in e for e in fresh_state.errors)


# ---------------------------------------------------------------------------
# PipelineState — retry policy
# ---------------------------------------------------------------------------

class TestRetryPolicy:

    def test_increment_retry_returns_true_within_budget(self, fresh_state):
        fresh_state.max_retries = 3
        assert fresh_state.increment_retry() is True   # 1
        assert fresh_state.increment_retry() is True   # 2
        assert fresh_state.increment_retry() is True   # 3

    def test_increment_retry_returns_false_when_exceeded(self, fresh_state):
        fresh_state.max_retries = 2
        fresh_state.increment_retry()   # 1
        fresh_state.increment_retry()   # 2
        result = fresh_state.increment_retry()           # 3 > max
        assert result is False

    def test_record_error_is_non_fatal(self, fresh_state):
        fresh_state.record_error("non-fatal warning")
        assert fresh_state.phase != Phase.FAILED
        assert len(fresh_state.errors) == 1


# ---------------------------------------------------------------------------
# PipelineState — feedback API
# ---------------------------------------------------------------------------

class TestFeedbackAPI:

    def test_add_and_consume_feedback(self, fresh_state):
        ev = FeedbackEvent("TC-001", "test_bug", "bad assert", Phase.TEST_CODE)
        fresh_state.add_feedback(ev)
        consumed = fresh_state.consume_feedback("test_bug")
        assert len(consumed) == 1
        assert consumed[0].test_id == "TC-001"

    def test_consume_leaves_other_types_intact(self, fresh_state):
        fresh_state.add_feedback(FeedbackEvent("TC-001", "test_bug", "", Phase.TEST_CODE))
        fresh_state.add_feedback(FeedbackEvent("TC-002", "feature_bug", "", Phase.FEATURE_CODE))
        fresh_state.consume_feedback("test_bug")
        assert len(fresh_state.feedback) == 1
        assert fresh_state.feedback[0].failure_type == "feature_bug"

    def test_consume_nonexistent_type_returns_empty(self, fresh_state):
        result = fresh_state.consume_feedback("new_risk")
        assert result == []


# ---------------------------------------------------------------------------
# PipelineState — persistence
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_save_creates_json_file(self, fresh_state, tmp_path):
        path = tmp_path / "state" / "run.json"
        fresh_state.save(path)
        assert path.exists()

    def test_load_restores_phase(self, fresh_state, tmp_path):
        path = tmp_path / "state.json"
        fresh_state.advance(Phase.RISK)
        fresh_state.save(path)
        restored = PipelineState.load(path)
        assert restored.phase == Phase.RISK

    def test_load_restores_artifacts(self, fresh_state, tmp_path):
        path = tmp_path / "state.json"
        fresh_state.set_artifact(ArtifactKey.REQUIREMENTS, ["req-a"])
        fresh_state.save(path)
        restored = PipelineState.load(path)
        assert restored.artifacts[ArtifactKey.REQUIREMENTS.value] == ["req-a"]

    def test_load_restores_feedback(self, fresh_state, tmp_path):
        path = tmp_path / "state.json"
        fresh_state.add_feedback(
            FeedbackEvent("TC-002", "feature_bug", "broken", Phase.FEATURE_CODE)
        )
        fresh_state.save(path)
        restored = PipelineState.load(path)
        assert len(restored.feedback) == 1
        assert restored.feedback[0].failure_type == "feature_bug"

    def test_save_load_roundtrip_preserves_run_id(self, fresh_state, tmp_path):
        path = tmp_path / "state.json"
        original_id = fresh_state.run_id
        fresh_state.save(path)
        restored = PipelineState.load(path)
        assert restored.run_id == original_id


# ---------------------------------------------------------------------------
# Orchestrator — happy path
# ---------------------------------------------------------------------------

class TestOrchestratorHappyPath:

    def test_run_completes_all_phases(self, orchestrator, all_mock_agents):
        state = orchestrator.run(scope="my-project/")
        assert state.phase == Phase.DONE

    def test_all_agents_called_once(self, orchestrator, all_mock_agents):
        orchestrator.run(scope="my-project/")
        for agent in all_mock_agents.values():
            agent.run.assert_called_once()

    def test_state_persisted_after_each_phase(self, orchestrator, tmp_path):
        orchestrator.run(scope="my-project/")
        saved = list((tmp_path / "state").glob("*.json"))
        assert len(saved) == 1                # one file, updated per phase


# ---------------------------------------------------------------------------
# Orchestrator — retry behaviour
# ---------------------------------------------------------------------------

class TestOrchestratorRetry:

    def test_agent_exception_triggers_retry(self, all_mock_agents, tmp_path):
        call_count = {"n": 0}
        def flaky_run(state):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("transient error")
        all_mock_agents["analyst"].run.side_effect = flaky_run

        orc = Orchestrator(state_dir=tmp_path / "state", max_retries=3, **all_mock_agents)
        state = orc.run("proj/")
        assert state.phase == Phase.DONE
        assert call_count["n"] == 3

    def test_exhausting_retries_marks_failed(self, all_mock_agents, tmp_path):
        all_mock_agents["analyst"].run.side_effect = RuntimeError("always fails")
        orc = Orchestrator(state_dir=tmp_path / "state", max_retries=2, **all_mock_agents)
        state = orc.run("proj/")
        assert state.phase == Phase.FAILED


# ---------------------------------------------------------------------------
# Orchestrator — feedback routing
# ---------------------------------------------------------------------------

class TestOrchestratorFeedbackRouting:

    def _make_executor_with_feedback(self, failure_type: str, target: Phase, all_mock_agents):
        """
        Returns an executor that on first call adds one FeedbackEvent,
        on second call does nothing (simulating the fix worked).
        """
        calls = {"n": 0}
        def executor_run(state):
            calls["n"] += 1
            if calls["n"] == 1:
                state.add_feedback(FeedbackEvent(
                    test_id="TC-R1-001",
                    failure_type=failure_type,
                    detail="simulated failure",
                    target_phase=target,
                ))
        all_mock_agents["test_executor"].run.side_effect = executor_run

    def test_feature_bug_rewinds_to_feature_implementer(self, all_mock_agents, tmp_path):
        self._make_executor_with_feedback("feature_bug", Phase.FEATURE_CODE, all_mock_agents)
        orc = Orchestrator(state_dir=tmp_path / "state", **all_mock_agents)
        state = orc.run("proj/")
        assert state.phase == Phase.DONE
        # Feature implementer should have been called twice (once + after rewind)
        assert all_mock_agents["feature_implementer"].run.call_count == 2

    def test_new_risk_rewinds_to_risk_analyst(self, all_mock_agents, tmp_path):
        self._make_executor_with_feedback("new_risk", Phase.RISK, all_mock_agents)
        orc = Orchestrator(state_dir=tmp_path / "state", **all_mock_agents)
        state = orc.run("proj/")
        assert state.phase == Phase.DONE
        # Risk analyst called twice; downstream agents also re-run
        assert all_mock_agents["risk_analyst"].run.call_count == 2
