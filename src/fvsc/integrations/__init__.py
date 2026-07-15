"""Third-party integrations.."""
"""Optional local/external adapters around the FVSC core contracts."""

from .ollama import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    OLLAMA_PROMPT_VERSION,
    OllamaGenerationTelemetry,
    OllamaIntegrationError,
    OllamaInterpretationBackend,
    OllamaModelIdentity,
)

__all__ = [
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_MODEL",
    "OLLAMA_PROMPT_VERSION",
    "OllamaGenerationTelemetry",
    "OllamaIntegrationError",
    "OllamaInterpretationBackend",
    "OllamaModelIdentity",
]
