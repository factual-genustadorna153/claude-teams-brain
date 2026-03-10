---
name: brain-query
description: |
  Query the claude-teams-brain for context about a specific role or topic
user_invocable: true
---

# brain-query

Query the brain memory index for context relevant to a role or topic. Shows exactly what a new teammate would receive on spawn.

## Instructions

The user provides a role or topic as an argument (e.g. `/brain-query backend`).

Run:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brain_engine.py query-role "$ARGS" "$CLAUDE_PROJECT_DIR"
```

Display the returned context in a readable format.
If no memory is found for that role, say so and suggest running an Agent Team session with a teammate using that role name.
