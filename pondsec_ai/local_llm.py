"""Local LLM adapter for PondSec AI."""
from __future__ import annotations

import collections
import json
import logging
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid
from typing import Deque, Optional, Tuple

from .ollama_client import ping_ollama

logger = logging.getLogger(__name__)


class WorkerClient:
    _instance: Optional["WorkerClient"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen[str]] = None
        self._lock = threading.Lock()
        self._stdout_queue: Optional[queue.Queue[str]] = None
        self._stderr_buffer: Optional[Deque[str]] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

    @classmethod
    def instance(cls) -> "WorkerClient":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _start_worker(self) -> None:
        env = os.environ.copy()
        cmd = [sys.executable, "-m", "pondsec_ai.llm_worker"]
        logger.info("pondsec_ai.local_llm.worker_start provider=%s", LocalLLM._provider_name())
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._stdout_queue = queue.Queue()
        self._stderr_buffer = collections.deque(maxlen=20)
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _stop_worker(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._stdout_thread = None
        self._stderr_thread = None
        self._stdout_queue = None
        self._stderr_buffer = None

    def _ensure_worker(self) -> None:
        if self._process is None or self._process.poll() is not None:
            self._stop_worker()
            self._start_worker()

    def _read_stdout(self) -> None:
        if self._process is None or self._process.stdout is None or self._stdout_queue is None:
            return
        for line in self._process.stdout:
            self._stdout_queue.put(line)

    def _read_stderr(self) -> None:
        if self._process is None or self._process.stderr is None or self._stderr_buffer is None:
            return
        for line in self._process.stderr:
            self._stderr_buffer.append(line.rstrip())

    def _stderr_tail(self) -> str:
        if not self._stderr_buffer:
            return ""
        return " | ".join(list(self._stderr_buffer)[-5:])

    def _readline_with_timeout(self, timeout: float) -> Optional[str]:
        if self._stdout_queue is None:
            return None
        try:
            return self._stdout_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def request(self, prompt: str, max_tokens: int) -> dict:
        request_id = uuid.uuid4().hex
        payload = {"id": request_id, "prompt": prompt, "max_tokens": max_tokens}
        with self._lock:
            self._ensure_worker()
            if self._process is None or self._process.stdin is None or self._process.stdout is None:
                return {"id": request_id, "error": "worker_not_running"}
            try:
                self._process.stdin.write(json.dumps(payload) + "\n")
                self._process.stdin.flush()
            except BrokenPipeError:
                logger.warning("pondsec_ai.local_llm.worker_broken_pipe stderr_tail=%s", self._stderr_tail())
                self._stop_worker()
                return {"id": request_id, "error": "worker_broken_pipe"}
            timeout_seconds = LocalLLM._timeout_seconds()
            line = self._readline_with_timeout(timeout_seconds)
            if line is None:
                logger.warning("pondsec_ai.local_llm.worker_timeout stderr_tail=%s", self._stderr_tail())
                self._stop_worker()
                return {"id": request_id, "error": "timeout"}
            if not line:
                logger.warning("pondsec_ai.local_llm.worker_died stderr_tail=%s", self._stderr_tail())
                self._stop_worker()
                return {"id": request_id, "error": "worker_died"}
            try:
                response = json.loads(line.strip())
            except json.JSONDecodeError:
                logger.warning("pondsec_ai.local_llm.worker_invalid_json stderr_tail=%s", self._stderr_tail())
                return {"id": request_id, "error": "invalid_json"}
            if response.get("error"):
                logger.warning(
                    "pondsec_ai.local_llm.worker_error=%s stderr_tail=%s",
                    response.get("error"),
                    self._stderr_tail(),
                )
            return response


class LocalLLM:
    _model = None
    _provider = None
    _model_path = None

    @staticmethod
    def _provider_name() -> str:
        return os.environ.get("PONDSEC_AI_LLM_PROVIDER", "ollama").strip().lower()

    @staticmethod
    def _max_tokens() -> int:
        try:
            return int(os.environ.get("PONDSEC_AI_LLM_MAX_TOKENS", "256"))
        except ValueError:
            return 256

    @staticmethod
    def _timeout_seconds() -> float:
        try:
            return float(os.environ.get("PONDSEC_AI_LLM_TIMEOUT_SECONDS", "30"))
        except ValueError:
            return 30.0

    @staticmethod
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

    @classmethod
    def is_available(cls) -> bool:
        provider = cls._provider_name()
        if provider in {"ollama", "auto"}:
            return True
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
        if provider == "ollama":
            return "Ollama: reachable" if ping_ollama() else "Ollama: unreachable"
        if provider == "auto":
            return "Auto LLM: local/ollama fallback"
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
        logger.info("pondsec_ai.local_llm.model_path=%s", str(Path(model_dir).resolve() / model_name))
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
    def generate(cls, prompt: str, max_tokens: Optional[int] = None) -> str:
        max_tokens = max_tokens or cls._max_tokens()
        if not prompt:
            return ""
        client = WorkerClient.instance()
        response = client.request(prompt, max_tokens)
        error = response.get("error")
        if error:
            logger.warning("pondsec_ai.local_llm.worker_error=%s", error)
            return json.dumps({"error": error})
        text = response.get("text")
        if text is None:
            return json.dumps({"error": "empty_response"})
        return text
