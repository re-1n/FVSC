"""Third-party integrations.."""
"""Optional local/external adapters around the FVSC core contracts."""

from .ollama import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_NUM_PREDICT,
    OLLAMA_PROMPT_VERSION,
    OllamaEmbeddingBackend,
    OllamaGenerationTelemetry,
    OllamaIntegrationError,
    OllamaInterpretationBackend,
    OllamaModelIdentity,
)

__all__ = [
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_NUM_PREDICT",
    "OLLAMA_PROMPT_VERSION",
    "OllamaEmbeddingBackend",
    "OllamaGenerationTelemetry",
    "OllamaIntegrationError",
    "OllamaInterpretationBackend",
    "OllamaModelIdentity",
]
