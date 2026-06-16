import { spawn, spawnSync, ChildProcess } from "child_process";
import { existsSync, statSync } from "fs";
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
 */
export function spawnOllamaServe(execPath: string): ChildProcess {
  const proc = spawn(execPath, ["serve"], {
    detached: true,
    stdio: "ignore",
    windowsHide: true,
  });
  proc.unref();
  return proc;
}

/**
 * If Ollama is already up — return alreadyUp=true and do nothing.
 * Otherwise spawn `ollama serve` and poll /api/tags until it answers
 * or we hit HEALTH_TIMEOUT_MS.
 */
export async function ensureOllamaRunning(
  execPath: string,
  host = "http://localhost:11434",
): Promise<{ started: boolean; alreadyUp: boolean }> {
  if (await pingOllama(host)) {
    return { started: false, alreadyUp: true };
  }
  try {
    spawnOllamaServe(execPath);
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
  host = "http://localhost:11434",
): Promise<{ status: "already_up" | "started" | "no_binary" | "spawn_failed"; execPath: string | null }> {
  if (await pingOllama(host)) {
    return { status: "already_up", execPath: null };
  }
  const execPath = await detectOllama();
  if (!execPath) {
    return { status: "no_binary", execPath: null };
  }
  const r = await ensureOllamaRunning(execPath, host);
  if (r.started) return { status: "started", execPath };
  if (r.alreadyUp) return { status: "already_up", execPath };
  return { status: "spawn_failed", execPath };
}

// Keep this so callers can still check the binary path; existsSync is fine
// for non-symlink cases but isLiveFile catches dead symlinks on macOS/Linux.
export { isLiveFile, existsSync };
