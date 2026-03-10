# brain-replay

Time-travel through any past Agent Team session — see who did what, what decisions were made, and what files were touched, in chronological order.

## Trigger

This skill activates when the user runs `/brain-replay`, `/brain-replay <run-id>`, or `/claude-teams-brain:brain-replay`.

## Workflow

### Step 1 — If no run-id given, list recent sessions first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py" list-runs "${CLAUDE_PROJECT_DIR}"
```

Parse the JSON array and present sessions to the user:

```
Recent sessions:
  3de2ae4f  2026-03-10 14:22  3 tasks  2 agents  (backend, frontend)
  8b55bbf1  2026-03-09 11:05  5 tasks  3 agents  (backend, database, tests)
  4849c51a  2026-03-08 09:30  2 tasks  1 agent   (architect)
```

Ask which session to replay, or use `latest` for the most recent. Then proceed to Step 2.

### Step 2 — Replay the session

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py" replay-run "<run_id_or_latest>" "${CLAUDE_PROJECT_DIR}"
```

The special values `latest` and `last` always replay the most recent session.
Partial run IDs work too — `3de2ae` will match `3de2ae4f...`.

Parse the JSON response:
- `status` — "ok" or "not_found"
- `run_id` — the full resolved run ID
- `narrative` — the full Markdown narrative to render

### Step 3 — Render the narrative

Output the `narrative` field directly as formatted Markdown. It contains:

- **Header**: run ID, start/end time, team members, task count
- **Timeline**: numbered list of tasks with agent, timestamp, files touched, decisions, summary
- **All Decisions**: every architectural decision made during the session
- **Files Touched**: all files modified with the agents that touched them
- **Session Summary**: compressed end-of-session summary

### Step 4 — Offer follow-up actions

After showing the replay, offer:
> "**What would you like to do next?**
> - `/brain-export` — export all accumulated knowledge as CONVENTIONS.md
> - `/brain-search <query>` — search for something specific from this session
> - `/brain-query <role>` — preview what a new teammate would receive"

## Notes

- Replay works for both Agent Teams sessions and solo sessions
- The more sessions you have, the more useful replay becomes for understanding project history
- `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PROJECT_DIR}` are set by Claude Code's hook environment
