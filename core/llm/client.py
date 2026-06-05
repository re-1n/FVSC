"""
Minimal LLM client abstraction. One method: chat().
Concrete backends (OllamaClient, OpenRouterClient) implement it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class ChatMessage:
    role: str   # "system" | "user" | "assistant"
    content: str


class LLMClient(Protocol):
    """All backends conform to this interface."""

    model: str

    def chat(self, messages: list[ChatMessage], stream: bool = False) -> str:
        """Send messages, return the assistant reply as a single string.

        If stream=True, the implementation should print tokens to stdout
        as they arrive and return the full text at the end.
        """
        ...
