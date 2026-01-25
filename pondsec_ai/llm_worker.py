"""Isolated local LLM worker process."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple


def _provider_name() -> str:
    return os.environ.get("PONDSEC_AI_LLM_PROVIDER", "gpt4all").strip().lower()


def _max_tokens() -> int:
    try:
        return int(os.environ.get("PONDSEC_AI_LLM_MAX_TOKENS", "512"))
    except ValueError:
        return 512


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


def _generate(prompt: str) -> str:
    provider = _provider_name()
    model_name, model_dir = _resolve_model_path()
    if not model_name or not model_dir:
        raise RuntimeError("Local LLM model not configured")
    max_tokens = _max_tokens()
    if provider == "gpt4all":
        from gpt4all import GPT4All

        model = GPT4All(model_name, model_path=model_dir)
        return model.generate(prompt, max_tokens=max_tokens) or ""
    if provider in {"llamacpp", "llama-cpp"}:
        from llama_cpp import Llama

        model = Llama(model_path=str(Path(model_dir) / model_name))
        output = model(
            prompt,
            max_tokens=max_tokens,
            temperature=0.2,
            stop=["\n\n"],
        )
        return output.get("choices", [{}])[0].get("text", "")
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def main() -> int:
    prompt = sys.stdin.read()
    if not prompt:
        sys.stdout.write(json.dumps({"text": ""}))
        return 0
    try:
        text = _generate(prompt)
        sys.stdout.write(json.dumps({"text": text}))
        return 0
    except Exception as exc:
        sys.stderr.write(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
