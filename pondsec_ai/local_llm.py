"""Local LLM adapter for PondSec AI."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class LocalLLM:
    _model = None
    _provider = None
    _model_path = None

    @staticmethod
    def _provider_name() -> str:
        return os.environ.get("PONDSEC_AI_LLM_PROVIDER", "gpt4all").strip().lower()

    @staticmethod
    def _max_tokens() -> int:
        try:
            return int(os.environ.get("PONDSEC_AI_LLM_MAX_TOKENS", "512"))
        except ValueError:
            return 512

    @staticmethod
    def _resolve_model_path() -> Tuple[Optional[str], Optional[str]]:
        model_path = os.environ.get("PONDSEC_AI_LLM_MODEL_PATH")
        model_name = os.environ.get("PONDSEC_AI_LLM_MODEL_NAME")
        if model_path:
            path = Path(model_path).expanduser()
            if path.exists():
                return path.name, str(path.parent)
            return None, None
        if not model_name:
            return None, None
        candidate_paths = [
            Path("./models").expanduser() / model_name,
            Path.home() / ".cache" / "gpt4all" / model_name,
            Path.home() / ".cache" / "llama" / model_name,
        ]
        for path in candidate_paths:
            if path.exists():
                return path.name, str(path.parent)
        return None, None

    @classmethod
    def is_available(cls) -> bool:
        provider = cls._provider_name()
        model_name, model_dir = cls._resolve_model_path()
        if not model_name or not model_dir:
            return False
        try:
            if provider == "gpt4all":
                import gpt4all  # noqa: F401
            elif provider in {"llamacpp", "llama-cpp"}:
                import llama_cpp  # noqa: F401
            else:
                return False
        except Exception:
            return False
        return True

    @classmethod
    def status(cls) -> str:
        provider = cls._provider_name()
        model_name, model_dir = cls._resolve_model_path()
        if not model_name or not model_dir:
            return "Local LLM: missing model"
        if provider not in {"gpt4all", "llamacpp", "llama-cpp"}:
            return f"Local LLM: unknown provider ({provider})"
        try:
            if provider == "gpt4all":
                import gpt4all  # noqa: F401
            else:
                import llama_cpp  # noqa: F401
        except Exception:
            return f"Local LLM: provider '{provider}' not installed"
        return f"Local LLM: ready ({provider})"

    @classmethod
    def _load_model(cls):
        if cls._model is not None:
            return cls._model
        provider = cls._provider_name()
        model_name, model_dir = cls._resolve_model_path()
        if not model_name or not model_dir:
            raise RuntimeError("Local LLM model not configured")
        if provider == "gpt4all":
            from gpt4all import GPT4All

            cls._model = GPT4All(model_name, model_path=model_dir)
        elif provider in {"llamacpp", "llama-cpp"}:
            from llama_cpp import Llama

            cls._model = Llama(model_path=str(Path(model_dir) / model_name))
        else:
            raise RuntimeError(f"Unknown LLM provider: {provider}")
        cls._provider = provider
        cls._model_path = str(Path(model_dir) / model_name)
        return cls._model

    @classmethod
    def generate(cls, prompt: str, max_tokens: int = 512) -> str:
        max_tokens = max_tokens or cls._max_tokens()
        if not prompt:
            return ""
        env = os.environ.copy()
        env["PONDSEC_AI_LLM_MAX_TOKENS"] = str(max_tokens)
        cmd = [sys.executable, "-m", "pondsec_ai.llm_worker"]
        logger.info("pondsec_ai.local_llm.worker_start provider=%s", cls._provider_name())
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=20,
                env=env,
            )
        except subprocess.TimeoutExpired:
            logger.warning("pondsec_ai.local_llm.worker_timeout")
            return ""
        if result.stderr:
            logger.warning("pondsec_ai.local_llm.worker_stderr=%s", result.stderr.strip())
        if result.returncode != 0:
            logger.warning("pondsec_ai.local_llm.worker_failed code=%s", result.returncode)
            return ""
        try:
            payload = json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError:
            logger.warning("pondsec_ai.local_llm.worker_invalid_json")
            return ""
        text = payload.get("text") or ""
        return text
