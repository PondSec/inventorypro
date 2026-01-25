"""Ollama client utilities for PondSec AI."""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    def __init__(self, message: str, kind: str = "unknown") -> None:
        super().__init__(message)
        self.kind = kind


def ollama_provider() -> str:
    return os.environ.get("PONDSEC_AI_LLM_PROVIDER", "ollama").strip().lower()


def ollama_url() -> str:
    return os.environ.get("PONDSEC_AI_OLLAMA_URL", "http://localhost:11434").strip()


def ollama_model() -> str:
    return os.environ.get("PONDSEC_AI_OLLAMA_MODEL", "mistral").strip()


def ollama_timeout_seconds() -> int:
    try:
        return int(os.environ.get("PONDSEC_AI_LLM_TIMEOUT_SECONDS", "30"))
    except ValueError:
        return 30


def ollama_max_tokens() -> int:
    try:
        return int(os.environ.get("PONDSEC_AI_LLM_MAX_TOKENS", "256"))
    except ValueError:
        return 256


def call_ollama(prompt: str, max_tokens: int, timeout: int) -> str:
    if not prompt:
        return ""
    payload = {
        "model": ollama_model(),
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.2,
        },
    }
    url = f"{ollama_url().rstrip('/')}/api/generate"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.Timeout as exc:
        logger.warning("pondsec_ai.ollama.timeout")
        raise OllamaError("ollama_timeout", kind="timeout") from exc
    except requests.RequestException as exc:
        logger.warning("pondsec_ai.ollama.connection_error")
        raise OllamaError("ollama_connection_error", kind="connection") from exc
    if response.status_code != 200:
        logger.warning("pondsec_ai.ollama.bad_status status=%s", response.status_code)
        raise OllamaError("ollama_bad_status", kind="response")
    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("pondsec_ai.ollama.invalid_json")
        raise OllamaError("ollama_invalid_json", kind="response") from exc
    text = data.get("response")
    if not isinstance(text, str):
        raise OllamaError("ollama_missing_response", kind="response")
    return text.strip()


def ping_ollama(timeout: float = 2.0) -> bool:
    url = f"{ollama_url().rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return False
    return response.status_code == 200


def ollama_settings() -> dict:
    return {
        "provider": ollama_provider(),
        "url": ollama_url(),
        "model": ollama_model(),
        "timeout": ollama_timeout_seconds(),
        "max_tokens": ollama_max_tokens(),
    }
