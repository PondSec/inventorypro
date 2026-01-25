"""Isolated local LLM worker process."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _provider_name() -> str:
    return os.environ.get("PONDSEC_AI_LLM_PROVIDER", "gpt4all").strip().lower()


def _max_tokens() -> int:
    try:
        return int(os.environ.get("PONDSEC_AI_LLM_MAX_TOKENS", "128"))
    except ValueError:
        return 128


def _resolve_model_path() -> Tuple[Optional[str], Optional[str]]:
    model_path = os.environ.get("PONDSEC_AI_LLM_MODEL_PATH")
    model_name = os.environ.get("PONDSEC_AI_LLM_MODEL_NAME")
    if not model_name:
        model_name = "mistral-7b-instruct-v0.2.Q4_K_S.gguf"
    if model_path:
        path = Path(model_path).expanduser()
        if path.exists():
            return path.name, str(path.parent)
        return None, None
    model_name_path = Path(model_name).expanduser()
    if model_name_path.parent != Path(".") and model_name_path.exists():
        return model_name_path.name, str(model_name_path.parent)
    candidate_paths = [
        Path("./models").expanduser() / model_name,
        Path.home() / ".cache" / "gpt4all" / model_name,
        Path.home() / ".cache" / "llama" / model_name,
    ]
    for path in candidate_paths:
        if path.exists():
            return path.name, str(path.parent)
    return None, None


def _load_model():
    provider = _provider_name()
    model_name, model_dir = _resolve_model_path()
    if not model_name or not model_dir:
        raise RuntimeError("Local LLM model not configured")
    logger.info("LLM model path resolved to %s", str(Path(model_dir).resolve() / model_name))
    if provider == "gpt4all":
        from gpt4all import GPT4All

        model = GPT4All(model_name, model_path=model_dir)
    elif provider in {"llamacpp", "llama-cpp"}:
        from llama_cpp import Llama

        model = Llama(model_path=str(Path(model_dir) / model_name))
    else:
        raise RuntimeError(f"Unknown LLM provider: {provider}")
    return model, provider


def _coerce_max_tokens(value: object) -> int:
    if value is None:
        return _max_tokens()
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return _max_tokens()
    if parsed <= 0:
        return _max_tokens()
    return parsed


def _generate(model, provider: str, prompt: str, max_tokens: int) -> str:
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


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.write("\n")
    sys.stdout.flush()


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    model = None
    provider = ""
    load_error: Optional[str] = None
    start_load = time.monotonic()
    try:
        model, provider = _load_model()
        elapsed = time.monotonic() - start_load
        logger.info("LLM model loaded in %.2f seconds", elapsed)
    except Exception as exc:  # pragma: no cover - logged for runtime visibility
        load_error = str(exc)
        logger.exception("LLM model failed to load")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request_id = "unknown"
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            _emit({"id": request_id, "error": "invalid_json"})
            continue
        request_id = request.get("id") or "unknown"
        prompt = request.get("prompt") or ""
        max_tokens = _coerce_max_tokens(request.get("max_tokens"))
        start = time.monotonic()
        try:
            if load_error:
                raise RuntimeError(load_error)
            text = _generate(model, provider, prompt, max_tokens)
            elapsed = time.monotonic() - start
            logger.info("LLM generate took %.2f seconds", elapsed)
            _emit({"id": request_id, "text": text})
        except Exception as exc:  # pragma: no cover - runtime safety
            elapsed = time.monotonic() - start
            logger.exception("LLM generate failed")
            logger.info("LLM generate took %.2f seconds", elapsed)
            _emit({"id": request_id, "error": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
