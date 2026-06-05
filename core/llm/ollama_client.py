"""
OllamaClient — talks to a local Ollama daemon at http://localhost:11434.

Uses stdlib urllib only, no new deps.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Iterable, Iterator

from .client import ChatMessage


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"


class OllamaClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        temperature: float = 0.4,
        num_ctx: int = 8192,
        timeout: float = 600.0,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout

    # ---------- introspection ----------

    def list_local_models(self) -> list[str]:
        """List models already pulled to the daemon."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5) as r:
                data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            return []

    def ping(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=2) as r:
                r.read()
            return True
        except Exception:
            return False

    # ---------- chat ----------

    def chat(self, messages: list[ChatMessage], stream: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {e.code}: {err_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Cannot reach Ollama at {self.host}. "
                f"Is the daemon running? ({e.reason})"
            ) from e

        if not stream:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "")

        # Streaming: Ollama returns one JSON line per token chunk.
        chunks: list[str] = []
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            tok = obj.get("message", {}).get("content", "")
            if tok:
                sys.stdout.write(tok)
                sys.stdout.flush()
                chunks.append(tok)
            if obj.get("done"):
                break
        sys.stdout.write("\n")
        return "".join(chunks)

    def chat_stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        """Generator variant — yields token chunks as they arrive, no stdout.

        Same wire protocol as chat(stream=True), but pure generator for use in
        SSE endpoints or programmatic streaming.
        """
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {e.code}: {err_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Cannot reach Ollama at {self.host} ({e.reason})"
            ) from e

        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            tok = obj.get("message", {}).get("content", "")
            if tok:
                yield tok
            if obj.get("done"):
                break
