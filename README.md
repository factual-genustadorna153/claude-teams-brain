<p align="center">
  <img src="claude-teams-brain/assets/logo.png" alt="claude-teams-brain" width="120" />
</p>

<h1 align="center">claude-teams-brain</h1>

<p align="center">
  <strong>Make Claude Code faster, cheaper, and smarter</strong><br>
  Save 90%+ tokens on command output. Persistent memory across sessions. Works solo or with Agent Teams.
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/claude-teams-brain"><img src="https://img.shields.io/npm/v/claude-teams-brain.svg" alt="npm version" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-3.8%2B-blue.svg" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/node-18%2B-green.svg" alt="Node 18+" />
  <a href="https://claude.ai/claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-orange.svg" alt="Claude Code Plugin" /></a>
</p>

---

<!-- TODO: Replace with your recorded GIF -->
<p align="center">
  <img src="demo/demo.gif" alt="claude-teams-brain demo" width="700" />
</p>

---

## Why claude-teams-brain?

### Cut token usage by 90–97%

A single `npm test` dumps 20,000 tokens of passing tests into context. `git push` adds transfer stats nobody reads. Every wasted token costs money and shrinks your context window.

claude-teams-brain replaces raw Bash with **token-efficient MCP tools** that filter, index, and search command output — so only what matters enters context.

### Persistent memory across sessions

Agent Teams are powerful — but ephemeral. Your backend agent spent two hours learning your conventions and building auth. Tomorrow, a new backend agent starts from zero.

claude-teams-brain **indexes everything** — tasks, decisions, files — per role. When `backend` spawns again, it receives the full history of what past backend agents built.

### Smarter agents, better results

Agents that start with context make better decisions. Convention learning from git history, shared knowledge base between teammates, and role-specific injection mean your agents produce higher-quality output from the first command.

---

## Install

**One command:**

```bash
npx claude-teams-brain
```

Or with curl:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Gr122lyBr/claude-teams-brain/master/claude-teams-brain/scripts/install.sh)
```

Then restart Claude Code. That's it — the plugin activates automatically.

---

## What It Does

### Token-Efficient Command Execution

Every command through the brain's MCP tools passes through an **8-stage filtering pipeline** with specialized parsers for 60+ commands:

| Command | Without brain | With brain | Savings |
|---------|--------------|------------|---------|
| `npm test` | 20,000 tokens of passing tests | Summary + failures only | **90%+** |
| `git push` | Transfer stats, compression, deltas | `ok main` | **98%** |
| `npm install` | Warnings, progress bars, funding | `added 542 packages in 12s` | **90%+** |
| `pytest` (all pass) | Full session output | `15 passed in 2.34s` | **82%** |
| `docker build` | Layer-by-layer progress | Final image + errors | **95%** |
| `tsc` (no errors) | Verbose compilation | `✓ no errors` | **90%+** |

**Auto-indexing** — every command's output is indexed into a searchable knowledge base. Run a command once, search it many times. Teammates share the same KB — no duplicate work.

**5 MCP tools** replace raw Bash for any command that produces output:
- `batch_execute` — run multiple commands in one call, all output auto-indexed
- `execute` — single command with optional auto-indexing for large output
- `search` — query indexed output without re-running commands
- `index` — save findings for yourself and teammates
- `stats` — see your token savings

### Cross-Session Memory

```
Session 1                              Session 2
─────────                              ─────────
You: "Build payments module"           You: "Add refund support"

  backend agent spawns (blank)           backend agent spawns
  ↓                                      ↓
  builds Stripe integration              🧠 Brain injects memory:
  creates controller.ts                    • Past work: Stripe integration
  decides: use PaymentIntents API          • Files: controller.ts, stripe.service.ts
  ↓                                        • Decision: use PaymentIntents API
  🧠 Brain indexes everything              • Rule: all endpoints need auth
                                           ↓
                                         picks up exactly where it left off
```

The brain hooks into 7 lifecycle events to capture and inject context automatically:
- **SubagentStart** — injects role-specific memory into new teammates
- **SubagentStop** — parses transcripts, extracts decisions, tracks files
- **SessionStart** — warms up KB with project context (CLAUDE.md, git log, directory tree)
- **SessionEnd** — compresses session into summary for future reference
- **TaskCompleted** — indexes individual task results immediately

Memory is **role-based** — `backend`, `frontend`, `tests`, `devops` each build their own history. When a teammate spawns, it receives only what's relevant to its role.

### Works Without Agent Teams

**You don't need Agent Teams to benefit.** In solo mode:

- All 5 MCP tools work — same 90%+ token savings on every command
- Memory builds from your own sessions via TaskCompleted and SessionEnd hooks
- `/brain-learn`, `/brain-remember`, and all commands work normally
- Convention profiles and git history learning work the same way

Solo mode activates automatically when Agent Teams isn't enabled. No configuration needed.

---

## Quick Start

**Existing repo:**
```
/brain-learn
```
Scans your git history and auto-extracts conventions, architecture, file coupling, and hotspots. Zero config.

**New project:**
```
/brain-seed nextjs-prisma
```
Loads pre-built conventions. Profiles: `nextjs-prisma`, `fastapi`, `go-microservices`, `react-native`, `python-general`.

**Then just use Claude Code normally.** Token savings and memory building happen automatically.

---

## Commands

| Command | Description |
|---------|-------------|
| `/brain-learn` | Auto-learn conventions from git history |
| `/brain-remember <text>` | Store a rule injected into all future teammates |
| `/brain-forget <text>` | Remove a stored memory |
| `/brain-search <query>` | Search the brain knowledge base |
| `/brain-query <role>` | Preview what context a teammate would receive |
| `/brain-export` | Export knowledge as `CONVENTIONS.md` |
| `/brain-stats` | Full stats: memory + KB + token savings |
| `/brain-runs` | List past sessions |
| `/brain-replay [run-id]` | Replay a past session as narrative |
| `/brain-update` | Pull latest version |

---

## Key Features

| | |
|---|---|
| **Token-efficient execution** | 60+ command-aware filters, 8-stage pipeline — 90–97% token reduction |
| **Auto-indexing KB** | Every command output indexed and searchable. Teammates share results |
| **Cross-session memory** | Tasks, decisions, and files indexed per role across sessions |
| **Role-based injection** | Memory routed by agent role — each teammate gets relevant context |
| **Auto-learn** | `/brain-learn` bootstraps the brain from your git history |
| **Solo mode** | Full token savings and memory without Agent Teams |
| **Fully local** | SQLite + FTS5, no cloud, no telemetry, zero external Python dependencies |
| **Cross-platform** | macOS, Linux, WSL2, native Windows — all hooks run via Python |

---

## Architecture

All data is local in `~/.claude-teams-brain/projects/<hash>/brain.db` (SQLite + FTS5).

7 lifecycle hooks capture everything → role-based memory → ranked + deduplicated → injected within a 3000-token budget.

For full technical details, MCP tool reference, and troubleshooting, see the **[full documentation](docs/DOCUMENTATION.md)**.

## License

MIT
