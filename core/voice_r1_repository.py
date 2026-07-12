"""Operational R1 repository extensions for retention and ASR retries.

The base ``VoiceRepository`` owns deterministic decoding, VAD and candidate
revision mechanics. This subclass adds lifecycle behaviour that depends on wall
clock time while keeping immutable artifact payloads unchanged.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from .voice_artifacts import TranscriptArtifact, VoiceEvidenceCandidate
from .voice_ingest import (
    ASRBackend,
    VoiceIngestError,
    VoiceRepository,
    _normalize_transcript,
)


_RETENTION_SECONDS = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}


class R1VoiceRepository(VoiceRepository):
    """Voice repository with enforced retention and reprocessing support."""

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        vault_path: Path | str | None = None,
        asr_backend: ASRBackend | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            root,
            vault_path=vault_path,
            asr_backend=asr_backend,
            **kwargs,
        )
        self.enforce_retention()

    def import_audio(
        self,
        data: bytes,
        *,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        source_hash = hashlib.sha256(bytes(data)).hexdigest()
        try:
            result = super().import_audio(data, **kwargs)
        except Exception as exc:
            # The base importer creates the capture record only after successful
            # decoding and VAD. If ASR or derived-artifact creation then fails, keep
            # that source indexed and retryable instead of leaving an orphaned file.
            capture_id = next(
                (
                    item_id
                    for item_id, item in self._data["captures"].items()
                    if item.get("artifact", {}).get("source_hash") == source_hash
                ),
                None,
            )
            if capture_id is None:
                raise
            record = self._data["captures"][capture_id]
            record["status"] = "failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["session_id"] = str(session_id).strip() if session_id else None
            record["audio_present"] = record.get("audio_deleted_at") is None
            self._save()
            return {
                "capture": self.get_capture(capture_id),
                "candidates": [],
                "asr_available": self.asr_available,
                "retriable": True,
            }

        capture_id = result["capture"]["artifact"]["capture_id"]
        record = self._data["captures"][capture_id]
        record["session_id"] = str(session_id).strip() if session_id else None
        record["audio_present"] = record.get("audio_deleted_at") is None
        self._save()
        result["capture"] = self.get_capture(capture_id)
        self.enforce_retention()
        return result

    def _latest_candidates_for_capture(self, capture_id: str) -> list[dict[str, Any]]:
        transcript_ids = {
            transcript_id
            for transcript_id, transcript in self._data["transcripts"].items()
            if transcript.get("capture_id") == capture_id
        }
        return [
            record
            for record in self._data["candidates"].values()
            if record.get("superseded_by") is None
            and record.get("artifact", {}).get("transcript_id") in transcript_ids
        ]

    def _ephemeral_can_delete(self, capture_id: str, record: dict[str, Any]) -> bool:
        candidates = self._latest_candidates_for_capture(capture_id)
        if candidates:
            return all(
                candidate["artifact"].get("promotion_state") in {"promoted", "discarded"}
                for candidate in candidates
            )
        # A failed or empty ASR result must retain the only source for retry and
        # diagnostics. Pure silence may be safely discarded without review.
        return record.get("status") == "no_speech"

    def enforce_retention(self, *, now: float | None = None) -> list[str]:
        current = float(time.time() if now is None else now)
        deleted: list[str] = []
        for capture_id, record in sorted(self._data["captures"].items()):
            if record.get("audio_deleted_at") is not None:
                continue
            artifact = record.get("artifact", {})
            retention = artifact.get("retention_class", "24h")
            should_delete = False
            if retention == "ephemeral":
                should_delete = self._ephemeral_can_delete(capture_id, record)
            elif retention in _RETENTION_SECONDS:
                created_at = float(record.get("created_at", artifact.get("ended_at", current)))
                should_delete = current >= created_at + _RETENTION_SECONDS[retention]
            elif retention == "keep":
                should_delete = False
            if should_delete:
                self._delete_audio_file(capture_id, deleted_at=current)
                deleted.append(capture_id)
        if deleted:
            self._save()
        return deleted

    def _delete_audio_file(self, capture_id: str, *, deleted_at: float) -> dict[str, Any]:
        record = self._data["captures"].get(str(capture_id).strip())
        if record is None:
            raise KeyError("voice capture not found")
        artifact = record["artifact"]
        storage_ref = artifact.get("storage_ref")
        if storage_ref:
            path = (self.root / storage_ref).resolve()
            try:
                path.relative_to(self.root)
            except ValueError as exc:
                raise VoiceIngestError("stored audio path escaped the voice directory") from exc
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        # The content-addressed artifact remains byte-for-byte intact. Deletion is
        # a lifecycle fact on the surrounding record, not a mutation of source data.
        record["audio_deleted_at"] = float(deleted_at)
        record["audio_present"] = False
        return self.get_capture(capture_id)

    def delete_audio(self, capture_id: str) -> dict[str, Any]:
        result = self._delete_audio_file(capture_id, deleted_at=time.time())
        self._save()
        return result

    def transcribe_capture(
        self,
        capture_id: str,
        *,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Create derived transcripts without changing the source capture ID."""
        if not self.asr_available:
            raise VoiceIngestError(
                "local ASR is not installed; install requirements-voice.txt"
            )
        record = self._data["captures"].get(str(capture_id).strip())
        if record is None:
            raise KeyError("voice capture not found")
        if record.get("audio_deleted_at") is not None:
            raise VoiceIngestError("raw audio was deleted and cannot be re-transcribed")
        artifact = record["artifact"]
        storage_ref = artifact.get("storage_ref")
        if not storage_ref:
            raise VoiceIngestError("capture has no retained audio reference")
        path = (self.root / storage_ref).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise VoiceIngestError("stored audio path escaped the voice directory") from exc
        if not path.exists():
            raise VoiceIngestError("retained audio file is missing")

        metadata = json.loads(artifact.get("metadata_json", "{}"))
        requested_language = language or metadata.get("language_requested")
        decoder = self._decoder_for(path)
        decoded = decoder.decode(path)
        regions = self.vad.detect(decoded)
        if not regions:
            record["status"] = "no_speech"
            record["error"] = None
            self._save()
            self.enforce_retention()
            return {
                "capture": self.get_capture(capture_id),
                "candidates": [],
                "asr_available": True,
            }

        try:
            results = self.asr_backend.transcribe(
                path,
                language=requested_language,
                regions=regions,
            )
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["audio_present"] = True
            self._save()
            raise VoiceIngestError(f"ASR retry failed: {exc}") from exc

        candidates: list[dict[str, Any]] = []
        for index, result in enumerate(results):
            normalized = _normalize_transcript(result.text)
            if not normalized:
                continue
            transcript = TranscriptArtifact.create(
                capture_id=capture_id,
                utterance_id=f"{capture_id[:16]}-{index:04d}",
                start_seconds=result.start_seconds,
                end_seconds=result.end_seconds,
                text_raw=result.text,
                text_normalized=normalized,
                asr_backend=self.asr_backend.backend_id,
                model_id=self.asr_backend.model_id,
                speaker_attribution=(
                    "declared_owner" if artifact["declared_owner_only"] else "uncertain"
                ),
                confidence=result.confidence,
                speaker_confidence=None,
                corrected=False,
                metadata={
                    "language": result.language,
                    "retry_language_requested": requested_language,
                },
            )
            candidate = VoiceEvidenceCandidate.create(
                transcript_id=transcript.transcript_id,
                capture_mode=artifact["mode"],
                evidence_mode=artifact["evidence_mode"],
                speaker_attribution=transcript.speaker_attribution,
                transcript_confidence=transcript.confidence,
                speaker_confidence=transcript.speaker_confidence,
            )
            self._data["transcripts"][transcript.transcript_id] = asdict(transcript)
            self._data["candidates"][candidate.candidate_id] = {
                "artifact": asdict(candidate),
                "created_at": time.time(),
                "superseded_by": None,
                "source_id": None,
            }
            candidates.append(self.candidate_payload(candidate.candidate_id))

        record["status"] = "ready" if candidates else "no_transcript"
        record["error"] = None
        record["audio_present"] = True
        record["last_transcribed_at"] = time.time()
        record["last_asr_backend"] = self.asr_backend.backend_id
        record["last_asr_model"] = self.asr_backend.model_id
        self._save()
        return {
            "capture": self.get_capture(capture_id),
            "candidates": candidates,
            "asr_available": True,
        }

    def status(self) -> dict[str, Any]:
        self.enforce_retention()
        payload = super().status()
        payload.update(
            {
                "audio_present_count": sum(
                    record.get("audio_deleted_at") is None
                    for record in self._data["captures"].values()
                ),
                "failed_capture_count": sum(
                    record.get("status") == "failed"
                    for record in self._data["captures"].values()
                ),
                "retention_enforced": True,
            }
        )
        return payload
