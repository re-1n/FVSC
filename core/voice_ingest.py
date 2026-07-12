"""Local-first R1 audio ingest, VAD, optional ASR and review persistence.

The module intentionally keeps source audio, ASR transcripts and semantic evidence
separate.  WAV decoding and an energy VAD baseline use only the Python standard
library plus NumPy.  PyAV and faster-whisper are optional local adapters; their
absence is reported as a capability gap rather than silently replaced by generated
text.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import tempfile
import time
from typing import Any, Mapping, Protocol, Sequence
import wave

import numpy as np

from .voice_artifacts import (
    AudioCaptureArtifact,
    TranscriptArtifact,
    VoiceEvidenceCandidate,
)


VOICE_INDEX_VERSION = 1
MAX_AUDIO_BYTES = 100 * 1024 * 1024
MAX_AUDIO_SECONDS = 2 * 60 * 60
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".webm"}


class VoiceIngestError(ValueError):
    """Expected validation or local backend error."""


@dataclass(frozen=True)
class DecodedAudio:
    samples: np.ndarray
    sample_rate: int
    source_channels: int

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            raise VoiceIngestError("audio contains no samples")
        if not np.isfinite(samples).all():
            raise VoiceIngestError("audio contains non-finite samples")
        if self.sample_rate < 1 or self.source_channels < 1:
            raise VoiceIngestError("invalid audio format")
        samples = np.clip(samples, -1.0, 1.0)
        samples.setflags(write=False)
        object.__setattr__(self, "samples", samples)

    @property
    def duration_seconds(self) -> float:
        return float(self.samples.size / self.sample_rate)


@dataclass(frozen=True)
class SpeechRegion:
    start_seconds: float
    end_seconds: float
    rms: float
    peak: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class ASRResult:
    start_seconds: float
    end_seconds: float
    text: str
    confidence: float | None = None
    language: str | None = None


class AudioDecoder(Protocol):
    backend_id: str

    def supports(self, path: Path) -> bool: ...
    def decode(self, path: Path) -> DecodedAudio: ...


class ASRBackend(Protocol):
    backend_id: str
    model_id: str

    @property
    def available(self) -> bool: ...

    def transcribe(
        self,
        path: Path,
        *,
        language: str | None,
        regions: Sequence[SpeechRegion],
    ) -> list[ASRResult]: ...


class WavPcmDecoder:
    backend_id = "stdlib-wave-pcm-v1"

    def supports(self, path: Path) -> bool:
        return path.suffix.casefold() == ".wav"

    def decode(self, path: Path) -> DecodedAudio:
        try:
            with wave.open(str(path), "rb") as handle:
                channels = handle.getnchannels()
                sample_rate = handle.getframerate()
                sample_width = handle.getsampwidth()
                frames = handle.readframes(handle.getnframes())
        except (wave.Error, OSError) as exc:
            raise VoiceIngestError(f"invalid WAV file: {exc}") from exc

        if sample_width == 1:
            raw = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
            values = (raw - 128.0) / 128.0
        elif sample_width == 2:
            values = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        elif sample_width == 3:
            octets = np.frombuffer(frames, dtype=np.uint8)
            if octets.size % 3:
                raise VoiceIngestError("invalid 24-bit WAV payload")
            triples = octets.reshape(-1, 3).astype(np.int32)
            signed = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
            signed = np.where(signed & 0x800000, signed - 0x1000000, signed)
            values = signed.astype(np.float32) / 8388608.0
        elif sample_width == 4:
            values = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise VoiceIngestError(f"unsupported WAV sample width: {sample_width}")

        if channels > 1:
            if values.size % channels:
                raise VoiceIngestError("WAV channel payload is truncated")
            values = values.reshape(-1, channels).mean(axis=1)
        return DecodedAudio(values, sample_rate, channels)


class PyAvDecoder:
    backend_id = "pyav-local-v1"

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("av") is not None

    def supports(self, path: Path) -> bool:
        return self.available and path.suffix.casefold() in ALLOWED_AUDIO_EXTENSIONS

    def decode(self, path: Path) -> DecodedAudio:
        if not self.available:
            raise VoiceIngestError("PyAV is not installed")
        try:
            import av  # type: ignore

            container = av.open(str(path))
            stream = next((item for item in container.streams if item.type == "audio"), None)
            if stream is None:
                raise VoiceIngestError("file contains no audio stream")
            sample_rate = int(stream.rate or 16000)
            source_channels = int(getattr(stream.codec_context, "channels", 1) or 1)
            chunks: list[np.ndarray] = []
            for frame in container.decode(stream):
                array = np.asarray(frame.to_ndarray())
                if array.ndim == 2:
                    # PyAV usually returns planar channels x samples.
                    axis = 0 if array.shape[0] <= 16 else 1
                    array = array.mean(axis=axis)
                array = array.reshape(-1)
                if np.issubdtype(array.dtype, np.integer):
                    info = np.iinfo(array.dtype)
                    scale = float(max(abs(info.min), info.max))
                    array = array.astype(np.float32) / scale
                else:
                    array = array.astype(np.float32)
                chunks.append(array)
            container.close()
        except VoiceIngestError:
            raise
        except Exception as exc:
            raise VoiceIngestError(f"cannot decode audio with PyAV: {exc}") from exc
        if not chunks:
            raise VoiceIngestError("audio decoder produced no samples")
        return DecodedAudio(np.concatenate(chunks), sample_rate, source_channels)


@dataclass(frozen=True)
class EnergyVadConfig:
    frame_ms: int = 30
    threshold_dbfs: float = -42.0
    min_speech_ms: int = 180
    min_silence_ms: int = 300
    padding_ms: int = 120


class EnergyVoiceActivityDetector:
    backend_id = "energy-vad-v1"

    def __init__(self, config: EnergyVadConfig | None = None) -> None:
        self.config = config or EnergyVadConfig()

    def detect(self, audio: DecodedAudio) -> list[SpeechRegion]:
        cfg = self.config
        frame_size = max(1, round(audio.sample_rate * cfg.frame_ms / 1000))
        samples = audio.samples
        frame_count = math.ceil(samples.size / frame_size)
        active: list[bool] = []
        frame_rms: list[float] = []
        for index in range(frame_count):
            frame = samples[index * frame_size : (index + 1) * frame_size]
            rms = float(np.sqrt(np.mean(np.square(frame), dtype=np.float64))) if frame.size else 0.0
            dbfs = 20.0 * math.log10(max(rms, 1e-12))
            frame_rms.append(rms)
            active.append(dbfs >= cfg.threshold_dbfs)

        min_speech_frames = max(1, math.ceil(cfg.min_speech_ms / cfg.frame_ms))
        max_gap_frames = max(0, math.floor(cfg.min_silence_ms / cfg.frame_ms))
        padding_frames = max(0, math.ceil(cfg.padding_ms / cfg.frame_ms))

        runs: list[tuple[int, int]] = []
        start: int | None = None
        last_active: int | None = None
        for index, is_active in enumerate(active):
            if is_active:
                if start is None:
                    start = index
                last_active = index
            elif start is not None and last_active is not None and index - last_active > max_gap_frames:
                if last_active - start + 1 >= min_speech_frames:
                    runs.append((start, last_active + 1))
                start = None
                last_active = None
        if start is not None and last_active is not None and last_active - start + 1 >= min_speech_frames:
            runs.append((start, last_active + 1))

        regions: list[SpeechRegion] = []
        for start_frame, end_frame in runs:
            padded_start = max(0, start_frame - padding_frames)
            padded_end = min(frame_count, end_frame + padding_frames)
            start_sample = padded_start * frame_size
            end_sample = min(samples.size, padded_end * frame_size)
            region = samples[start_sample:end_sample]
            regions.append(
                SpeechRegion(
                    start_seconds=float(start_sample / audio.sample_rate),
                    end_seconds=float(end_sample / audio.sample_rate),
                    rms=float(np.sqrt(np.mean(np.square(region), dtype=np.float64))),
                    peak=float(np.max(np.abs(region))),
                )
            )
        return regions


class FasterWhisperASR:
    backend_id = "faster-whisper-local-v1"

    def __init__(
        self,
        model_id: str = "small",
        *,
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        self.model_id = str(model_id).strip() or "small"
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def _get_model(self) -> Any:
        if not self.available:
            raise VoiceIngestError(
                "faster-whisper is not installed; install requirements-voice.txt"
            )
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore

            self._model = WhisperModel(
                self.model_id,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(
        self,
        path: Path,
        *,
        language: str | None,
        regions: Sequence[SpeechRegion],
    ) -> list[ASRResult]:
        model = self._get_model()
        segments, info = model.transcribe(
            str(path),
            language=language,
            word_timestamps=True,
            vad_filter=False,
            beam_size=5,
        )
        results: list[ASRResult] = []
        detected_language = getattr(info, "language", None)
        for segment in segments:
            text = str(segment.text).strip()
            if not text:
                continue
            avg_logprob = float(getattr(segment, "avg_logprob", -2.0))
            confidence = float(np.clip(math.exp(avg_logprob), 0.0, 1.0))
            results.append(
                ASRResult(
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=text,
                    confidence=confidence,
                    language=detected_language,
                )
            )
        return results


def default_voice_data_dir() -> Path:
    override = os.environ.get("FVSC_VOICE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system().casefold()
    if system == "windows" and os.environ.get("LOCALAPPDATA"):
        return (Path(os.environ["LOCALAPPDATA"]) / "FVSC" / "voice").resolve()
    if system == "darwin":
        return (Path.home() / "Library" / "Application Support" / "FVSC" / "voice").resolve()
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (base / "fvsc" / "voice").resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _normalize_transcript(text: str) -> str:
    # R1 deliberately performs only whitespace normalization.  Punctuation,
    # repetitions and hesitation markers remain auditable in text_raw.
    return " ".join(str(text).split()).strip()


class VoiceRepository:
    """Versioned local store for captures, transcripts and candidate revisions."""

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        vault_path: Path | str | None = None,
        asr_backend: ASRBackend | None = None,
        decoders: Sequence[AudioDecoder] | None = None,
        vad: EnergyVoiceActivityDetector | None = None,
    ) -> None:
        self.root = Path(root or default_voice_data_dir()).expanduser().resolve()
        self.vault_path = Path(vault_path).resolve() if vault_path is not None else None
        if self.vault_path is not None and _is_relative_to(self.root, self.vault_path):
            raise VoiceIngestError("voice data directory must not be inside the vault")
        self.root.mkdir(parents=True, exist_ok=True)
        self.capture_dir = self.root / "captures"
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "voice-index.json"
        self.asr_backend = asr_backend or FasterWhisperASR(
            model_id=os.environ.get("FVSC_ASR_MODEL", "small")
        )
        self.decoders = tuple(decoders or (WavPcmDecoder(), PyAvDecoder()))
        self.vad = vad or EnergyVoiceActivityDetector()
        self._data = self._load()

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": VOICE_INDEX_VERSION,
            "captures": {},
            "transcripts": {},
            "candidates": {},
        }

    def _load(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return self._empty()
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VoiceIngestError(f"cannot read voice index: {exc}") from exc
        if payload.get("schema_version") != VOICE_INDEX_VERSION:
            raise VoiceIngestError("unsupported voice index version")
        for key in ("captures", "transcripts", "candidates"):
            if not isinstance(payload.get(key), dict):
                raise VoiceIngestError(f"voice index field {key} is invalid")
        return payload

    def _save(self) -> None:
        _atomic_json(self.index_path, self._data)

    @property
    def asr_available(self) -> bool:
        return bool(getattr(self.asr_backend, "available", False))

    def _decoder_for(self, path: Path) -> AudioDecoder:
        for decoder in self.decoders:
            if decoder.supports(path):
                return decoder
        raise VoiceIngestError(
            f"no local decoder for {path.suffix or 'unknown format'}; "
            "WAV is always supported and compressed formats require PyAV"
        )

    def import_audio(
        self,
        data: bytes,
        *,
        filename: str,
        mode: str = "file_import",
        declared_owner_only: bool = True,
        evidence_mode: str = "save_owner_turns_for_review",
        retention_class: str = "24h",
        language: str | None = None,
        observed_at: float | None = None,
    ) -> dict[str, Any]:
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise VoiceIngestError("audio body is empty")
        if len(data) > MAX_AUDIO_BYTES:
            raise VoiceIngestError(f"audio exceeds {MAX_AUDIO_BYTES} bytes")
        safe_name = Path(str(filename)).name.strip()
        if not safe_name:
            raise VoiceIngestError("filename is required")
        extension = Path(safe_name).suffix.casefold()
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise VoiceIngestError(f"unsupported audio extension: {extension or '<none>'}")

        source_hash = hashlib.sha256(bytes(data)).hexdigest()
        relative_ref = Path("captures") / f"{source_hash}{extension}"
        destination = self.root / relative_ref
        if not destination.exists():
            fd, temporary = tempfile.mkstemp(prefix=".audio.", suffix=extension, dir=self.capture_dir)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, destination)
            finally:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

        try:
            decoder = self._decoder_for(destination)
            decoded = decoder.decode(destination)
            if decoded.duration_seconds > MAX_AUDIO_SECONDS:
                raise VoiceIngestError("audio duration exceeds the R1 limit")
            regions = self.vad.detect(decoded)
            now = float(time.time() if observed_at is None else observed_at)
            capture = AudioCaptureArtifact.create(
                mode=mode,  # type: ignore[arg-type]
                started_at=now,
                ended_at=now + decoded.duration_seconds,
                sample_rate=decoded.sample_rate,
                channels=decoded.source_channels,
                source_hash=source_hash,
                retention_class=retention_class,  # type: ignore[arg-type]
                declared_owner_only=declared_owner_only,
                evidence_mode=evidence_mode,  # type: ignore[arg-type]
                storage_ref=relative_ref.as_posix(),
                metadata={
                    "filename": safe_name,
                    "decoder": decoder.backend_id,
                    "vad": self.vad.backend_id,
                    "regions": [region.to_dict() for region in regions],
                    "duration_seconds": decoded.duration_seconds,
                    "language_requested": language,
                },
            )
            capture_record = {
                "artifact": asdict(capture),
                "status": "no_speech" if not regions else "awaiting_asr",
                "created_at": time.time(),
                "audio_deleted_at": None,
                "error": None,
            }
            self._data["captures"][capture.capture_id] = capture_record

            candidates: list[dict[str, Any]] = []
            if regions and self.asr_available:
                results = self.asr_backend.transcribe(
                    destination,
                    language=language,
                    regions=regions,
                )
                for index, result in enumerate(results):
                    normalized = _normalize_transcript(result.text)
                    if not normalized:
                        continue
                    transcript = TranscriptArtifact.create(
                        capture_id=capture.capture_id,
                        utterance_id=f"{capture.capture_id[:16]}-{index:04d}",
                        start_seconds=result.start_seconds,
                        end_seconds=result.end_seconds,
                        text_raw=result.text,
                        text_normalized=normalized,
                        asr_backend=self.asr_backend.backend_id,
                        model_id=self.asr_backend.model_id,
                        speaker_attribution=(
                            "declared_owner" if declared_owner_only else "uncertain"
                        ),
                        confidence=result.confidence,
                        speaker_confidence=None,
                        corrected=False,
                        metadata={"language": result.language},
                    )
                    candidate = VoiceEvidenceCandidate.create(
                        transcript_id=transcript.transcript_id,
                        capture_mode=capture.mode,
                        evidence_mode=capture.evidence_mode,
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
                capture_record["status"] = "ready" if candidates else "no_transcript"
            self._save()
            return {
                "capture": capture_record,
                "candidates": candidates,
                "asr_available": self.asr_available,
            }
        except Exception:
            # Keep the raw source only when a capture record exists.  Prior to that,
            # a failed decode should not create an unindexed orphan.
            if not any(
                record.get("artifact", {}).get("source_hash") == source_hash
                for record in self._data["captures"].values()
            ):
                try:
                    destination.unlink()
                except OSError:
                    pass
            raise

    def status(self) -> dict[str, Any]:
        latest = [
            record for record in self._data["candidates"].values()
            if record.get("superseded_by") is None
        ]
        return {
            "root": str(self.root),
            "capture_count": len(self._data["captures"]),
            "transcript_count": len(self._data["transcripts"]),
            "candidate_count": len(latest),
            "pending_candidate_count": sum(
                record["artifact"].get("promotion_state") == "pending_review"
                for record in latest
            ),
            "asr_backend": self.asr_backend.backend_id,
            "asr_model": self.asr_backend.model_id,
            "asr_available": self.asr_available,
            "compressed_audio_decoder": any(
                isinstance(decoder, PyAvDecoder) and decoder.available
                for decoder in self.decoders
            ),
        }

    def get_capture(self, capture_id: str) -> dict[str, Any]:
        record = self._data["captures"].get(str(capture_id).strip())
        if record is None:
            raise KeyError("voice capture not found")
        return json.loads(json.dumps(record))

    def get_transcript(self, transcript_id: str) -> dict[str, Any]:
        record = self._data["transcripts"].get(str(transcript_id).strip())
        if record is None:
            raise KeyError("voice transcript not found")
        return dict(record)

    def candidate_payload(self, candidate_id: str) -> dict[str, Any]:
        record = self._data["candidates"].get(str(candidate_id).strip())
        if record is None:
            raise KeyError("voice candidate not found")
        artifact = dict(record["artifact"])
        transcript = self.get_transcript(artifact["transcript_id"])
        capture = self.get_capture(transcript["capture_id"])
        return {
            "candidate": artifact,
            "transcript": transcript,
            "capture": capture,
            "created_at": record["created_at"],
            "superseded_by": record.get("superseded_by"),
            "source_id": record.get("source_id"),
        }

    def list_candidates(self, *, include_terminal: bool = False) -> list[dict[str, Any]]:
        result = []
        for candidate_id, record in self._data["candidates"].items():
            if record.get("superseded_by") is not None:
                continue
            state = record["artifact"].get("promotion_state")
            if not include_terminal and state != "pending_review":
                continue
            result.append(self.candidate_payload(candidate_id))
        result.sort(key=lambda item: (item["created_at"], item["candidate"]["candidate_id"]))
        return result

    def correct_candidate(self, candidate_id: str, text: str) -> dict[str, Any]:
        payload = self.candidate_payload(candidate_id)
        normalized = _normalize_transcript(text)
        if not normalized:
            raise VoiceIngestError("corrected transcript must not be empty")
        old_transcript = payload["transcript"]
        old_candidate = payload["candidate"]
        transcript = TranscriptArtifact.create(
            capture_id=old_transcript["capture_id"],
            utterance_id=old_transcript["utterance_id"],
            start_seconds=old_transcript["start_seconds"],
            end_seconds=old_transcript["end_seconds"],
            text_raw=old_transcript["text_raw"],
            text_normalized=normalized,
            asr_backend=old_transcript["asr_backend"],
            model_id=old_transcript["model_id"],
            speaker_attribution=old_transcript["speaker_attribution"],
            confidence=old_transcript.get("confidence"),
            speaker_confidence=old_transcript.get("speaker_confidence"),
            corrected=True,
            metadata={
                **json.loads(old_transcript.get("metadata_json", "{}")),
                "supersedes_transcript_id": old_transcript["transcript_id"],
            },
        )
        candidate = VoiceEvidenceCandidate.create(
            transcript_id=transcript.transcript_id,
            capture_mode=old_candidate["capture_mode"],
            evidence_mode=old_candidate["evidence_mode"],
            speaker_attribution=old_candidate["speaker_attribution"],
            transcript_confidence=old_candidate.get("transcript_confidence"),
            speaker_confidence=old_candidate.get("speaker_confidence"),
        )
        self._data["transcripts"][transcript.transcript_id] = asdict(transcript)
        self._data["candidates"][candidate.candidate_id] = {
            "artifact": asdict(candidate),
            "created_at": time.time(),
            "superseded_by": None,
            "source_id": None,
        }
        self._data["candidates"][candidate_id]["superseded_by"] = candidate.candidate_id
        self._save()
        return self.candidate_payload(candidate.candidate_id)

    def _revise_candidate(
        self,
        candidate_id: str,
        *,
        promotion_state: str,
        reviewed_by_user: bool,
        explicit_user_approval: bool,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        payload = self.candidate_payload(candidate_id)
        old = payload["candidate"]
        candidate = VoiceEvidenceCandidate.create(
            transcript_id=old["transcript_id"],
            capture_mode=old["capture_mode"],
            evidence_mode=old["evidence_mode"],
            speaker_attribution=old["speaker_attribution"],
            transcript_confidence=old.get("transcript_confidence"),
            speaker_confidence=old.get("speaker_confidence"),
            promotion_state=promotion_state,  # type: ignore[arg-type]
            reviewed_by_user=reviewed_by_user,
            explicit_user_approval=explicit_user_approval,
        )
        self._data["candidates"][candidate.candidate_id] = {
            "artifact": asdict(candidate),
            "created_at": time.time(),
            "superseded_by": None,
            "source_id": source_id,
        }
        self._data["candidates"][candidate_id]["superseded_by"] = candidate.candidate_id
        self._save()
        return self.candidate_payload(candidate.candidate_id)

    def approve_candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._revise_candidate(
            candidate_id,
            promotion_state="pending_review",
            reviewed_by_user=True,
            explicit_user_approval=True,
        )

    def mark_promoted(self, candidate_id: str, *, source_id: str) -> dict[str, Any]:
        return self._revise_candidate(
            candidate_id,
            promotion_state="promoted",
            reviewed_by_user=True,
            explicit_user_approval=True,
            source_id=source_id,
        )

    def discard_candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._revise_candidate(
            candidate_id,
            promotion_state="discarded",
            reviewed_by_user=True,
            explicit_user_approval=False,
        )

    def delete_audio(self, capture_id: str) -> dict[str, Any]:
        record = self._data["captures"].get(str(capture_id).strip())
        if record is None:
            raise KeyError("voice capture not found")
        artifact = record["artifact"]
        storage_ref = artifact.get("storage_ref")
        if storage_ref:
            path = (self.root / storage_ref).resolve()
            if not _is_relative_to(path, self.root):
                raise VoiceIngestError("stored audio path escaped the voice directory")
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        record["audio_deleted_at"] = time.time()
        artifact["storage_ref"] = None
        self._save()
        return self.get_capture(capture_id)
