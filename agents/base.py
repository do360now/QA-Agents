"""
agents/base.py
--------------
Base class for all QA pipeline agents.
Provides common LLM client, logging, and error handling.
"""

from __future__ import annotations

import logging
import re
from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING

from llm_client import LLMClientBase, create_llm_client, parse_json_response
from pipeline_state import PipelineState

if TYPE_CHECKING:
    from orchestrator import Agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    path = prompt_dir / f"{name}.txt"
    if path.exists():
        return path.read_text()
    return ""


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """
    Base class for all pipeline agents.

    Provides:
    - LLM client initialization
    - Logging
    - Common error handling
    - JSON response parsing with retry
    - File reading utilities
    """

    name: str = "BaseAgent"

    def __init__(
        self,
        llm_client: LLMClientBase | None = None,
        *,
        provider: str = "ollama",
        model: str = "llama3",
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the agent.

        Args:
            llm_client: Pre-configured LLM client. If not provided, creates one.
            provider: LLM provider (ollama, anthropic, openai)
            model: Model name
            api_key: API key (optional)
            base_url: Custom base URL (optional)
            max_retries: Max retries for LLM calls
        """
        self._llm = llm_client or create_llm_client(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        self._max_retries = max_retries
        self._logger = logging.getLogger(f"{__name__}.{self.name}")

    def run(self, state: PipelineState) -> None:
        """Execute the agent. Override in subclasses."""
        self._logger.info("[%s] Starting", self.name)
        try:
            self._execute(state)
        except Exception as exc:
            self._logger.exception("[%s] Failed: %s", self.name, exc)
            raise

    def _execute(self, state: PipelineState) -> None:
        """Override in subclasses to implement agent logic."""
        raise NotImplementedError("Subclasses must implement _execute")

    # ------------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------------

    def call_llm(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """
        Call the LLM with the given prompts.

        Args:
            system: System prompt
            user: User prompt
            json_mode: If True, expect JSON response
            temperature: Temperature setting

        Returns:
            LLM response text
        """
        for attempt in range(self._max_retries):
            try:
                response = self._llm.complete(
                    system=system,
                    user=user,
                    json_mode=json_mode,
                    temperature=temperature,
                )
                self._logger.debug("[%s] LLM response: %s", self.name, response[:200])
                return response
            except Exception as exc:
                self._logger.warning(
                    "[%s] LLM call failed (attempt %d/%d): %s",
                    self.name, attempt + 1, self._max_retries, exc,
                )
                if attempt == self._max_retries - 1:
                    raise

        raise RuntimeError("Should not reach here")

    def call_llm_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
    ) -> dict | list:
        """
        Call the LLM and parse JSON from response.

        Args:
            system: System prompt
            user: User prompt
            temperature: Temperature setting

        Returns:
            Parsed JSON (dict or list)
        """
        response = self.call_llm(system, user, json_mode=True, temperature=temperature)
        return parse_json_response(response)

    # ------------------------------------------------------------------------
    # File reading helpers
    # ------------------------------------------------------------------------

    def read_file(self, path: Path) -> str:
        """Read a file's contents. Fails loudly if not found."""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_text(encoding="utf-8")

    def read_files_in_dir(self, dir_path: Path, pattern: str = "*.py") -> dict[Path, str]:
        """
        Read all files matching pattern in directory.

        Returns:
            Dict mapping file path to contents
        """
        if not dir_path.exists():
            return {}

        files = {}
        for path in dir_path.rglob(pattern):
            # Skip common excluded directories
            if any(excluded in path.parts for excluded in (
                "__pycache__", ".git", "node_modules", "venv", ".env",
            )):
                continue
            try:
                files[path] = self.read_file(path)
            except Exception as exc:
                self._logger.warning("Failed to read %s: %s", path, exc)

        return files

    def truncate_for_llm(self, content: str, max_chars: int = 50000) -> str:
        """
        Truncate content if too long, preserving structure.
        """
        if len(content) <= max_chars:
            return content

        # Truncate and add note
        return content[:max_chars] + f"\n\n[... content truncated, {len(content) - max_chars} chars omitted ...]"

    # ------------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------------

    def log_summary(self, summary: str) -> None:
        """Log a summary of what the agent produced."""
        self._logger.info("[%s] %s", self.name, summary)