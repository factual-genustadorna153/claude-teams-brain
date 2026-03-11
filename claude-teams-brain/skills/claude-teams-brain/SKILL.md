---
name: claude-teams-brain
description: |
  Persistent cross-session memory for Claude Code Agent Teams.
  Use when spawning agent teams, reviewing past work, or when context
  from previous sessions is needed. Auto-activates for agent team workflows.
---

# claude-teams-brain Skill

## What it does
claude-teams-brain automatically indexes everything Agent Teams produce — tasks completed, files touched, decisions made — and injects role-specific memory into each new teammate via SubagentStart hooks.

## When to use
- **Always active** during Agent Team sessions (hooks fire automatically)
- Use `/brain-status` to see what's been indexed before starting a new team
- Use `/brain-query <role>` to preview what context a new teammate would receive
- Use `/brain-runs` to review past sessions

## How to spawn a memory-aware Agent Team
When creating a team, the brain works automatically. Just spawn your team normally:

```
Create an agent team. Spawn three teammates:
- backend: implement the API endpoints
- frontend: build the React components
- tests: write integration tests
```

Each teammate automatically receives:
1. Their past work history (tasks completed in this project)
2. Key decisions the team has made across all sessions
3. Files they've previously worked on
4. Project conventions and rules

## Tips for better memory
- Use descriptive agent names matching their role (`backend`, `database`, `security`)
- Let tasks complete naturally so the TaskCompleted hook fires and indexes the work
- The brain gets richer every session — first run is cold, second run onwards gets context
- Use `/brain-remember <rule>` to manually inject rules into every future teammate

## What gets auto-indexed at session start
Every session, the brain automatically indexes into the KB:
- **CLAUDE.md** — project instructions
- **Git log** — last 20 commits
- **Directory tree** — project structure
- **Config files** — package.json, requirements.txt, go.mod, etc.
- **Convention files** — CONVENTIONS.md, AGENTS.md, .cursorrules
- **Stack conventions** — auto-detected and seeded on first session (Next.js, FastAPI, Go, etc.)

## MCP Tools for teammates

Teammates have five MCP tools to keep output out of their context window:

| Tool | When to use |
|------|-------------|
| `batch_execute` | **Default for shell commands.** Run 2+ commands in one call; all output auto-indexed and searchable. Always include `queries`. |
| `search` | Follow-up queries against already-indexed output — no commands re-run. |
| `index` | Manually store findings or analysis for yourself and teammates. |
| `execute` | Single command/script. Set `intent` for large output — auto-indexes instead of returning raw. |
| `stats` | Check bytes indexed vs returned; verify context savings. |

### Standard workflow for teammates

```
1. batch_execute(commands=[...], queries=["what I need to know"])
   → runs commands, indexes all output, returns search results

2. search(queries=["follow-up question"])
   → searches indexed KB without re-running anything

3. index(content="key finding", source="my-analysis")
   → saves conclusion for teammates to search
```

All teammates share the same session KB — one teammate's indexed output is searchable by others.

### Example batch_execute call

```json
{
  "commands": [
    {"label": "tests", "command": "npm test 2>&1"},
    {"label": "git-log", "command": "git log --oneline -20"},
    {"label": "deps", "command": "npm list --depth=0"}
  ],
  "queries": ["failing tests", "recent auth changes", "outdated packages"]
}
```

## Memory location
All data stored locally at `~/.claude-teams-brain/projects/<project-hash>/brain.db`
Never sent anywhere. Fully offline. SQLite — inspectable with any SQLite viewer.

## Resetting
Use `/brain-clear` to wipe memory for this project and start fresh.
