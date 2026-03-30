#!/usr/bin/env python3
"""
main.py
-------
Entry point for the QA pipeline.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from orchestrator import Orchestrator
from pipeline_state import ArtifactKey
from agents import (
    AnalystAgent,
    RiskAnalystAgent,
    TestDesignerAgent,
    TestCoderAgent,
    FeatureImplementerAgent,
    TestExecutorAgent,
    ReporterAgent,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QA pipeline")
    parser.add_argument(
        "--scope",
        type=str,
        required=True,
        help="Root path of codebase to analyze",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama3",
        help="LLM model to use (default: llama3)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="ollama",
        choices=["ollama", "anthropic", "openai"],
        help="LLM provider (default: ollama)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="Custom base URL for LLM provider",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key for cloud LLM providers",
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="Path to saved pipeline state to resume",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(".pipeline_state"),
        help="Directory for state persistence (default: .pipeline_state)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries per phase (default: 3)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting QA pipeline")
    logger.info("Scope: %s", args.scope)
    logger.info("LLM: %s/%s", args.provider, args.model)

    # Create agents
    common_kwargs = dict(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    )

    analyst = AnalystAgent(**common_kwargs)
    risk_analyst = RiskAnalystAgent(**common_kwargs)
    test_designer = TestDesignerAgent(**common_kwargs)
    test_coder = TestCoderAgent(**common_kwargs)
    feature_implementer = FeatureImplementerAgent(**common_kwargs)
    test_executor = TestExecutorAgent(**common_kwargs)
    reporter = ReporterAgent(**common_kwargs)

    # Create orchestrator
    orchestrator = Orchestrator(
        analyst=analyst,
        risk_analyst=risk_analyst,
        test_designer=test_designer,
        test_coder=test_coder,
        feature_implementer=feature_implementer,
        test_executor=test_executor,
        reporter=reporter,
        state_dir=args.state_dir,
        max_retries=args.max_retries,
    )

    # Run pipeline
    state = orchestrator.run(
        scope=args.scope,
        resume_from=args.resume_from,
    )

    # Report results
    if state.phase.name == "DONE":
        logger.info("Pipeline completed successfully")
        report_path = state.get_artifact(ArtifactKey.REPORT_PATH)
        logger.info("Report: %s", report_path)
    else:
        logger.error("Pipeline failed at phase: %s", state.phase.name)
        logger.error(state.summary())
        exit(1)


if __name__ == "__main__":
    main()