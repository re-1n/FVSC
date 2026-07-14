"""Third-party integrations.."""
"""Optional local/external adapters around the FVSC core contracts."""

from .ollama import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    OLLAMA_PROMPT_VERSION,
    OllamaIntegrationError,
    OllamaInterpretationBackend,
)

__all__ = [
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_MODEL",
    "OLLAMA_PROMPT_VERSION",
    "OllamaIntegrationError",
    "OllamaInterpretationBackend",
]
