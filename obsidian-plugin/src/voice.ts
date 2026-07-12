import { App, Modal, Notice } from "obsidian";

export interface VoiceControllerOptions {
  app: App;
  baseUrl: () => string;
  ensureBackend: () => Promise<boolean>;
  onRecordingState: (recording: boolean, detail?: string) => void;
}

interface VoiceCandidatePayload {
  candidate: {
    candidate_id: string;
    promotion_state: string;
    speaker_attribution: string;
  };
  transcript: {
    text_raw: string;
    text_normalized: string;
    confidence?: number | null;
    corrected: boolean;
  };
  capture: {
    artifact: {
      capture_id: string;
      mode: string;
      retention_class: string;
    };
  };
}

interface VoiceImportResponse {
  capture: { status: string; artifact: { capture_id: string } };
  candidates: VoiceCandidatePayload[];
  asr_available: boolean;
}

function safeHeaderFilename(name: string): string {
  const cleaned = name.replace(/[^\x20-\x7e]/g, "_").replace(/[\\/]/g, "_").trim();
  return cleaned || `voice-${Date.now()}.wav`;
}

function mergeFloat32(chunks: Float32Array[]): Float32Array {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const result = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);
  const writeText = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const value = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, value < 0 ? value * 32768 : value * 32767, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function pickAudioFile(): Promise<File | null> {
  return await new Promise<File | null>((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".wav,.flac,.mp3,.m4a,.ogg,.webm,audio/*";
    input.style.display = "none";
    input.onchange = () => {
      const file = input.files?.item(0) ?? null;
      input.remove();
      resolve(file);
    };
    input.oncancel = () => {
      input.remove();
      resolve(null);
    };
    document.body.appendChild(input);
    input.click();
  });
}

export class VoiceController {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private chunks: Float32Array[] = [];
  private sessionId: string | null = null;
  private recordingStartedAt = 0;

  constructor(private options: VoiceControllerOptions) {}

  isRecording(): boolean {
    return this.stream !== null;
  }

  async importAudio(): Promise<void> {
    if (!(await this.options.ensureBackend())) return;
    const file = await pickAudioFile();
    if (!file) return;
    new Notice(`FVSC Voice: импортирую ${file.name}…`);
    try {
      const result = await this.upload(file, file.name, "file_import");
      this.reportImport(result);
    } catch (error) {
      console.error("[fvsc-voice] import failed", error);
      new Notice(`FVSC Voice: импорт не удался — ${String(error)}`, 10_000);
    }
  }

  async toggleVoiceMemo(): Promise<void> {
    if (this.isRecording()) await this.stopVoiceMemo();
    else await this.startVoiceMemo();
  }

