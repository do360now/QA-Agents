"""
llm_client.py
-------------
Unified LLM client supporting multiple backends:
- Ollama (local models)
- Anthropic API
- OpenAI API
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base client interface
# ---------------------------------------------------------------------------

class LLMClientBase(ABC):
    """Abstract base for LLM clients."""

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Make an LLM completion request. Returns response text."""
        ...


# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------

class OllamaClient(LLMClientBase):
    """Client for Ollama local models."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        url = f"{self.base_url}/api/generate"

        payload: dict[str, Any] = {
            "model": self.model,
            "system": system,
            "prompt": user,
            "temperature": temperature,
            "stream": False,
        }

        if json_mode:
            payload["format"] = "json"

        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()
        return data.get("response", "")


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------

class AnthropicClient(LLMClientBase):
    """Client for Anthropic Claude API."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com",
    ) -> None:
        self.model = model
        self.api_key = api_key or self._get_api_key()
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _get_api_key() -> str:
        import os
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return key

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        url = f"{self.base_url}/v1/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": 4096,
        }

        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()

        data = response.json()
        return data.get("content", [{}])[0].get("text", "")


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

class OpenAIClient(LLMClientBase):
    """Client for OpenAI API."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.model = model
        self.api_key = api_key or self._get_api_key()
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _get_api_key() -> str:
        import os
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY not set")
        return key

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()

        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Unified client factory
# ---------------------------------------------------------------------------

def create_llm_client(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClientBase:
    """
    Factory to create an LLM client.

    Args:
        provider: "ollama", "anthropic", or "openai"
        model: Model name (e.g., "llama3", "claude-3-opus-20240229", "gpt-4")
        api_key: API key (optional, reads from env if not provided)
        base_url: Custom base URL (optional)

    Returns:
        An LLMClientBase implementation
    """
    provider = provider.lower()

    if provider == "ollama":
        return OllamaClient(model=model, base_url=base_url or "http://localhost:11434")
    elif provider == "anthropic":
        return AnthropicClient(model=model, api_key=api_key, base_url=base_url)
    elif provider == "openai":
        return OpenAIClient(model=model, api_key=api_key, base_url=base_url)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use: ollama, anthropic, openai")


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def parse_json_response(response: str) -> dict | list:
    """
    Parse JSON from LLM response. Handles common issues:
    - Response wrapped in markdown code blocks
    - Trailing text after JSON
    - Malformed JSON
    """
    # Strip markdown code blocks
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    response = response.strip()

    # Try direct parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in response
    start = response.find("{")
    if start == -1:
        start = response.find("[")

    if start != -1:
        # Find matching closing brace
        brace_count = 0
        in_string = False
        escape = False
        for i, char in enumerate(response[start:], start):
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if char in "{[":
                    brace_count += 1
                elif char in "}]":
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return json.loads(response[start:i+1])
                        except json.JSONDecodeError:
                            pass

    raise ValueError(f"Could not parse JSON from response: {response[:200]}...")