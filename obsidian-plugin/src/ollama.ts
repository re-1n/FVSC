import { spawn, spawnSync, ChildProcess } from "child_process";
import { existsSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { homedir, platform } from "os";

/**
 * ollama.ts — autodetect, ping, and auto-start a local Ollama daemon.
 *
 * Mirrors paths.ts in spirit: Obsidian's process PATH doesn't reliably
 * include the user's shell PATH, so probing canonical install dirs gives
 * a much better hit rate than `where ollama` / `which ollama` alone.
 *
 * `ollama serve` is spawned detached so it survives Obsidian closing —
 * the user's other tools (the Ollama tray app, other Ollama clients)
 * expect the daemon to stick around, not die with the editor.
 */

const PING_TIMEOUT_MS = 2_000;
const HEALTH_POLL_MS = 500;
const HEALTH_TIMEOUT_MS = 10_000;

function isLiveFile(path: string): boolean {
  try {
    statSync(path);
    return true;
  } catch {
    return false;
  }
}

function whichOllama(): string | null {
  const cmd = platform() === "win32" ? "where" : "which";
  try {
    // windowsHide stops the cmd.exe console from flashing on screen.
    const r = spawnSync(cmd, ["ollama"], { timeout: 2000, encoding: "utf8", windowsHide: true });
    if (r.status === 0 && r.stdout) {
      // `where` on Windows can list multiple lines; take the first.
      const first = r.stdout.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)[0];
      if (first && isLiveFile(first)) return first;
    }
  } catch { /* ignore */ }
  return null;
}

function windowsOllamaCandidates(): string[] {
  const out: string[] = [];
  const localApp = process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local");
  const progFiles = process.env["ProgramFiles"] || "C:\\Program Files";
  const progFilesX86 = process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)";

  // Default user-scope installer
  out.push(join(localApp, "Programs", "Ollama", "ollama.exe"));

  // System-scope installer
  out.push(join(progFiles, "Ollama", "ollama.exe"));
  out.push(join(progFilesX86, "Ollama", "ollama.exe"));

  // Common alt-drive install (power users moving Ollama off C:)
  out.push("D:\\Ollama\\ollama.exe");
  out.push("E:\\Ollama\\ollama.exe");

  return out;
}

function macosOllamaCandidates(): string[] {
  return [
    "/opt/homebrew/bin/ollama",
    "/usr/local/bin/ollama",
    "/Applications/Ollama.app/Contents/Resources/ollama",
    "/Applications/Ollama.app/Contents/MacOS/ollama",
  ];
}

function linuxOllamaCandidates(): string[] {
  const home = homedir();
  return [
    "/usr/local/bin/ollama",
    "/usr/bin/ollama",
    join(home, ".local", "bin", "ollama"),
  ];
}

/**
 * Find a runnable `ollama` binary. Returns null if Ollama isn't installed.
 * Order: PATH (`where`/`which`) → canonical install dirs for the platform.
 */
export async function detectOllama(): Promise<string | null> {
  const fromPath = whichOllama();
  if (fromPath) return fromPath;

  const candidates: string[] =
    platform() === "win32" ? windowsOllamaCandidates()
    : platform() === "darwin" ? macosOllamaCandidates()
    : linuxOllamaCandidates();

  for (const c of candidates) {
    if (isLiveFile(c)) return c;
  }
  return null;
}

/**
 * Ping the daemon's HTTP API. Bounded timeout — we never want to block the
 * UI for more than a couple seconds waiting on a dead socket.
 */
