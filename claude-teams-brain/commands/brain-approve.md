---
name: brain-approve
description: Approve, reject, or manage pending brain memories
---

Manage pending brain memories. Memories from `/brain-remember` start as PENDING and need approval before being injected into teammates.

Usage: `/brain-approve [all|<id>]`

Examples:
- `/brain-approve` — list all pending memories
- `/brain-approve all` — approve all pending memories
- `/brain-approve 42` — approve a specific memory by ID

If the user provides "all" as argument:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py approve-all-pending "$CLAUDE_PROJECT_DIR"
```

If the user provides a specific task/decision ID:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py approve-task "$ARGS" "$CLAUDE_PROJECT_DIR"
```

If no argument provided, list pending items first:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py list-pending "$CLAUDE_PROJECT_DIR"
```

Then ask the user which items to approve or if they want to approve all.
