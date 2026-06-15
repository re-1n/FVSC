import { App, FileSystemAdapter } from "obsidian";
import { spawnSync } from "child_process";
import { existsSync, readdirSync, statSync } from "fs";
import { join, dirname } from "path";
import { homedir, platform } from "os";
import type FvscPlugin from "./main";

/**
 * Resolve the absolute filesystem path of the plugin's own directory.
 * Obsidian gives us a vault-relative path on `manifest.dir`; the
 * FileSystemAdapter converts it to an absolute path.
 */
export function getPluginAbsDir(app: App, manifestDir: string | undefined): string | null {
  if (!manifestDir) return null;
  const adapter = app.vault.adapter;
  if (!(adapter instanceof FileSystemAdapter)) return null;
  return adapter.getFullPath(manifestDir);
}

/**
 * Verify a python binary works and is >= 3.10. Synchronous spawnSync — cheap
 * when the command exists, bounded by 3s timeout otherwise.
 */
function testPython(cmd: string): boolean {
  try {
    const r = spawnSync(
      cmd,
      ["-c", "import sys; print(sys.version_info[0]*100+sys.version_info[1])"],
      { timeout: 3000, encoding: "utf8" },
    );
    if (r.status !== 0 || !r.stdout) return false;
    const v = parseInt(r.stdout.trim(), 10);
    return Number.isFinite(v) && v >= 310;
  } catch {
    return false;
  }
}

// existsSync returns true for broken symlinks (e.g. git-bash venvs where
// venv/bin/python points at a removed system python3). statSync follows the
// link and throws ENOENT on a dead target, which is the liveness signal we want.
function isLiveFile(path: string): boolean {
  try {
    statSync(path);
    return true;
  } catch {
    return false;
  }
}

// Scan common Windows install locations directly — Obsidian doesn't always
// inherit the user's shell PATH, so `python` / `python3` lookups fail even
// when CPython is installed. We probe canonical install dirs instead.
function windowsSystemCandidates(): string[] {
  const out: string[] = [];
  const localApp = process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local");
  const progFiles = process.env["ProgramFiles"] || "C:\\Program Files";
  const progFilesX86 = process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)";

  // User-scope (most common — CPython installer default)
  // %LOCALAPPDATA%\Programs\Python\Python3XX\python.exe
  const userPyRoot = join(localApp, "Programs", "Python");
  if (existsSync(userPyRoot)) {
    try {
      for (const sub of readdirSync(userPyRoot)) {
        if (/^Python3\d{1,2}$/i.test(sub)) {
          out.push(join(userPyRoot, sub, "python.exe"));
        }
      }
    } catch { /* ignore */ }
  }

  // System-scope: C:\Program Files\Python3XX\python.exe (less common but valid)
  for (const root of [progFiles, progFilesX86]) {
    if (!existsSync(root)) continue;
    try {
      for (const sub of readdirSync(root)) {
        if (/^Python3\d{1,2}$/i.test(sub)) {
          out.push(join(root, sub, "python.exe"));
        }
      }
    } catch { /* ignore */ }
  }

  // py launcher — single binary, knows how to dispatch to an installed Python.
  // We probe it last because spawn cost is higher than a direct exe.
  const pyLauncher = join(process.env.SystemRoot || "C:\\Windows", "py.exe");
  if (existsSync(pyLauncher)) out.push(pyLauncher);

  return out;
}

/**
 * Try to find a usable Python interpreter. Order:
 *   1. Bundled python inside the plugin folder (future PyInstaller layout).
 *   2. venv inside the FVSC repo — Windows-style `Scripts/` first, then Unix-style `bin/`
 *      (handles git-bash-created venvs on Windows).
 *   3. Windows: canonical install dirs (%LOCALAPPDATA%\Programs\Python\Python3XX,
 *      Program Files\Python3XX, py launcher) — Obsidian's process PATH doesn't
 *      always include user-scope installs.
 *   4. `python` / `python3` on PATH (last resort — may be missing in Obsidian).
 */
export async function detectPython(
  pluginAbsDir: string | null,
  repoCandidate: string | null,
): Promise<string | null> {
  const isWin = platform() === "win32";
  const candidates: string[] = [];

  if (pluginAbsDir) {
    candidates.push(
      isWin
        ? join(pluginAbsDir, "python", "python.exe")
        : join(pluginAbsDir, "python", "bin", "python"),
    );
  }
  if (repoCandidate) {
    if (isWin) {
      candidates.push(join(repoCandidate, "venv", "Scripts", "python.exe"));
      candidates.push(join(repoCandidate, "venv", "bin", "python.exe"));
      candidates.push(join(repoCandidate, "venv", "bin", "python"));
    } else {
      candidates.push(join(repoCandidate, "venv", "bin", "python"));
    }
  }

  if (isWin) candidates.push(...windowsSystemCandidates());

  for (const c of candidates) {
    if (isLiveFile(c) && testPython(c)) return c;
  }

  for (const c of ["python", "python3"]) {
    if (testPython(c)) {
      const r = spawnSync(
        c,
        ["-c", "import sys; print(sys.executable)"],
        { timeout: 3000, encoding: "utf8" },
      );
      if (r.status === 0 && r.stdout) return r.stdout.trim();
    }
  }
  return null;
}

/**
 * Try to find the FVSC repo root (a directory containing `service/app.py`).
 * Order:
 *   1. Self-contained future layout: <plugin>/fvsc/
 *   2. FVSC_REPO env var
 *   3. Plugin lives inside the repo (.../FVSC/obsidian-plugin/release → up 2, or .../FVSC/obsidian-plugin → up 1)
 *   4. ~/FVSC, ~/Desktop/FVSC, ~/Documents/FVSC
 */
export async function detectRepo(pluginAbsDir: string): Promise<string | null> {
  const home = homedir();
  const candidates = [
    join(pluginAbsDir, "fvsc"),
    process.env.FVSC_REPO || "",
    dirname(dirname(pluginAbsDir)),
    dirname(pluginAbsDir),
    join(home, "FVSC"),
    join(home, "Desktop", "FVSC"),
    join(home, "Documents", "FVSC"),
  ].filter(Boolean);

  for (const c of candidates) {
    if (existsSync(join(c, "service", "app.py"))) return c;
  }
  return null;
}

/**
 * Best-effort auto-fill of pythonPath / fvscRepoPath in settings.
 * Only writes to settings if a value was previously empty AND detection found
 * something. Returns the resolved values for UI to surface, and a `changed`
 * flag if settings were persisted.
 */
export async function autoFillSettings(
  plugin: FvscPlugin,
): Promise<{ python: string | null; repo: string | null; changed: boolean }> {
  const s = plugin.settings;
  const pluginAbsDir = getPluginAbsDir(plugin.app, plugin.manifest.dir);
  if (!pluginAbsDir) return { python: null, repo: null, changed: false };

  let changed = false;
  let repo: string | null = s.fvscRepoPath || null;
  if (!repo) {
    repo = await detectRepo(pluginAbsDir);
    if (repo) {
      s.fvscRepoPath = repo;
      changed = true;
    }
  }
  let py: string | null = s.pythonPath || null;
  if (!py) {
    py = await detectPython(pluginAbsDir, repo);
    if (py) {
      s.pythonPath = py;
      changed = true;
    }
  }
  if (changed) await plugin.saveSettings();
  return { python: py, repo, changed };
}
