# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-03-10

### Added
- **Cross-platform Python hook runner** (`hook_runner.py`) — replaces all bash scripts; works natively on macOS, Linux, WSL2, and Windows. Requires only Python 3.8+ (already a dependency). No WSL2 required on macOS
- **Solo mode** — memory now builds even without Agent Teams enabled. Previous session context is injected into the main Claude instance at every `SessionStart`. Solo mode is now a first-class supported workflow
- **`/brain-seed <profile>`** — instantly seed the brain with pre-built stack conventions. Five built-in profiles: `nextjs-prisma`, `fastapi`, `go-microservices`, `react-native`, `python-general`. Accepts custom JSON profile files
- **`/brain-replay [run-id]`** — time-travel through any past session as a chronological Markdown narrative: timeline of tasks, decisions, files touched, and session summary. Use `latest` for the most recent run
- **`/brain-github-export`** — export CONVENTIONS.md and open a GitHub Pull Request via `gh` CLI. Includes reusable GitHub Actions workflow template (`profiles/github-actions-conventions.yml`) for automatic PR creation after every session
- Auto-seed from existing `.cursorrules`, `AGENTS.md`, and `CONVENTIONS.md` files at session warm-up (zero-config onboarding)
- New `brain_engine.py` commands: `replay-run`, `seed-profile`, `list-profiles`

### Changed
- All hooks now use `python3 hook_runner.py <event>` instead of bash — identical behaviour, all platforms
- Session start message distinguishes solo mode from Agent Teams mode with appropriate messaging
- Agent Teams env var absence no longer shows a warning — replaced with a friendly "solo mode active" tip

## [1.0.4] - 2026-03-10

### Added
- Agent Teams env var check on SessionStart — warns if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is not set
- TaskCompleted confirmation — shows `🧠 Indexed: [agent] task` so users see the brain capturing work in real time
- `/brain-search <query>` — search the full brain knowledge base directly from conversation
- `/brain-stats` — full stats summary: persistent memory + session KB

### Improved
- SessionStart status now shows decisions count alongside tasks and sessions

## [1.0.3] - 2026-03-10

### Added
- Smart context pruning: memories ranked by relevance to the current task description
- Command result caching in batch_execute (60s TTL) — identical commands served from cache
- Session warm-up: CLAUDE.md, git log, directory tree, and config files indexed at SessionStart
- Cache hit counter in stats output

### Improved
- Deduplication of decisions and files before context injection
- Large command output auto-summarized before indexing (keeps KB lean)

## [1.0.2] - 2026-03-10

### Added
- `/brain-remember <text>` — manually store rules and conventions that get injected into every future teammate
- `/brain-forget <text>` — remove a manually stored memory by partial text match
- `/brain-export` — distill all accumulated brain knowledge into a committable `CONVENTIONS.md` file
- Manual memories shown as "Project Rules & Conventions" section in teammate context (before team decisions)

## [1.0.1] - 2026-03-10

### Added
- `/brain-update` skill — pull the latest version from GitHub without reinstalling
- Version check on `SessionStart` — non-intrusive hint when a new version is available
- Token-efficient tool guidance injected into every subagent on spawn (`batch_execute`, `search`, `execute`, `index`)
- Skill files for all user commands: `brain-status`, `brain-query`, `brain-runs`, `brain-clear`
- First-run welcome message on cold start (empty brain)
- `SECURITY.md` with vulnerability reporting process
- GitHub Actions CI — validates JSON, lints shell scripts, checks Python syntax, enforces version consistency

### Fixed
- `marketplace.json` source path corrected to `./claude-teams-brain`

## [1.0.0] - 2026-02-10

### Added

- Persistent memory system for Claude Code Agent Teams
- SQLite brain engine with FTS5 full-text search (`brain_engine.py`)
- 6 lifecycle hooks: SessionStart, SubagentStart, TaskCompleted, SubagentStop, TeammateIdle, SessionEnd
- Auto-injection of context from past sessions into agent conversations
- 4 user commands: `brain-status`, `brain-query`, `brain-runs`, `brain-clear`
- Semantic memory organization by topic
- Claude Code marketplace plugin integration
- Configurable settings via `settings.json`