  async startVoiceMemo(): Promise<void> {
    if (this.isRecording()) return;
    if (!(await this.options.ensureBackend())) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      new Notice("FVSC Voice: захват микрофона недоступен в этой версии Obsidian.");
      return;
    }
    try {
      const sessionResponse = await fetch(`${this.options.baseUrl()}/pilot/voice/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "voice_memo",
          declared_owner_only: true,
          evidence_mode: "save_owner_turns_for_review",
          retention_class: "24h",
          tts_enabled: false,
        }),
      });
      if (!sessionResponse.ok) throw new Error(await sessionResponse.text());
      const sessionData = await sessionResponse.json() as { session: { session_id: string } };
      this.sessionId = sessionData.session.session_id;

      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      this.audioContext = new AudioContext();
      this.source = this.audioContext.createMediaStreamSource(this.stream);
      // Transitional R1 capture. Realtime R2 moves frame processing to AudioWorklet.
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
      this.chunks = [];
      this.processor.onaudioprocess = (event: AudioProcessingEvent) => {
        this.chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      };
      this.source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);
      this.recordingStartedAt = Date.now();
      this.options.onRecordingState(true, "owner voice memo");
      new Notice("FVSC Voice: запись началась. Нажмите кнопку ещё раз для остановки.", 6000);
    } catch (error) {
      await this.releaseCapture();
      await this.stopBackendSession("capture_start_failed");
      console.error("[fvsc-voice] capture start failed", error);
      new Notice(`FVSC Voice: микрофон не запущен — ${String(error)}`, 10_000);
    }
  }

  async stopVoiceMemo(): Promise<void> {
    if (!this.isRecording()) return;
    const context = this.audioContext;
    const sampleRate = context?.sampleRate ?? 48_000;
    const samples = mergeFloat32(this.chunks);
    await this.releaseCapture();
    this.options.onRecordingState(false);
    try {
      if (samples.length < sampleRate / 5) {
        throw new Error("запись короче 0.2 секунды");
      }
      const blob = encodeWav(samples, sampleRate);
      const result = await this.upload(blob, `voice-memo-${Date.now()}.wav`, "voice_memo");
      await this.stopBackendSession("user_stop");
      this.reportImport(result);
    } catch (error) {
      await this.stopBackendSession("upload_failed");
      console.error("[fvsc-voice] memo upload failed", error);
      new Notice(`FVSC Voice: запись не обработана — ${String(error)}`, 10_000);
    } finally {
      this.chunks = [];
      this.recordingStartedAt = 0;
    }
  }

  async emergencyStop(): Promise<void> {
    await this.releaseCapture();
    this.chunks = [];
    this.recordingStartedAt = 0;
    this.options.onRecordingState(false);
    try {
      await fetch(`${this.options.baseUrl()}/pilot/voice/emergency-stop`, { method: "POST" });
    } catch { /* backend may already be down */ }
    this.sessionId = null;
    new Notice("FVSC Voice: emergency stop выполнен; незавершённый буфер отброшен.");
  }

  openReviewQueue(): void {
    new VoiceReviewModal(this.options.app, this.options.baseUrl).open();
  }

  async dispose(): Promise<void> {
    if (this.isRecording()) await this.emergencyStop();
  }

  private async upload(blob: Blob, filename: string, mode: "file_import" | "voice_memo"): Promise<VoiceImportResponse> {
    const response = await fetch(
      `${this.options.baseUrl()}/pilot/voice/import?mode=${mode}&declared_owner_only=true&` +
      "evidence_mode=save_owner_turns_for_review&retention_class=24h&language=ru",
      {
        method: "POST",
        headers: {
          "Content-Type": blob.type || "application/octet-stream",
          "X-FVSC-Filename": safeHeaderFilename(filename),
        },
        body: await blob.arrayBuffer(),
      },
    );
    if (!response.ok) throw new Error(await response.text());
    return await response.json() as VoiceImportResponse;
  }

  private reportImport(result: VoiceImportResponse): void {
    if (result.candidates.length > 0) {
      new Notice(
        `FVSC Voice: создано кандидатов: ${result.candidates.length}. Откройте очередь проверки.`,
        8000,
      );
    } else if (!result.asr_available) {
      new Notice(
        "FVSC Voice: аудио сохранено, но локальный ASR не установлен. Установите requirements-voice.txt.",
        10_000,
      );
    } else if (result.capture.status === "no_speech") {
      new Notice("FVSC Voice: участки речи не обнаружены.");
    } else {
      new Notice(`FVSC Voice: capture сохранён со статусом ${result.capture.status}.`);
    }
  }

  private async releaseCapture(): Promise<void> {
    if (this.processor) {
      this.processor.onaudioprocess = null;
      try { this.processor.disconnect(); } catch { /* ignore */ }
    }
    if (this.source) {
      try { this.source.disconnect(); } catch { /* ignore */ }
    }
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.audioContext) {
      try { await this.audioContext.close(); } catch { /* ignore */ }
    }
    this.processor = null;
    this.source = null;
    this.audioContext = null;
    this.stream = null;
  }

  private async stopBackendSession(reason: string): Promise<void> {
    const sessionId = this.sessionId;
    this.sessionId = null;
    if (!sessionId) return;
    try {
      await fetch(`${this.options.baseUrl()}/pilot/voice/sessions/${sessionId}/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
    } catch { /* lifecycle cleanup is best-effort after local capture ended */ }
  }
}

