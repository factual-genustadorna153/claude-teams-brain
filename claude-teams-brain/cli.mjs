#!/usr/bin/env node
// claude-teams-brain: cross-platform npx installer
//
// Usage:
//   npx claude-teams-brain
//
// Equivalent to the bash install.sh but runs on any OS with Node.js 18+.
// No external dependencies — only Node.js built-in modules.

import { execSync, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync, cpSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { homedir, platform } from "node:os";

// ── Colors ───────────────────────────────────────────────────────────────────

const supportsColor = process.stdout.isTTY && !process.env.NO_COLOR;
const c = {
  bold:    (s) => supportsColor ? `\x1b[1m${s}\x1b[0m` : s,
  green:   (s) => supportsColor ? `\x1b[32m${s}\x1b[0m` : s,
  cyan:    (s) => supportsColor ? `\x1b[36m${s}\x1b[0m` : s,
  yellow:  (s) => supportsColor ? `\x1b[33m${s}\x1b[0m` : s,
  red:     (s) => supportsColor ? `\x1b[31m${s}\x1b[0m` : s,
  dim:     (s) => supportsColor ? `\x1b[2m${s}\x1b[0m` : s,
};

function step(n, msg)  { console.log(`\n${c.cyan(`[${n}/5]`)} ${c.bold(msg)}`); }
function info(msg)     { console.log(`     ${msg}`); }
function success(msg)  { console.log(`     ${c.green(msg)}`); }
function warn(msg)     { console.log(`     ${c.yellow(msg)}`); }
function fail(msg)     { console.error(`     ${c.red(msg)}`); }

// ── Helpers ──────────────────────────────────────────────────────────────────

function run(cmd, opts = {}) {
  return execSync(cmd, { encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"], ...opts }).trim();
}

function runGit(args, opts = {}) {
  return execFileSync("git", args, { encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"], ...opts }).trim();
}

function readJSON(filePath) {
  const raw = readFileSync(filePath, "utf-8").trim();
  return raw ? JSON.parse(raw) : {};
}

function writeJSON(filePath, data) {
  writeFileSync(filePath, JSON.stringify(data, null, 2) + "\n", "utf-8");
}

function ensureDir(dir) {
  mkdirSync(dir, { recursive: true });
}

/**
 * Recursively copy src → dest, skipping .git directory.
 * Uses Node 16.7+ fs.cpSync with filter.
 */
function syncDir(src, dest) {
  // Remove dest contents first for a clean sync
  if (existsSync(dest)) {
    rmSync(dest, { recursive: true, force: true });
  }
  ensureDir(dest);
  cpSync(src, dest, {
    recursive: true,
    force: true,
    filter: (source) => !source.includes(`${join(".git")}`),
  });
}

// ── Constants ────────────────────────────────────────────────────────────────

const REPO_URL      = "https://github.com/Gr122lyBr/claude-teams-brain.git";
const REPO_URL_BARE = "https://github.com/Gr122lyBr/claude-teams-brain";
const HOME          = homedir();
const PLUGINS_DIR   = join(HOME, ".claude", "plugins");
const MARKETPLACE_DIR     = join(PLUGINS_DIR, "marketplaces", "claude-teams-brain");
const KNOWN_MARKETPLACES  = join(PLUGINS_DIR, "known_marketplaces.json");
const INSTALLED_JSON      = join(PLUGINS_DIR, "installed_plugins.json");

// ── Main ─────────────────────────────────────────────────────────────────────

console.log("");
console.log(c.bold("  claude-teams-brain installer"));
console.log(c.dim("  Persistent memory for Claude Code Agent Teams"));
console.log(c.dim(`  Platform: ${platform()}, Home: ${HOME}`));
console.log("");

try {
  // ── Step 1: Clone or pull ────────────────────────────────────────────────

  step(1, "Clone / update marketplace repo");

  if (!existsSync(join(MARKETPLACE_DIR, ".git"))) {
    info(`Cloning into ${c.dim(MARKETPLACE_DIR)}...`);
    ensureDir(dirname(MARKETPLACE_DIR));
    runGit(["clone", REPO_URL, MARKETPLACE_DIR]);
    success("Cloned successfully.");
  } else {
    info(`Repo exists at ${c.dim(MARKETPLACE_DIR)} — pulling latest...`);
    runGit(["fetch", "origin"], { cwd: MARKETPLACE_DIR });
    const before = runGit(["rev-parse", "HEAD"], { cwd: MARKETPLACE_DIR });
    const branch = runGit(["symbolic-ref", "--short", "HEAD"], { cwd: MARKETPLACE_DIR });
    runGit(["pull", "--ff-only", "origin", branch], { cwd: MARKETPLACE_DIR });
    const after = runGit(["rev-parse", "HEAD"], { cwd: MARKETPLACE_DIR });
    if (before === after) {
      success(`Already up to date (${after.slice(0, 7)})`);
    } else {
      success(`Updated: ${before.slice(0, 7)}..${after.slice(0, 7)}`);
    }
  }

  // ── Step 2: Patch known_marketplaces.json ────────────────────────────────

  step(2, "Patch known_marketplaces.json");

  if (existsSync(KNOWN_MARKETPLACES)) {
    const data = readJSON(KNOWN_MARKETPLACES);

    function patchEntry(entry) {
      entry.installLocation = MARKETPLACE_DIR;
      if (!entry.url) entry.url = REPO_URL_BARE;
      return entry;
    }

    let patched = false;

    // Format 1: { marketplaces: { "claude-teams-brain": {...} } }
    if (data && typeof data === "object" && data.marketplaces && typeof data.marketplaces === "object" && !Array.isArray(data.marketplaces)) {
      const m = data.marketplaces;
      if (!m["claude-teams-brain"]) {
        m["claude-teams-brain"] = { name: "claude-teams-brain", url: REPO_URL_BARE };
      }
      patchEntry(m["claude-teams-brain"]);
      patched = true;
    }
    // Format 2: flat object with entries at top level { "claude-teams-brain": {...}, ... }
    else if (data && typeof data === "object" && !Array.isArray(data) && !data.marketplaces) {
      if (!data["claude-teams-brain"]) {
        data["claude-teams-brain"] = { source: { source: "git", url: REPO_URL_BARE } };
      }
      data["claude-teams-brain"].installLocation = MARKETPLACE_DIR;
      patched = true;
    }
    // Format 3: { marketplaces: [...] } or top-level array
    else if (data && typeof data === "object") {
      const items = Array.isArray(data) ? data : (Array.isArray(data.marketplaces) ? data.marketplaces : null);
      if (items) {
        let found = false;
        for (const entry of items) {
          if (entry && entry.name === "claude-teams-brain") {
            patchEntry(entry);
            found = true;
          }
        }
        if (!found) {
          items.push({ name: "claude-teams-brain", url: REPO_URL_BARE, installLocation: MARKETPLACE_DIR });
        }
        patched = true;
      } else if (typeof data.marketplaces === "object") {
        if (!data.marketplaces["claude-teams-brain"]) {
          data.marketplaces["claude-teams-brain"] = { name: "claude-teams-brain", url: REPO_URL_BARE };
        }
        patchEntry(data.marketplaces["claude-teams-brain"]);
        patched = true;
      }
    }

    if (patched) {
      writeJSON(KNOWN_MARKETPLACES, data);
      success(`Patched: installLocation => ${MARKETPLACE_DIR}`);
    } else {
      warn("Unrecognised known_marketplaces.json format — skipped patching.");
      warn(`You may need to manually set installLocation to: ${MARKETPLACE_DIR}`);
    }
  } else {
    ensureDir(dirname(KNOWN_MARKETPLACES));
    // Create the file with the correct entry
    const data = {
      marketplaces: {
        "claude-teams-brain": {
          name: "claude-teams-brain",
          url: REPO_URL_BARE,
          installLocation: MARKETPLACE_DIR,
        },
      },
    };
    writeJSON(KNOWN_MARKETPLACES, data);
    success("Created known_marketplaces.json with plugin entry.");
  }

  // ── Step 3: Read version ─────────────────────────────────────────────────

  step(3, "Read plugin version");

  const PLUGIN_SRC = join(MARKETPLACE_DIR, "claude-teams-brain");
  const pkgPath = join(PLUGIN_SRC, "package.json");

  if (!existsSync(pkgPath)) {
    fail(`Plugin source not found at ${pkgPath}`);
    process.exit(1);
  }

  const pkg = readJSON(pkgPath);
  const NEW_VERSION = pkg.version;

  if (!NEW_VERSION) {
    fail(`Could not read version from ${pkgPath}`);
    process.exit(1);
  }

  success(`Version: ${c.bold(NEW_VERSION)}`);

  // ── Step 4: Sync to cache ───────────────────────────────────────────────

  step(4, "Sync plugin to cache directory");

  const CACHE_BASE = join(PLUGINS_DIR, "cache", "claude-teams-brain", "claude-teams-brain");
  const NEW_CACHE_DIR = join(CACHE_BASE, NEW_VERSION);

  info(`Target: ${c.dim(NEW_CACHE_DIR)}`);
  syncDir(PLUGIN_SRC, NEW_CACHE_DIR);
  success("Sync complete.");

  // ── Step 5: Update installed_plugins.json ────────────────────────────────

  step(5, "Update installed_plugins.json");

  const now = new Date().toISOString().replace(/\.\d{3}Z$/, ".000Z");
  const pluginKey = "claude-teams-brain@claude-teams-brain";

  const newEntry = {
    version: NEW_VERSION,
    installPath: NEW_CACHE_DIR,
    source: REPO_URL_BARE,
    lastUpdated: now,
  };

  if (existsSync(INSTALLED_JSON)) {
    const data = readJSON(INSTALLED_JSON);
    const plugins = data.plugins = data.plugins || {};

    if (plugins[pluginKey] && Array.isArray(plugins[pluginKey]) && plugins[pluginKey].length > 0) {
      for (const e of plugins[pluginKey]) {
        Object.assign(e, newEntry);
      }
      success(`Updated existing entry to v${NEW_VERSION}`);
    } else {
      plugins[pluginKey] = [newEntry];
      success(`Created new entry for v${NEW_VERSION}`);
    }

    writeJSON(INSTALLED_JSON, data);
  } else {
    ensureDir(dirname(INSTALLED_JSON));
    const data = { plugins: { [pluginKey]: [newEntry] } };
    writeJSON(INSTALLED_JSON, data);
    success(`Created installed_plugins.json with v${NEW_VERSION}`);
  }

  // ── Done ─────────────────────────────────────────────────────────────────

  console.log("");
  console.log(c.green(c.bold("  Install complete!")));
  console.log("");
  console.log("  Next steps:");
  console.log(`    1. ${c.bold("Restart Claude Code")}`);
  console.log(`    2. If the plugin does not appear active, run inside Claude Code:`);
  console.log(`       ${c.cyan("/plugin install claude-teams-brain@claude-teams-brain")}`);
  console.log(`    3. (Optional) Enable Agent Teams in ~/.claude/settings.json:`);
  console.log(`       ${c.dim('"env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }')}`);
  console.log("");

} catch (err) {
  console.log("");
  fail("Installation failed:");
  console.error(err.message || err);
  if (err.stderr) console.error(c.dim(err.stderr));
  console.log("");
  console.log("  Troubleshooting:");
  console.log("    - Make sure git is installed and in your PATH");
  console.log("    - Check network connectivity (needs to reach github.com)");
  console.log("    - Try running with elevated permissions if file access is denied");
  console.log("");
  process.exit(1);
}
