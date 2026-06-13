import { App, FileSystemAdapter } from "obsidian";
import { spawnSync } from "child_process";
import { existsSync } from "fs";
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
      ["-c", "import sys; print(sys.version_info[0]*10+sys.version_info[1])"],
      { timeout: 3000, encoding: "utf8" },
    );
    if (r.status !== 0 || !r.stdout) return false;
    const v = parseInt(r.stdout.trim(), 10);
    return Number.isFinite(v) && v >= 310;
  } catch {
    return false;
  }
}

/**
 * Try to find a usable Python interpreter. Order:
 *   1. Bundled python inside the plugin folder (future PyInstaller layout).
 *   2. venv inside the FVSC repo — Windows-style `Scripts/` first, then Unix-style `bin/`
 *      (handles git-bash-created venvs on Windows).
 *   3. `python` on PATH.
 *   4. `python3` on PATH.
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

  for (const c of candidates) {
    if (existsSync(c) && testPython(c)) return c;
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