class VoiceReviewModal extends Modal {
  constructor(app: App, private baseUrl: () => string) {
    super(app);
  }

  onOpen(): void {
    this.modalEl.addClass("fvsc-voice-review-modal");
    void this.renderQueue();
  }

  private async renderQueue(): Promise<void> {
    this.contentEl.empty();
    this.contentEl.createEl("h2", { text: "FVSC Voice — очередь проверки" });
    const loading = this.contentEl.createEl("p", { text: "Загружаю…" });
    try {
      const response = await fetch(`${this.baseUrl()}/pilot/voice/candidates`);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json() as { candidates: VoiceCandidatePayload[] };
      loading.remove();
      if (data.candidates.length === 0) {
        this.contentEl.createEl("p", { text: "Нет ожидающих проверки транскриптов." });
        return;
      }
      for (const item of data.candidates) this.renderCandidate(item);
    } catch (error) {
      loading.setText(`Ошибка: ${String(error)}`);
    }
  }

  private renderCandidate(item: VoiceCandidatePayload): void {
    const card = this.contentEl.createDiv({ cls: "fvsc-voice-candidate" });
    card.createEl("h3", { text: `${item.capture.artifact.mode} · ${item.candidate.speaker_attribution}` });
    const confidence = item.transcript.confidence;
    card.createEl("p", {
      text: `ASR confidence: ${typeof confidence === "number" ? confidence.toFixed(3) : "unknown"}`,
      cls: "fvsc-voice-meta",
    });
    const rawDetails = card.createEl("details");
    rawDetails.createEl("summary", { text: "Сырой ASR-текст" });
    rawDetails.createEl("pre", { text: item.transcript.text_raw });
    const editor = card.createEl("textarea", { cls: "fvsc-voice-transcript-editor" });
    editor.value = item.transcript.text_normalized;
    editor.rows = 5;
    const actions = card.createDiv({ cls: "fvsc-voice-actions" });

    const save = actions.createEl("button", { text: "Сохранить исправление" });
    save.onclick = async () => {
      save.disabled = true;
      try {
        await this.correct(item.candidate.candidate_id, editor.value);
        new Notice("FVSC Voice: исправление сохранено как новая ревизия.");
        await this.renderQueue();
      } catch (error) {
        new Notice(`FVSC Voice: ${String(error)}`, 8000);
        save.disabled = false;
      }
    };

    const promote = actions.createEl("button", { text: "Подтвердить в карту", cls: "mod-cta" });
    promote.onclick = async () => {
      promote.disabled = true;
      try {
        let candidateId = item.candidate.candidate_id;
        if (editor.value.trim() !== item.transcript.text_normalized.trim()) {
          const corrected = await this.correct(candidateId, editor.value);
          candidateId = corrected.candidate.candidate_id;
        }
        const response = await fetch(`${this.baseUrl()}/pilot/voice/candidates/${candidateId}/promote`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ automatic_promotion_enabled: false }),
        });
        if (!response.ok) throw new Error(await response.text());
        new Notice("FVSC Voice: проверенный транскрипт добавлен в evidence ledger.", 7000);
        await this.renderQueue();
      } catch (error) {
        new Notice(`FVSC Voice: promotion failed — ${String(error)}`, 10_000);
        promote.disabled = false;
      }
    };

    const discard = actions.createEl("button", { text: "Отбросить", cls: "mod-warning" });
    discard.onclick = async () => {
      discard.disabled = true;
      try {
        const response = await fetch(
          `${this.baseUrl()}/pilot/voice/candidates/${item.candidate.candidate_id}/discard`,
          { method: "POST" },
        );
        if (!response.ok) throw new Error(await response.text());
        await this.renderQueue();
      } catch (error) {
        new Notice(`FVSC Voice: ${String(error)}`, 8000);
        discard.disabled = false;
      }
    };
  }

  private async correct(candidateId: string, text: string): Promise<VoiceCandidatePayload> {
    const response = await fetch(`${this.baseUrl()}/pilot/voice/candidates/${candidateId}/correct`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error(await response.text());
    return await response.json() as VoiceCandidatePayload;
  }
}
