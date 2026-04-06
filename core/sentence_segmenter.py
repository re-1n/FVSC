# -*- coding: utf-8 -*-
"""
FVSC Sentence Segmenter — L1 preprocessor for unpunctuated chat text.

Uses WTSplit/SaT (Segment any Text) to detect sentence boundaries
in text that lacks punctuation. Inserted BEFORE the normalizer:

    raw text → segment_sentences() → per-sentence: normalize_text() → spaCy → ...

L1 (inference-level): neural model, deterministic at inference.
Temporary: will be replaced when T11 (morphological core) handles
clause boundaries via pymorphy2 + case grammar.

Graceful degradation: if wtpsplit is not installed, falls back to
newline splitting (preserving pre-SaT behavior).
"""

import os
from typing import Optional

# ---------------------------------------------------------------------------
# Lazy singleton (same pattern as text_normalizer._get_spellchecker)
# ---------------------------------------------------------------------------

_sat_model = None
_sat_available: Optional[bool] = None


def _get_sat_model():
    """Lazy-load SaT model. Cached as module-level singleton."""
    global _sat_model, _sat_available
    if _sat_available is False:
        return None
    if _sat_model is not None:
        return _sat_model
    try:
        from wtpsplit import SaT
        model_name = os.environ.get("FVSC_SAT_MODEL", "sat-3l-sm")
        _sat_model = SaT(model_name)
        _sat_available = True
        return _sat_model
    except ImportError:
        _sat_available = False
        return None


# ---------------------------------------------------------------------------
# Subordinate clause markers — prevent splitting inside modal envelopes
# ---------------------------------------------------------------------------

_SUBORDINATE_PREFIXES = (
    "что ", "чтобы ", "чтоб ", "как ", "будто ", "словно ",
    "который ", "которая ", "которое ", "которые ",
    "которого ", "которой ", "которому ", "которым ", "которых ",
)


def _remerge_subordinates(segments: list[str]) -> list[str]:
    """Re-merge segments that start with subordinate conjunctions.

    Prevents SaT from splitting "я думаю | что свобода важна" into
    two segments, which would break modal envelope detection in
    tree_extractor.
    """
    if len(segments) <= 1:
        return segments
    result = [segments[0]]
    for seg in segments[1:]:
        lower = seg.lower().lstrip()
        if any(lower.startswith(p) for p in _SUBORDINATE_PREFIXES):
            result[-1] = result[-1] + " " + seg
        else:
            result.append(seg)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

MIN_SEGMENT_LENGTH = 5  # skip trivially short segments ("да", "ну")


def segment_sentences(text: str) -> list[str]:
    """Split a text block into individual sentences.

    Uses SaT for punctuation-agnostic boundary detection.
    Falls back to newline splitting if wtpsplit is not installed.

    Args:
        text: Raw text block, possibly multi-sentence without punctuation.
    Returns:
        List of sentence strings (non-empty, stripped).
    """
    if not text or not text.strip():
        return []

    model = _get_sat_model()
    if model is None:
        # Fallback: split on newlines (old behavior)
        return [s.strip() for s in text.split("\n") if s.strip()]

    segments = model.split(text)
    segments = [s.strip() for s in segments if s.strip()]
    segments = _remerge_subordinates(segments)
    segments = [s for s in segments if len(s) >= MIN_SEGMENT_LENGTH]

    return segments if segments else [text.strip()]


def segment_and_flatten(
    texts: list[str],
    timestamps: Optional[list[float]] = None,
) -> tuple[list[str], Optional[list[float]]]:
    """Segment text blocks and expand timestamps to match.

    Each text block is split into sentences. If timestamps are provided,
    each timestamp is replicated for all sentences from its block.

    Args:
        texts: List of text blocks (e.g., merged Telegram messages).
        timestamps: Parallel list of epoch timestamps (or None).
    Returns:
        (flat_sentences, expanded_timestamps)
    """
    flat_sentences = []
    flat_timestamps = [] if timestamps is not None else None

    for i, text in enumerate(texts):
        sentences = segment_sentences(text)
        flat_sentences.extend(sentences)
        if flat_timestamps is not None and timestamps:
            ts = timestamps[i] if i < len(timestamps) else 0.0
            flat_timestamps.extend([ts] * len(sentences))

    return flat_sentences, flat_timestamps
