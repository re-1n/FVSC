import { spawn, ChildProcess } from "child_process";
import { Notice } from "obsidian";
import type { FvscSettings } from "./settings";

export type BackendStatus = "stopped" | "starting" | "up" | "failed";

export interface BackendOptions {
  vaultPath: string;
  onStatus: (s: BackendStatus, detail?: string) => void;
  /** Fired when start() fails due to missing/invalid config so the host can
   *  open its own Settings tab without leaking Obsidian internals in here. */
  onConfigError?: () => void;
}

const HEALTH_POLL_MS = 500;
const HEALTH_TIMEOUT_MS = 20_000;
const SHUTDOWN_GRACE_MS = 2_000;

export class BackendController {
  private proc: ChildProcess | null = null;
  private status: BackendStatus = "stopped";

  constructor(
    private getSettings: () => FvscSettings,
    private opts: BackendOptions,
  ) {}

  getStatus(): BackendStatus {
    return this.status;
  }

  baseUrl(): string {
    return `http://127.0.0.1:${this.getSettings().port}`;
  }

  async start(): Promise<void> {
    if (this.proc) {
      return;
    }
    const s = this.getSettings();
    if (!s.pythonPath || !s.fvscRepoPath) {
      this.setStatus("failed", "Не указан путь к Python или папка FVSC");
      new Notice("FVSC: укажи путь к Python и папку FVSC в настройках плагина.");
      this.opts.onConfigError?.();
      return;
    }

    this.setStatus("starting");

    const env = {
      ...process.env,
      FVSC_VAULT_PATH: this.opts.vaultPath,
      FVSC_LLM_MODEL: s.modelName,
      PYTHONIOENCODING: "utf-8",
      PYTHONUTF8: "1",
    };

    const args = [
      "-X", "utf8",
      "-m", "uvicorn",
      "fvsc.service.app:app",
      "--app-dir", "src",
      "--host", "127.0.0.1",
      "--port", String(s.port),
    ];

    let proc: ChildProcess;
    try {
      proc = spawn(s.pythonPath, args, {
        cwd: s.fvscRepoPath,
        env,
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
      });
    } catch (e) {
      this.setStatus("failed", String(e));
      new Notice(`FVSC: не удалось запустить движок карты — ${String(e)}`);
      this.opts.onConfigError?.();
      return;
    }

    proc.stdout?.on("data", (b) => console.log("[fvsc-backend]", b.toString().trimEnd()));
    proc.stderr?.on("data", (b) => console.log("[fvsc-backend]", b.toString().trimEnd()));
    proc.on("error", (err) => {
      const msg = (err as NodeJS.ErrnoException).code === "ENOENT"
        ? `Python не найден по пути: ${s.pythonPath}. Открой Настройки → FVSC Antourage.`
        : `Не удалось запустить движок карты: ${err.message}`;
      console.error("[fvsc-backend] spawn error:", err);
      this.proc = null;
      this.setStatus("failed", msg);
      new Notice(`FVSC: ${msg}`);
      this.opts.onConfigError?.();
    });
    proc.on("exit", (code, signal) => {
      console.log(`[fvsc-backend] exited code=${code} signal=${signal}`);
      this.proc = null;
      if (this.status !== "stopped" && this.status !== "failed") {
        this.setStatus(
          "failed",
          `Движок карты неожиданно остановился (код ${code}). Открой Консоль (Ctrl+Shift+I) для подробностей.`,
        );
      }
    });

    this.proc = proc;

    const ok = await this.waitForHealth();
    if (ok) {
      this.setStatus("up");
    } else if (this.status === "starting") {
      this.setStatus("failed", "движок карты не ответил вовремя — проверь Консоль (Ctrl+Shift+I)");
      new Notice("FVSC: движок карты не ответил вовремя. Открой Консоль (Ctrl+Shift+I).");
    }
  }

  async stop(): Promise<void> {
    const p = this.proc;
    this.proc = null;
    this.setStatus("stopped");
    if (!p || p.killed) return;
    try {
      p.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    await new Promise<void>((resolve) => {
      const t = setTimeout(() => {
        try { p.kill("SIGKILL"); } catch { /* ignore */ }
        resolve();
      }, SHUTDOWN_GRACE_MS);
      p.on("exit", () => { clearTimeout(t); resolve(); });
    });
  }

  async restart(): Promise<void> {
    await this.stop();
    await this.start();
  }

  private async waitForHealth(): Promise<boolean> {
    const deadline = Date.now() + HEALTH_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (!this.proc) return false;
      try {
        const r = await fetch(`${this.baseUrl()}/health`, { method: "GET" });
        if (r.ok) {
          return true;
        }
      } catch {
        /* not up yet */
      }
      await sleep(HEALTH_POLL_MS);
    }
    return false;
  }

  private setStatus(s: BackendStatus, detail?: string) {
    this.status = s;
    this.opts.onStatus(s, detail);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