export async function pingOllama(host = "http://localhost:11434"): Promise<boolean> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), PING_TIMEOUT_MS);
  try {
    const r = await fetch(`${host}/api/tags`, { signal: ctrl.signal });
    return r.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Spawn `ollama serve` detached from Obsidian. unref() prevents the parent
 * from waiting on it during exit, and `detached: true` puts it in its own
 * process group so closing Obsidian doesn't take Ollama down with it —
 * matching the user's expectation that the daemon lives independently
 * (same way the Ollama tray app keeps it running).
 *
 * Pass `modelsDir` to force OLLAMA_MODELS so the daemon scans a custom
 * directory (e.g. Rein's `D:\ollama models\`). Without this Ollama uses
 * its default `~/.ollama/models` and would miss models stored elsewhere.
 */
export function spawnOllamaServe(execPath: string, modelsDir?: string): ChildProcess {
  const env = modelsDir
    ? { ...process.env, OLLAMA_MODELS: modelsDir }
    : process.env;
  const proc = spawn(execPath, ["serve"], {
    detached: true,
    stdio: "ignore",
    windowsHide: true,
    env,
  });
  proc.unref();
  return proc;
}

/**
 * Kill every running Ollama process on the host. Use this only when the
 * daemon is up but pointing at the wrong models directory, so we can
 * restart it with the right OLLAMA_MODELS. Best-effort: missing perms,
 * missing tools, etc. all silently no-op.
 */
export async function killAllOllama(): Promise<void> {
  const isWin = platform() === "win32";
  try {
    if (isWin) {
      // Kill both daemon and tray app. /F = force, /T = kill children.
      spawnSync("taskkill", ["/F", "/T", "/IM", "ollama.exe"], {
        timeout: 5000, windowsHide: true,
      });
      spawnSync("taskkill", ["/F", "/IM", "ollama app.exe"], {
        timeout: 5000, windowsHide: true,
      });
    } else {
      spawnSync("pkill", ["-x", "ollama"], { timeout: 5000 });
    }
  } catch { /* ignore */ }
  // Brief settle so the next ping doesn't catch the dying socket.
  await new Promise((r) => setTimeout(r, 600));
}

/**
 * Scan canonical Ollama model storage paths and return the first that has
 * a non-empty `manifests/registry.ollama.ai/` directory. Used to find
 * models that exist on disk but aren't visible to the daemon because it
 * was launched without OLLAMA_MODELS pointed at this location.
 */
export async function detectOllamaModelsDir(): Promise<string | null> {
  const home = homedir();
  const isWin = platform() === "win32";
  const isMac = platform() === "darwin";

  const candidates: string[] = [];
  candidates.push(join(home, ".ollama", "models"));

  if (isWin) {
    // Common alt-drive setups: D:\ollama models (with space), D:\Ollama\models, etc.
    candidates.push("D:\\ollama models");
    candidates.push("D:\\ollama_models");
    candidates.push("D:\\Ollama\\models");
    candidates.push("E:\\ollama models");
    candidates.push("E:\\Ollama\\models");
    const programData = process.env["ProgramData"] || "C:\\ProgramData";
    candidates.push(join(programData, "Ollama", "models"));
  } else if (isMac) {
    candidates.push("/usr/local/share/ollama/.ollama/models");
  } else {
    candidates.push("/usr/share/ollama/.ollama/models");
    candidates.push("/var/lib/ollama/models");
  }

  for (const c of candidates) {
    const manifestRoot = join(c, "manifests", "registry.ollama.ai");
    if (!existsSync(manifestRoot)) continue;
    try {
      // A directory with at least one library subdirectory means models live here.
      const entries = readdirSync(manifestRoot);
      if (entries.length > 0) return c;
    } catch { /* ignore */ }
  }
  return null;
}

/**
 * If Ollama is already up — return alreadyUp=true and do nothing.
 * Otherwise spawn `ollama serve` and poll /api/tags until it answers
 * or we hit HEALTH_TIMEOUT_MS.
 */
export async function ensureOllamaRunning(
  execPath: string,
  host = "http://localhost:11434",
  modelsDir?: string,
): Promise<{ started: boolean; alreadyUp: boolean }> {
  if (await pingOllama(host)) {
    return { started: false, alreadyUp: true };
  }
  try {
    spawnOllamaServe(execPath, modelsDir);
  } catch (e) {
    console.warn("[fvsc-ollama] spawn failed:", e);
    return { started: false, alreadyUp: false };
  }
  const deadline = Date.now() + HEALTH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
    if (await pingOllama(host)) return { started: true, alreadyUp: false };
  }
  return { started: false, alreadyUp: false };
}

/**
 * Top-level orchestration helper for main.ts. Returns a short status string
 * suitable for logging / statusBar tooltips. Never throws.
 */
export async function tryAutoStartOllama(
  opts: { host?: string; modelsDir?: string } = {},
): Promise<{ status: "already_up" | "started" | "no_binary" | "spawn_failed"; execPath: string | null }> {
  const host = opts.host || "http://localhost:11434";
  if (await pingOllama(host)) {
    return { status: "already_up", execPath: null };
  }
  const execPath = await detectOllama();
  if (!execPath) {
    return { status: "no_binary", execPath: null };
  }
  const r = await ensureOllamaRunning(execPath, host, opts.modelsDir);
  if (r.started) return { status: "started", execPath };
  if (r.alreadyUp) return { status: "already_up", execPath };
  return { status: "spawn_failed", execPath };
}

/**
 * Kill the daemon and restart it with the given OLLAMA_MODELS — used when
 * /api/tags returns empty but detectOllamaModelsDir found models on disk.
 * This is the only safe way to fix the daemon-vs-models mismatch:
 * Ollama refuses to rescan its model dir at runtime.
 */
export async function restartOllamaWithModelsDir(
  execPath: string,
  modelsDir: string,
  host = "http://localhost:11434",
): Promise<{ ok: boolean }> {
  await killAllOllama();
  try {
    spawnOllamaServe(execPath, modelsDir);
  } catch (e) {
    console.warn("[fvsc-ollama] respawn failed:", e);
    return { ok: false };
  }
  const deadline = Date.now() + HEALTH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
    if (await pingOllama(host)) return { ok: true };
  }
  return { ok: false };
}

// Keep this so callers can still check the binary path; existsSync is fine
// for non-symlink cases but isLiveFile catches dead symlinks on macOS/Linux.
export { isLiveFile, existsSync };
