"""Local LLM adapter for PondSec AI."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple


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
        model = cls._load_model()
        provider = cls._provider_name()
        max_tokens = max_tokens or cls._max_tokens()
        if provider == "gpt4all":
            return model.generate(prompt, max_tokens=max_tokens) or ""
        if provider in {"llamacpp", "llama-cpp"}:
            output = model(
                prompt,
                max_tokens=max_tokens,
                temperature=0.2,
                stop=["\n\n"],
            )
            return output.get("choices", [{}])[0].get("text", "")
        raise RuntimeError(f"Unknown LLM provider: {provider}")
